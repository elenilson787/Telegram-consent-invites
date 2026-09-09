import os
import tempfile
import unittest
from unittest.mock import patch

from config import Settings


class TestGuiProvisioning(unittest.TestCase):
    def test_gui_can_open_without_telegram_app_credentials(self):
        env = {
            'MAX_INVITES_PER_RUN': '5',
            'MIN_DELAY_SECONDS': '15',
            'MAX_DELAY_SECONDS': '30',
            'DRY_RUN': 'true',
            'EXCLUDED_USER_IDS': '',
            'TARGET_USER_IDS': '',
        }
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.dict(os.environ, env, clear=True):
                    settings = Settings.load(require_explicit_targets=False)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(settings.api_id, 0)
        self.assertEqual(settings.api_hash, '')
        self.assertFalse(settings.telegram_app_provisioned)

    def test_cli_still_requires_telegram_app_credentials(self):
        with patch.dict(os.environ, {'DRY_RUN': 'true'}, clear=True):
            with self.assertRaises(RuntimeError):
                Settings.load(require_explicit_targets=True)


if __name__ == '__main__':
    unittest.main()
