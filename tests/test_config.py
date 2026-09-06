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
            'TARGET_USER_IDS',
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
        self.assertEqual(settings.target_user_ids, frozenset())

    def test_parse_user_ids_uses_variable_name(self):
        self.assertEqual(
            parse_user_ids(
                '7226192599, 123456789,7226192599',
                'EXCLUDED_USER_IDS',
            ),
            frozenset({7226192599, 123456789}),
        )

    def test_invalid_user_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'TARGET_USER_IDS'):
            parse_user_ids('123,abc', 'TARGET_USER_IDS')

    def test_real_mode_requires_explicit_target(self):
        env = {
            'TELEGRAM_API_ID': '12345',
            'TELEGRAM_API_HASH': 'hash-de-teste',
            'MAX_INVITES_PER_RUN': '1',
            'MIN_DELAY_SECONDS': '15',
            'MAX_DELAY_SECONDS': '30',
            'DRY_RUN': 'false',
            'EXCLUDED_USER_IDS': '',
            'TARGET_USER_IDS': '',
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, 'TARGET_USER_IDS'):
                Settings.load()

    def test_real_mode_accepts_single_explicit_target(self):
        env = {
            'TELEGRAM_API_ID': '12345',
            'TELEGRAM_API_HASH': 'hash-de-teste',
            'MAX_INVITES_PER_RUN': '1',
            'MIN_DELAY_SECONDS': '15',
            'MAX_DELAY_SECONDS': '30',
            'DRY_RUN': 'false',
            'EXCLUDED_USER_IDS': '7226192599',
            'TARGET_USER_IDS': '6879246100',
        }
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.dict(os.environ, env, clear=True):
                    settings = Settings.load()
            finally:
                os.chdir(old_cwd)

        self.assertFalse(settings.dry_run)
        self.assertEqual(settings.target_user_ids, frozenset({6879246100}))
        self.assertEqual(settings.excluded_user_ids, frozenset({7226192599}))

    def test_target_cannot_also_be_excluded(self):
        env = {
            'TELEGRAM_API_ID': '12345',
            'TELEGRAM_API_HASH': 'hash-de-teste',
            'MAX_INVITES_PER_RUN': '1',
            'MIN_DELAY_SECONDS': '15',
            'MAX_DELAY_SECONDS': '30',
            'DRY_RUN': 'false',
            'EXCLUDED_USER_IDS': '6879246100',
            'TARGET_USER_IDS': '6879246100',
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, 'mesmos IDs'):
                Settings.load()

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
