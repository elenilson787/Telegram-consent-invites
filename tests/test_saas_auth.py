import os
import unittest
from unittest.mock import patch

from account_profiles import AccountProfileStore
from local_app_v17 import LocalAppV17
from saas_auth import Entitlements


class TestSaaSCommercialLimits(unittest.TestCase):
    def test_entitlements_parse_server_payload(self):
        ent = Entitlements.from_dict({
            'user_id': 'abc',
            'plan_id': 'pro',
            'plan_name': 'Pro',
            'subscription_status': 'active',
            'entitled': True,
            'max_telegram_accounts': 3,
            'daily_direct_cap': 40,
            'daily_message_cap': 40,
            'history_days': 90,
            'current_period_end': '2026-10-09T00:00:00+00:00',
        })
        self.assertTrue(ent.entitled)
        self.assertEqual(ent.plan_id, 'pro')
        self.assertEqual(ent.max_telegram_accounts, 3)
        self.assertEqual(ent.daily_direct_cap, 40)
        self.assertEqual(ent.history_days, 90)

    def test_server_entitlements_override_local_plan_limits(self):
        ent = Entitlements(
            user_id='abc',
            plan_id='starter',
            plan_name='Starter',
            subscription_status='active',
            entitled=True,
            max_telegram_accounts=1,
            daily_direct_cap=20,
            daily_message_cap=20,
            history_days=30,
        )
        with patch.dict(os.environ, {}, clear=False):
            LocalAppV17._apply_entitlement_env(ent)
            self.assertEqual(os.environ['TELEGRAM_EXTRACTOR_MAX_ACCOUNTS'], '1')
            self.assertEqual(os.environ['TELEGRAM_EXTRACTOR_DAILY_DIRECT_CAP'], '20')
            self.assertEqual(os.environ['TELEGRAM_EXTRACTOR_DAILY_MESSAGE_CAP'], '20')

    def test_account_store_reads_server_applied_limit(self):
        ent = Entitlements(
            user_id='abc',
            plan_id='pro',
            plan_name='Pro',
            subscription_status='active',
            entitled=True,
            max_telegram_accounts=3,
            daily_direct_cap=40,
            daily_message_cap=40,
            history_days=90,
        )
        with patch.dict(os.environ, {}, clear=False):
            LocalAppV17._apply_entitlement_env(ent)
            store = AccountProfileStore.__new__(AccountProfileStore)
            self.assertEqual(store.max_accounts(), 3)


if __name__ == '__main__':
    unittest.main()
