import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from account_profiles import AccountProfileStore, mask_phone


class TestAccountProfileStore(unittest.TestCase):
    def test_phone_is_masked_before_persistence(self):
        self.assertEqual(mask_phone('+55 93 99123-4567'), '+55 •••• 4567')

    def test_accounts_receive_isolated_session_and_state_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            store = AccountProfileStore(Path(temp) / 'accounts.json')
            with patch.dict(os.environ, {'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS': '3'}):
                first = store.create_pending('Loja A')
                second = store.create_pending('Loja B')

            self.assertNotEqual(first.id, second.id)
            self.assertNotEqual(first.session_path, second.session_path)
            self.assertNotEqual(first.state_path, second.state_path)
            self.assertIn(first.id, first.session_path)
            self.assertIn(second.id, second.state_path)

    def test_plan_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            store = AccountProfileStore(Path(temp) / 'accounts.json')
            with patch.dict(os.environ, {'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS': '1'}):
                store.create_pending('Primeira')
                with self.assertRaises(ValueError):
                    store.create_pending('Segunda')

    def test_legacy_session_is_registered_without_moving_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session = root / 'sessions' / 'main'
            session.parent.mkdir(parents=True)
            Path(str(session) + '.session').write_bytes(b'legacy')
            state = root / 'data' / 'local_state.sqlite3'
            state.parent.mkdir(parents=True)
            state.write_bytes(b'')

            store = AccountProfileStore(root / 'data' / 'accounts.json')
            profile = store.ensure_legacy(str(session), str(state))

            self.assertIsNotNone(profile)
            self.assertEqual(profile.id, 'legacy-main')
            self.assertEqual(profile.session_path, str(session))
            self.assertEqual(profile.state_path, str(state))
            self.assertTrue(Path(str(session) + '.session').exists())
            self.assertEqual(store.active().id, 'legacy-main')

    def test_status_update_is_scoped_to_one_account(self):
        with tempfile.TemporaryDirectory() as temp:
            store = AccountProfileStore(Path(temp) / 'accounts.json')
            with patch.dict(os.environ, {'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS': '3'}):
                first = store.create_pending('Loja A')
                second = store.create_pending('Loja B')

            store.update(first.id, status='peer_flood', last_error='rate limit')

            self.assertEqual(store.get(first.id).status, 'peer_flood')
            self.assertEqual(store.get(second.id).status, 'onboarding')
            self.assertEqual(store.get(second.id).last_error, '')


if __name__ == '__main__':
    unittest.main()
