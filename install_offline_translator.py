"""One-time download of the Argos Arabic -> English package. Never runs in the game."""
from __future__ import annotations
import sys
import argostranslate.package
import argostranslate.translate


def main():
    langs = argostranslate.translate.get_installed_languages()
    ar = next((l for l in langs if l.code == 'ar'), None)
    en = next((l for l in langs if l.code == 'en'), None)
    if ar and en:
        try:
            if ar.get_translation(en):
                print('Arabic -> English offline translator already installed.')
                return 0
        except Exception:
            pass
    print('Fetching model list from Argos. Internet is needed only for this installation.')
    argostranslate.package.update_package_index()
    avail = argostranslate.package.get_available_packages()
    model = next((p for p in avail if p.from_code == 'ar' and p.to_code == 'en'), None)
    if model is None:
        print('ERROR: no direct Arabic -> English Argos package in current index.')
        return 2
    print('Downloading Arabic -> English translation model...')
    path = model.download()
    argostranslate.package.install_from_path(path)
    print('Installed. Try a translation:')
    print(argostranslate.translate.translate('مرحبا كيف حالك', 'ar', 'en'))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('Installation failed:', type(exc).__name__, exc)
        sys.exit(1)
