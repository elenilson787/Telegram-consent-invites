import os
import tempfile
import unittest
from unittest.mock import patch

from config import Settings, parse_user_ids


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
            'EXCLUDED_USER_IDS',
        ]

        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.dict(os.environ, env, clear=False):
                    with patch.dict(os.environ, {key: '' for key in optional}, clear=False):
                        for key in optional:
                            os.environ.pop(key, None)
                        settings = Settings.load()
            finally:
                os.chdir(old_cwd)

        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.max_invites_per_run, 5)
        self.assertEqual(settings.min_delay_seconds, 15)
        self.assertEqual(settings.max_delay_seconds, 30)
        self.assertEqual(settings.excluded_user_ids, frozenset())

    def test_parse_excluded_user_ids(self):
        self.assertEqual(
            parse_user_ids('7226192599, 123456789,7226192599'),
            frozenset({7226192599, 123456789}),
        )

    def test_invalid_excluded_user_id_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_user_ids('123,abc')

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
