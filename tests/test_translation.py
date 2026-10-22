"""Pure, offline regression tests; use Python 3.12: python -m unittest discover -s tests -v"""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_modes import safe_mode, model_for_mode, transcription_kwargs, ENGLISH_MODELS, MULTILINGUAL_MODELS

class SpeechModeTests(unittest.TestCase):
    def test_arabic_requires_multilingual_model(self):
        self.assertEqual(model_for_mode('base.en', 'arabic_translate'), 'small')
        self.assertEqual(model_for_mode('small', 'arabic_translate'), 'small')
        self.assertEqual(model_for_mode('large-v3', 'arabic_translate'), 'small')
        self.assertTrue(all(not x.endswith('.en') for x in MULTILINGUAL_MODELS))

    def test_english_preserves_previous_model(self):
        self.assertEqual(model_for_mode('base.en', 'english'), 'base.en')
        self.assertEqual(model_for_mode('bogus', 'english'), 'base.en')
        self.assertIn('small.en', ENGLISH_MODELS)

    def test_whisper_arabic_translation_task(self):
        arabic = transcription_kwargs('arabic_translate')
        self.assertEqual(arabic['language'], 'ar')
        self.assertEqual(arabic['task'], 'translate')
        self.assertFalse(arabic['condition_on_previous_text'])
        self.assertIn('Counter-Strike 2', arabic['initial_prompt'])

    def test_whisper_english_transcription_task(self):
        english = transcription_kwargs('english')
        self.assertEqual(english['language'], 'en')
        self.assertEqual(english['task'], 'transcribe')

    def test_invalid_mode_fallback(self):
        self.assertEqual(safe_mode(None), 'english')
        self.assertEqual(safe_mode('fr'), 'english')

if __name__ == '__main__':
    unittest.main()
