import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Settings


class TestSettings(unittest.TestCase):
    def test_safe_defaults_use_dry_run_and_five_candidates(self):
        env = {
            'TELEGRAM_API_ID': '12345',
            'TELEGRAM_API_HASH': 'hash-de-teste',
            'TELEGRAM_SESSION': 'sessions/teste',
        }
        optional = [
            'MAX_INVITES_PER_RUN',
            'MIN_DELAY_SECONDS',
            'MAX_DELAY_SECONDS',
            'DRY_RUN',
        ]

        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.dict(os.environ, env, clear=False):
                    with patch.dict(os.environ, {key: '' for key in optional}, clear=False):
                        # Valores vazios não representam ausência para int/float;
                        # portanto removemos explicitamente as opcionais.
                        for key in optional:
                            os.environ.pop(key, None)
                        settings = Settings.load()
            finally:
                os.chdir(old_cwd)

        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.max_invites_per_run, 5)
        self.assertEqual(settings.min_delay_seconds, 15)
        self.assertEqual(settings.max_delay_seconds, 30)

    def test_invalid_range_is_rejected(self):
        env = {
            'TELEGRAM_API_ID': '12345',
            'TELEGRAM_API_HASH': 'hash-de-teste',
            'MAX_INVITES_PER_RUN': '5',
            'MIN_DELAY_SECONDS': '30',
            'MAX_DELAY_SECONDS': '15',
            'DRY_RUN': 'true',
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                Settings.load()


if __name__ == '__main__':
    unittest.main()
