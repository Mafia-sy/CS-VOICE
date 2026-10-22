"""Visible diagnostics even when launched with pythonw.exe (no console)."""
from __future__ import annotations

import ctypes
import sys
import traceback
from pathlib import Path


def main():
    try:
        from mafia_voice_v3 import main as gui_main
        gui_main()
    except BaseException:
        msg = traceback.format_exc()
        from config_store import CONFIG_PATH
        log = CONFIG_PATH.parent / 'MAFIA_VOICE_ERROR.log' 
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(msg, encoding='utf-8')
        except OSError:
            pass
        print(msg, file=sys.stderr)
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                'MAFIA VOICE could not start.\n\n'
                'Open START_DEBUG.bat or check MAFIA_VOICE_ERROR.log.\n\n'
                + msg[-600:],
                'MAFIA VOICE - Startup Error', 0x10,
            )
        except Exception:
            pass
        raise SystemExit(1)


if __name__ == '__main__':
    main()
