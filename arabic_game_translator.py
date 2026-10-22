"""Safe, offline Arabic -> English CS2 callouts with an optional Argos fallback.

Never guesses arbitrary English text from unmatched Arabic. The source transcription
is displayed separately to let a human diagnose recognition mistakes.
"""
from __future__ import annotations
import re
import unicodedata

NUMBERS = {
    'واحد': 'One', 'واحدة': 'One', 'واحده': 'One', 'احد': 'One', '1': 'One',
    'تنين': 'Two', 'اتنين': 'Two', 'اثنين': 'Two', 'اثنان': 'Two', '2': 'Two',
    'ثلاثة': 'Three', 'ثلاثه': 'Three', 'تلاتة': 'Three', 'تلاته': 'Three', 'تلات': 'Three', 'ثلاث': 'Three', '3': 'Three',
    'اربعة': 'Four', 'اربعه': 'Four', '4': 'Four',
    'خمسة': 'Five', 'خمسه': 'Five', '5': 'Five',
}
LOCATIONS = {
    'ميد': 'mid', 'mid': 'mid', 'ميدل': 'mid', 'منتصف': 'mid', 'نص': 'mid',
    'شورت': 'short', 'short': 'short', 'قصير': 'short',
    'لونغ': 'long', 'لونج': 'long', 'long': 'long', 'طويل': 'long',
    'كونكتور': 'connector', 'كونكتر': 'connector', 'كونكتير': 'connector',
    'بالاس': 'palace', 'بلاس': 'palace', 'بلس': 'palace',
    'رامب': 'ramp', 'بانانا': 'banana', 'تونل': 'tunnels', 'تونيل': 'tunnels',
    'ويندو': 'window', 'وندوز': 'window', 'ويندوز': 'window',
    'اندر': 'under', 'كات': 'catwalk', 'سايت': 'site',
    'سباون': 'spawn', 'بي': 'B', 'b': 'B', 'اي': 'A', 'a': 'A',
}
WEAPONS = {
    'اوب': 'AWP', 'اويبي': 'AWP', 'اوبب': 'AWP', 'awp': 'AWP',
    'سنايبر': 'AWP', 'كلاش': 'AK', 'كلاشينكوف': 'AK', 'اك': 'AK',
}
SKIP = {'في', 'بال', 'بل', 'ب', 'على', 'عال', 'يا', 'شباب', 'هني', 'هن',
        'فيه', 'فيهن', 'هناك', 'هونيك', 'هو', 'معه', 'معو', 'عنده', 'عندو',
        'واحدن', 'العدو', 'عدو', 'حاليا', 'هلق', 'ال', 'اي', 'هيك'}


def ar_norm(text: str) -> str:
    text = unicodedata.normalize('NFKC', str(text or ''))
    text = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', text)
    text = text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ٱ':'ا','ى':'ي','ؤ':'و','ئ':'ي','ة':'ه'}))
    text = re.sub(r'[^\u0600-\u06ff\w\s]', ' ', text.lower())
    return ' '.join(text.split())


def _value(tok: str, options: dict) -> str | None:
    if tok in options: return options[tok]
    for prefix in ('بال', 'عال', 'ال', 'بل', 'ب'):
        if tok.startswith(prefix) and tok[len(prefix):] in options:
            return options[tok[len(prefix):]]
    return None


def _contains(tokens: list[str], keys: set[str]) -> bool:
    return any(t in keys for t in tokens)


def translate_callout(arabic: str) -> str | None:
    """Only recognize explicit tactical patterns; decline anything ambiguous."""
    s = ar_norm(arabic)
    if not s or len(s) > 130: return None
    toks = s.split()
    if not toks or len(toks) > 15: return None
    # Avoid confidently reversing meaning of negated phrases.
    if _contains(toks, {'ما', 'مو', 'مش', 'مافي', 'مفيش', 'لا', 'موفي'}):
        return None
    count = next((NUMBERS[t] for t in toks if t in NUMBERS), None)
    # Arabic ASR commonly spells AWP aloud as three separate words.
    if any(phrase in ' ' + s + ' ' for phrase in (' ايه دبليو بي ', ' اي دبليو بي ', ' اي دابليو بي ', ' ايه دابليو بي ')):
        return f'{count or "Enemy"} has an AWP'
    if count is None and any(t in toks for t in ('عشرة','عشره','ستة','سته','سبعة','سبعه','ثمانية','ثمانيه','تسعة','تسعه')):
        return None
    loc = next((_value(t, LOCATIONS) for t in toks if _value(t, LOCATIONS)), None)
    weapon = next((_value(t, WEAPONS) for t in toks if _value(t, WEAPONS)), None)
    if weapon and (count or _contains(toks, {'معه','معو','معهم','معهن','عنده','عندو','شايل','ماسك','معا'})):
        return f'{count or "Enemy"} has an {weapon}' if weapon == 'AWP' else f'{count or "Enemy"} has an {weapon}'
    if _contains(toks, {'دمه','دمو','دمهن','هب','اتشبي','اتش','مضروب'}) and _contains(toks, {'قليل','ضعيف','ون','واحد','لو','قليله','قليلة','شوي'}):
        return 'One low HP' if count == 'One' else 'Enemy low HP'
    if _contains(toks, {'فلاش','فلاشة','فلاشه','فلاشينغ'}): return 'Flashing'
    if _contains(toks, {'ساعدوني','مساعده','مساعدة','باكاب','باكب','هيلب'}): return 'Need backup'
    if _contains(toks, {'اسكتوا','اسكت','هدوء'}): return 'Quiet'
    if _contains(toks, {'ازرع','ازرعوا','بلانت','بلنت'}): return 'Plant the bomb'
    if _contains(toks, {'ارجعوا','ارجعو','روتيت','روتيتوا','لفوا','حولوا'}):
        return ('Rotate to ' + loc.upper()) if loc in ('A','B') else 'Rotate back'
    if _contains(toks, {'راش','رش','راشوا','راشوو','اهجموا','هجوم','بوش','بوشوا'}):
        return 'Rush ' + loc.upper() if loc in ('A','B') else 'Push together'
    if _contains(toks, {'انتبه','انتبهوا','راقب','راقبوا','ديروا','دير'}) and loc:
        return 'Watch ' + loc
    if loc:
        if count: return f'{count} {loc}'
        if _contains(toks, {'عدو','اعداء','خصم','واحدن'}): return 'Enemy ' + loc
        if len(toks) <= 3 and all(t in SKIP or _value(t, LOCATIONS) for t in toks):
            return loc.upper() if loc in ('A','B') else loc.capitalize()
    return None


def _installed_argos_translation():
    """Never downloads models or talks to internet during gameplay."""
    try:
        import argostranslate.translate as tr
        langs = tr.get_installed_languages()
        ar = next((x for x in langs if x.code == 'ar'), None)
        en = next((x for x in langs if x.code == 'en'), None)
        return ar.get_translation(en) if ar and en else None
    except (ImportError, LookupError, OSError, AttributeError):
        return None


def translate_arabic(text: str) -> tuple[str, str]:
    """(English result, pipeline label) - empty result means DO NOT SEND."""
    if not text or not re.search(r'[\u0600-\u06ff]', text):
        return '', 'NO_ARABIC_TRANSCRIPT'
    tactical = translate_callout(text)
    if tactical: return tactical, 'CS2_GLOSSARY'
    translator = _installed_argos_translation()
    if translator is None:
        return '', 'NO_MATCH_INSTALL_ARGOS_FOR_GENERAL_SENTENCES'
    try:
        out = str(translator.translate(text) or '').strip()
    except Exception:
        return '', 'ARGOS_TRANSLATION_FAILED'
    if not out or re.search(r'[\u0600-\u06ff]', out):
        return '', 'NO_ENGLISH_RESULT'
    return ' '.join(out.split()), 'ARGOS_OFFLINE'
