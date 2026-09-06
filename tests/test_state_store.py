import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class TestStateStore(unittest.TestCase):
    def test_exclusions_can_be_added_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'state.sqlite3')
            store.add_exclusion(7226192599, 'admin conhecido')
            self.assertEqual(store.excluded_ids(), {7226192599})

            rows = store.list_exclusions()
            self.assertEqual(rows[0]['user_id'], 7226192599)
            self.assertEqual(rows[0]['note'], 'admin conhecido')

            store.remove_exclusion(7226192599)
            self.assertEqual(store.excluded_ids(), set())

    def test_real_attempt_blocks_automatic_retry_but_dry_run_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'state.sqlite3')
            store.record_attempt(10, 20, 1, None, 'User 1', 'dry_run', '')
            self.assertEqual(store.processed_ids(10, 20), set())

            store.record_attempt(10, 20, 1, None, 'User 1', 'privacy', 'restrição')
            self.assertEqual(store.processed_ids(10, 20), {1})

            self.assertEqual(store.processed_ids(10, 99), set())

    def test_recent_history_is_returned_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'state.sqlite3')
            store.record_attempt(1, 2, 10, None, 'Primeiro', 'added', '')
            store.record_attempt(1, 2, 11, None, 'Segundo', 'privacy', '')

            rows = store.recent_history(10)
            self.assertEqual([row['user_id'] for row in rows], [11, 10])


if __name__ == '__main__':
    unittest.main()
