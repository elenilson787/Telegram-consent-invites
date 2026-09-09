import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from account_profiles import AccountProfileStore, normalize_phone


class TestPhoneNormalization(unittest.TestCase):
    def test_brazil_local_number_gets_country_code(self):
        self.assertEqual(
            normalize_phone('(93) 99999-9999'),
            '+5593999999999',
        )
        self.assertEqual(
            normalize_phone('93999999999'),
            '+5593999999999',
        )

    def test_explicit_brazil_country_code_is_preserved(self):
        self.assertEqual(
            normalize_phone('+55 93 99999-9999'),
            '+5593999999999',
        )
        self.assertEqual(
            normalize_phone('5593999999999'),
            '+5593999999999',
        )

    def test_international_number_with_plus_is_preserved(self):
        self.assertEqual(normalize_phone('+351912345678'), '+351912345678')

    def test_invalid_short_number_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inválido'):
            normalize_phone('12345')


class TestDuplicateTelegramAccounts(unittest.TestCase):
    def test_find_by_telegram_user_id_ignores_current_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'accounts.json'
            with patch.dict(os.environ, {'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS': '3'}, clear=False):
                store = AccountProfileStore(path)
                first = store.create_pending('Primeira')
                first = store.update(
                    first.id,
                    status='offline',
                    telegram_user_id=123456789,
                    display_name='Conta A',
                )
                second = store.create_pending('Segunda')

                duplicate = store.find_by_telegram_user_id(
                    123456789,
                    exclude_account_id=second.id,
                )
                self.assertIsNotNone(duplicate)
                self.assertEqual(duplicate.id, first.id)

                same = store.find_by_telegram_user_id(
                    123456789,
                    exclude_account_id=first.id,
                )
                self.assertIsNone(same)

    def test_removing_duplicate_releases_plan_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'accounts.json'
            with patch.dict(os.environ, {'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS': '2'}, clear=False):
                store = AccountProfileStore(path)
                first = store.create_pending('Primeira')
                store.update(first.id, telegram_user_id=987654321, status='offline')
                duplicate = store.create_pending('Duplicada')
                self.assertEqual(len(store.list()), 2)

                store.remove(duplicate.id)
                self.assertEqual(len(store.list()), 1)

                replacement = store.create_pending('Nova válida')
                self.assertIsNotNone(replacement)
                self.assertEqual(len(store.list()), 2)


if __name__ == '__main__':
    unittest.main()
