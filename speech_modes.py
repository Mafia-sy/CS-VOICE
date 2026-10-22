"""MAFIA VOICE V3.1 multilingual speech mode helpers. Offline inference."""
from __future__ import annotations

SUPPORTED = ('english', 'arabic_translate')
ENGLISH_MODELS = ('tiny.en', 'base.en', 'small.en', 'medium.en')
MULTILINGUAL_MODELS = ('tiny', 'base', 'small', 'medium')


def safe_mode(value: object) -> str:
    return value if value in SUPPORTED else 'english'


def model_for_mode(model: str, mode: str) -> str:
    """Never run Arabic translation on an English-only .en model."""
    if safe_mode(mode) == 'arabic_translate':
        return model if model in MULTILINGUAL_MODELS else 'small'
    return model if model in ENGLISH_MODELS + MULTILINGUAL_MODELS else 'base.en'


def transcription_kwargs(mode: str) -> dict:
    """Arabic: transcribe what the player said; NEVER seed English phrases.

    English retains its existing recognition settings unchanged.
    """
    if safe_mode(mode) == 'arabic_translate':
        return {
            'language': 'ar', 'task': 'transcribe', 'beam_size': 5,
            'condition_on_previous_text': False, 'temperature': 0,
            'vad_filter': True,
            'vad_parameters': {'min_speech_duration_ms': 160,
                               'min_silence_duration_ms': 240,
                               'speech_pad_ms': 180},
            # IMPORTANT: no English `initial_prompt` with invented CS2 callouts.
        }
    return {
        'language': 'en', 'task': 'transcribe', 'beam_size': 1,
        'condition_on_previous_text': False,
        'initial_prompt': (
            'Counter-Strike 2 callouts: In short. In long. He has an AWP. '
            'One HP. Two mid. Rush B. One palace. Flashing. I am rotating.'
        ),
    }


def inspect_translated_text(raw: str, mode: str) -> tuple[str, str]:
    """Return diagnostic status and safe English candidate; never silently strip Arabic."""
    value = ' '.join(str(raw or '').split())
    if not value:
        return ('empty', '')
    if safe_mode(mode) == 'arabic_translate':
        # Includes the common Arabic and Arabic presentation forms Unicode blocks.
        has_arabic = any('\u0600' <= c <= '\u06ff' or
                         '\u0750' <= c <= '\u077f' or
                         '\u08a0' <= c <= '\u08ff' or
                         '\ufb50' <= c <= '\ufdff' or
                         '\ufe70' <= c <= '\ufeff' for c in value)
        if has_arabic:
            return ('untranslated_arabic', '')
    return ('ok', value)
