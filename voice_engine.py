"""Local speech-to-CS2 chat engine. No game memory access, DLLs or Steam API."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import re
import threading
import time

import keyboard
import numpy as np
import psutil
import pyautogui
import sounddevice as sd
from faster_whisper import WhisperModel
from PySide6.QtCore import QObject, Signal

from config_store import save_config
from speech_modes import model_for_mode, safe_mode, transcription_kwargs, inspect_translated_text
from arabic_game_translator import translate_arabic

pyautogui.PAUSE = 0.035


def foreground_app() -> str:
    """Executable name of the foreground window (Windows only)."""
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ''
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ''


def normalize_text(text: str, max_chars: int = 110) -> str:
    text = ' '.join(text.strip().split())
    text = re.sub(r"[^a-zA-Z0-9 .,!?':()/\-]", '', text)
    text = text.strip(' .,')
    fixes = {
        'in short': 'In short', 'in long': 'In long',
        'he have awp': 'He has an AWP', 'he has awp': 'He has an AWP',
        'he has an awp': 'He has an AWP', 'one hp': 'One HP',
        'one short': 'One short', 'one long': 'One long',
        'two mid': 'Two mid', 'rush b': 'Rush B',
    }
    return fixes.get(text.lower().rstrip('.!?'), text)[:max(1, min(int(max_chars), 255))]


class VoiceEngine(QObject):
    status_changed = Signal(str)            # OFFLINE / LOADING / DOWNLOADING / READY / RECORDING / PROCESSING / ERROR
    event = Signal(str, str)                 # type, message
    level_changed = Signal(float)           # 0..1 mic peak display
    heard = Signal(str)                      # transcribed message
    mode_changed = Signal(bool)             # True = team

    def __init__(self, config: dict, parent: QObject | None = None):
        super().__init__(parent)
        self.config = config
        self.enabled = False
        self.recording = False
        self._busy = False
        self._state_guard = threading.RLock()
        self._stream = None
        self._frames = []
        self._samples_recorded = 0
        self._sample_rate = 48000
        self._audio_ticks = 0
        self._model = None
        self._model_id = None
        self._generation = 0
        self._hotkey_hooks = []
        self._mouse_listener = None

    @property
    def team_only(self) -> bool:
        return bool(self.config.get('team_only', True))

    def _is_game_active(self) -> bool:
        return foreground_app() == str(self.config.get('target_process', 'cs2.exe')).lower()

    def start(self) -> None:
        with self._state_guard:
            if self.enabled:
                return
            self.enabled = True
            self._generation += 1
            token = self._generation
        self.status_changed.emit('LOADING')
        self.event.emit('info', 'Loading local speech model. First launch may download it...')
        threading.Thread(target=self._prepare, args=(token,), daemon=True).start()

    def _prepare(self, token: int) -> None:
        try:
            mode = safe_mode(self.config.get('speech_mode', 'english'))
            name = model_for_mode(str(self.config.get('model', 'base.en')), mode)
            self.event.emit('info', f'Offline model: {name} | ' + ('Arabic → English' if mode == 'arabic_translate' else 'English'))
            # Load into a local variable, then publish only if this start is current.
            if self._model is not None and self._model_id == name:
                loaded_model = self._model
            else:
                # Try the local Hugging Face cache first. Only fetch the model on a
                # cache miss, and clearly disclose the one-time download in the UI.
                try:
                    loaded_model = WhisperModel(
                        name, device='cpu', compute_type='int8', local_files_only=True
                    )
                except OSError as cache_error:
                    from huggingface_hub.errors import LocalEntryNotFoundError
                    if not isinstance(cache_error, LocalEntryNotFoundError):
                        raise
                    self.status_changed.emit('DOWNLOADING')
                    self.event.emit('info',
                        f'First use: downloading multilingual speech model {name} '
                        'from Hugging Face. This downloads model files only, not microphone audio.')
                    loaded_model = WhisperModel(
                        name, device='cpu', compute_type='int8'
                    )
                if token != self._generation or not self.enabled:
                    return
            with self._state_guard:
                if not self.enabled or token != self._generation:
                    return
                self._model = loaded_model
                self._model_id = name
            self._bind_hotkeys()
            with self._state_guard:
                if not self.enabled or token != self._generation:
                    self._unbind_hotkeys()
                    return
            self.status_changed.emit('READY')
            self.event.emit('info', 'Listening is enabled. Hold the PTT button while CS2 is focused.')
        except Exception as exc:
            with self._state_guard:
                if token != self._generation:
                    return
                self.enabled = False
            self._unbind_hotkeys()
            self.status_changed.emit('ERROR')
            self.event.emit('error', f'Startup error: {type(exc).__name__}: {exc}')

    def _bind_hotkeys(self) -> None:
        """Bind PTT and chat toggle to keyboard or mouse 4/5.

        One listener handles both mouse buttons; conflicting keys are rejected in UI.
        """
        self._unbind_hotkeys()
        key = str(self.config.get('push_to_talk_key', 'f8')).lower()
        toggle_key = str(self.config.get('toggle_chat_key', 'f9')).lower()
        mouse_keys = ('mouse4', 'mouse5')
        if key not in mouse_keys:
            self._hotkey_hooks.append(keyboard.on_press_key(key, lambda _: self.begin_recording()))
            self._hotkey_hooks.append(keyboard.on_release_key(key, lambda _: self.end_recording()))
        if toggle_key not in mouse_keys:
            self._hotkey_hooks.append(keyboard.on_release_key(toggle_key, lambda _: self.toggle_mode()))
        if key in mouse_keys or toggle_key in mouse_keys:
            from pynput import mouse
            name_to_btn = {'mouse4': mouse.Button.x1, 'mouse5': mouse.Button.x2}
            ptt_button = name_to_btn.get(key)
            mode_button = name_to_btn.get(toggle_key)

            def mouse_action(x, y, button, pressed):
                if button == ptt_button:
                    if pressed:
                        self.begin_recording()
                    else:
                        self.end_recording()
                elif button == mode_button and not pressed:
                    self.toggle_mode()

            self._mouse_listener = mouse.Listener(on_click=mouse_action)
            self._mouse_listener.start()

    def _unbind_hotkeys(self) -> None:
        for hook in self._hotkey_hooks:
            try:
                keyboard.unhook(hook)
            except Exception:
                pass
        self._hotkey_hooks.clear()
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

    def stop(self) -> None:
        with self._state_guard:
            self.enabled = False
            self._generation += 1
        self._unbind_hotkeys()
        self._cancel_recording()
        self.status_changed.emit('OFFLINE')
        self.level_changed.emit(0)
        self.event.emit('info', 'Listening disabled.')

    def _cancel_recording(self) -> None:
        with self._state_guard:
            self.recording = False
            stream = self._stream
            self._stream = None
            self._frames = []
            self._samples_recorded = 0
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def begin_recording(self) -> None:
        with self._state_guard:
            if not self.enabled or self.recording or self._busy or self._model is None:
                return
            if not self._is_game_active():
                return
            self._frames = []
            self._samples_recorded = 0
            self._audio_ticks = 0
            self.recording = True
            device = self.config.get('microphone_device')
            try:
                details = sd.query_devices(device, 'input')
                self._sample_rate = int(details['default_samplerate'])
                self._stream = sd.InputStream(
                    device=device,
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype='float32',
                    blocksize=2048,
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception as exc:
                self.recording = False
                self._stream = None
                self.status_changed.emit('ERROR')
                self.event.emit('error', f'Microphone error: {exc}')
                return
        self.status_changed.emit('RECORDING')

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if not self.recording:
            return
        max_samples = int(self._sample_rate * float(self.config.get('max_seconds', 8)))
        remaining = max_samples - self._samples_recorded
        if remaining > 0:
            chunk = indata[:remaining, 0].copy()
            self._frames.append(chunk)
            self._samples_recorded += len(chunk)
        self._audio_ticks += 1
        if self._audio_ticks % 4 == 0:
            peak = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
            self.level_changed.emit(min(1.0, peak * 9.0))

    def end_recording(self) -> None:
        with self._state_guard:
            if not self.recording:
                return
            self.recording = False
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                self.event.emit('error', f'Audio stop warning: {exc}')
        self.level_changed.emit(0)
        with self._state_guard:
            if not self.enabled:
                self._frames.clear()
                return
            if not self._frames:
                self.status_changed.emit('READY')
                return
            audio = np.concatenate(self._frames).astype('float32', copy=False)
            self._frames = []
            rate = self._sample_rate
            if self._busy:
                return
            self._busy = True
        if len(audio) < rate * 0.25:
            self._busy = False
            self.status_changed.emit('READY')
            self.event.emit('warning', 'Hold the key a little longer.')
            return
        self.status_changed.emit('PROCESSING')
        token = self._generation
        threading.Thread(target=self._recognize, args=(audio, rate, token), daemon=True).start()

    def _recognize(self, audio: np.ndarray, rate: int, token: int) -> None:
        try:
            mode = safe_mode(self.config.get('speech_mode', 'english'))
            model = self._model
            rms = float(np.sqrt(np.mean(audio * audio)))
            if rms < float(self.config.get('silence_rms', 0.006)):
                self.event.emit('warning', 'No clear microphone signal detected.')
                return
            if rate != 16000:
                n = max(1, int(round(len(audio) * 16000 / rate)))
                audio = np.interp(
                    np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio
                ).astype('float32')
            if model is None:
                self.event.emit('error', 'Speech model is not loaded yet.')
                return
            segments, _ = model.transcribe(audio, **transcription_kwargs(mode))
            raw_text = ' '.join(segment.text for segment in segments).strip()
            if not raw_text:
                self.event.emit('warning', 'No clear speech transcribed; nothing sent.')
                return
            if mode == 'arabic_translate':
                english_text, method = translate_arabic(raw_text)
                self.event.emit('translation_trace', f'AR HEARD: {raw_text[:110]} | EN: {english_text or "[not translated]"} | {method}')
                if not english_text:
                    self.event.emit('warning',
                        'Arabic recognized, but translation is uncertain: NOTHING SENT. '
                        'If it is a general sentence, run INSTALL_TRANSLATOR.bat for offline Argos.')
                    return
            else:
                english_text = raw_text
            message = normalize_text(english_text, int(self.config.get('max_chars', 110)))
            if not message:
                self.event.emit('warning', 'Speech could not be recognized.')
                return
            self.heard.emit(message)
            self.event.emit('heard', message)
            if not self.enabled or token != self._generation:
                self.event.emit('warning', 'Speech mode changed or listening disabled; nothing sent.')
                return
            if not self._is_game_active():
                self.event.emit('warning', 'CS2 is not in focus; nothing sent.')
                return
            if not bool(self.config.get('auto_send', True)):
                self.event.emit('preview', 'Preview mode; auto-send is off.')
                return
            key = str(self.config.get('team_chat_key', 'u') if self.team_only else self.config.get('all_chat_key', 'y'))
            pyautogui.press(key)
            time.sleep(float(self.config.get('chat_open_delay', 0.22)))
            if not self.enabled or token != self._generation or not self._is_game_active():
                self.event.emit('warning', 'Mode or game focus changed before typing; nothing typed.')
                return
            pyautogui.write(message, interval=float(self.config.get('type_interval', 0.012)))
            time.sleep(.06)
            if self.enabled and token == self._generation and self._is_game_active():
                pyautogui.press('enter')
                self.event.emit('attempted', message)
            else:
                self.event.emit('warning', 'Game focus changed before Enter; send cancelled.')
        except Exception as exc:
            self.event.emit('error', f'{type(exc).__name__}: {exc}')
        finally:
            with self._state_guard:
                self._busy = False
            if self.enabled and token == self._generation:
                self.status_changed.emit('READY')

    def test_speech_translation(self) -> None:
        """Diagnose the selected speech language without needing CS2 or sending a message."""
        with self._state_guard:
            if not self.enabled or self._model is None:
                self.event.emit('translation_test', 'Enable the voice system and wait for READY first. The Arabic model may need downloading.')
                return
            if self.recording or self._busy:
                self.event.emit('translation_test', 'Speech engine busy. Finish the current phrase and retry.')
                return
            self._busy = True
            token = self._generation
            mode = safe_mode(self.config.get('speech_mode', 'english'))
            model = self._model
            device = self.config.get('microphone_device')
        self.status_changed.emit('TESTING')
        self.event.emit('translation_test', 'Recording 4.5 seconds NOW. Speak a full sentence clearly. No chat message will be sent.')
        threading.Thread(target=self._speech_test_worker,
                         args=(token, mode, model, device), daemon=True).start()

    def _speech_test_worker(self, token: int, mode: str, model, device) -> None:
        try:
            d = sd.query_devices(device, 'input')
            rate = int(d['default_samplerate'])
            audio = sd.rec(int(rate * 4.5), samplerate=rate, channels=1,
                           dtype='float32', device=device)
            sd.wait()
            audio = audio[:, 0].copy()
            rms = float(np.sqrt(np.mean(audio * audio)))
            if rms < max(0.002, float(self.config.get('silence_rms', .006)) * .5):
                self.event.emit('translation_test',
                    f'No clear microphone signal (RMS {rms:.4f}). Select a different microphone or increase Windows mic volume.')
                return
            if rate != 16000:
                n = max(1, int(round(len(audio) * 16000 / rate)))
                audio = np.interp(np.linspace(0, len(audio)-1, n),
                                  np.arange(len(audio)), audio).astype('float32')
            begun = time.monotonic()
            segments, info = model.transcribe(audio, **transcription_kwargs(mode))
            raw = ' '.join(segment.text for segment in segments).strip()
            seconds = time.monotonic() - begun
            model_id = model_for_mode(str(self.config.get('model','small')), mode)
            if mode == 'arabic_translate':
                english, method = translate_arabic(raw)
                result = (f'AR HEARD: {raw or "[nothing]"} | ENGLISH: {english or "[nothing - not sent]"} '
                          f'| {method} | model {model_id} | {seconds:.1f}s')
            else:
                result = (f'ENGLISH HEARD: {raw or "[nothing]"} | model {model_id} | {seconds:.1f}s')
            if self.enabled and token == self._generation:
                self.event.emit('translation_test', result)
        except Exception as exc:
            self.event.emit('translation_test', f'SPEECH TEST ERROR: {type(exc).__name__}: {exc}')
        finally:
            with self._state_guard:
                self._busy = False
            if self.enabled and token == self._generation:
                self.status_changed.emit('READY')

    def toggle_mode(self) -> None:
        self.set_mode(not self.team_only)

    def set_mode(self, team: bool) -> None:
        self.config['team_only'] = bool(team)
        save_config(self.config)
        self.mode_changed.emit(bool(team))
        self.event.emit('info', 'Chat mode: ' + ('TEAM' if team else 'ALL'))
