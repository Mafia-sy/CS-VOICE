"""JSON settings for MAFIA VOICE — safe defaults and atomic saving."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESOURCES = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
HERE = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
if getattr(sys, 'frozen', False):
    CONFIG_PATH = Path(os.environ.get('APPDATA', str(Path.home()))) / 'MAFIA_VOICE_CONTROL_V3_1' / 'config.json'
else:
    CONFIG_PATH = HERE / 'config.json'

DEFAULTS = {
    'target_process': 'cs2.exe',
    'model': 'base.en',
    'speech_mode': 'english',
    'english_model': 'base.en',
    'arabic_model': 'small',
    'auto_send': True,
    'team_only': True,
    'team_chat_key': 'u',
    'all_chat_key': 'y',
    'push_to_talk_key': 'f8',
    'toggle_chat_key': 'f9',
    'microphone_device': None,
    'max_seconds': 8,
    'silence_rms': 0.006,
    'max_chars': 110,
    'chat_open_delay': 0.22,
    'type_interval': 0.012,
    'minimize_to_tray': True,
}


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                config.update({k: v for k, v in loaded.items() if k in DEFAULTS})
                # V3 compatibility: the old model selection becomes the English profile.
                if 'english_model' not in loaded and str(loaded.get('model', '')).endswith('.en'):
                    config['english_model'] = loaded['model']
        except (OSError, ValueError):
            pass
    return config


def save_config(config: dict) -> None:
    content = {k: config.get(k, v) for k, v in DEFAULTS.items()}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(content, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, CONFIG_PATH)
