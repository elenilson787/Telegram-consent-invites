import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from state_store import StateStore


class TestAccountHealth(unittest.TestCase):
    def make_store(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / 'state.sqlite3'
        return tmp, StateStore(path)

    def test_daily_summary_ignores_dry_run(self):
        tmp, store = self.make_store()
        try:
            store.record_attempt(1, 2, 10, '', 'A', 'dry_run', '')
            store.record_attempt(1, 2, 11, '', 'B', 'added', '')
            store.record_attempt(1, 2, 12, '', 'C', 'invalid_user', '')
            store.record_message_attempt(1, 2, 20, '', 'D', 'message_dry_run', '')
            store.record_message_attempt(1, 2, 21, '', 'E', 'message_sent', '')

            summary = store.activity_counts_for_day()

            self.assertEqual(summary['direct_attempts'], 2)
            self.assertEqual(summary['added'], 1)
            self.assertEqual(summary['messages_attempted'], 1)
            self.assertEqual(summary['messages_sent'], 1)
        finally:
            tmp.cleanup()

    def test_rate_limits_are_counted_by_channel(self):
        tmp, store = self.make_store()
        try:
            store.record_attempt(1, 2, 10, '', 'A', 'peer_flood', 'limit')
            store.record_attempt(1, 2, 11, '', 'B', 'flood_wait', 'wait')
            store.record_message_attempt(1, 2, 20, '', 'C', 'message_peer_flood', 'limit')

            summary = store.activity_counts_for_day()

            self.assertEqual(summary['direct_rate_limits'], 2)
            self.assertEqual(summary['message_rate_limits'], 1)
        finally:
            tmp.cleanup()

    def test_seven_day_series_includes_today(self):
        tmp, store = self.make_store()
        try:
            series = store.activity_series(7)
            self.assertEqual(len(series), 7)
            self.assertEqual(series[-1]['day'], datetime.now().astimezone().date().isoformat())
        finally:
            tmp.cleanup()

    def test_old_day_does_not_enter_today(self):
        tmp, store = self.make_store()
        try:
            store.record_attempt(1, 2, 10, '', 'A', 'added', '')
            yesterday = datetime.now().astimezone().date() - timedelta(days=1)
            self.assertEqual(store.activity_counts_for_day(yesterday)['added'], 0)
            self.assertEqual(store.activity_counts_for_day()['added'], 1)
        finally:
            tmp.cleanup()


if __name__ == '__main__':
    unittest.main()
