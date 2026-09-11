import unittest
from datetime import datetime, timedelta, timezone

from safety_policy import compute_action_safety, peer_flood_pause_hours


UTC = timezone.utc


def row(timestamp, status, reason=''):
    return {
        'timestamp': timestamp.isoformat(),
        'status': status,
        'reason': reason,
    }


class SafetyPolicyTests(unittest.TestCase):
    def test_backoff_steps(self):
        self.assertEqual(peer_flood_pause_hours(1), 24)
        self.assertEqual(peer_flood_pause_hours(2), 72)
        self.assertEqual(peer_flood_pause_hours(3), 168)
        self.assertEqual(peer_flood_pause_hours(8), 168)

    def test_first_peer_flood_blocks_24_hours(self):
        event = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        state = compute_action_safety(
            [row(event, 'peer_flood')],
            mode='direct',
            now=event + timedelta(hours=1),
        )
        self.assertTrue(state.blocked)
        self.assertEqual(state.kind, 'peer_flood')
        self.assertEqual(state.peer_flood_count, 1)
        self.assertEqual(state.until, event + timedelta(hours=24))

    def test_second_recent_peer_flood_blocks_72_hours(self):
        first = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
        second = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        state = compute_action_safety(
            [row(second, 'peer_flood'), row(first, 'peer_flood')],
            mode='direct',
            now=second + timedelta(minutes=5),
        )
        self.assertEqual(state.peer_flood_count, 2)
        self.assertEqual(state.until, second + timedelta(hours=72))

    def test_third_recent_peer_flood_blocks_seven_days(self):
        events = [
            datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        ]
        state = compute_action_safety(
            [row(value, 'peer_flood') for value in events],
            mode='direct',
            now=events[0] + timedelta(minutes=1),
        )
        self.assertTrue(state.blocked)
        self.assertEqual(state.peer_flood_count, 3)
        self.assertEqual(state.until, events[0] + timedelta(days=7))

    def test_old_peer_flood_outside_window_does_not_raise_streak(self):
        latest = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        old = latest - timedelta(days=15)
        state = compute_action_safety(
            [row(latest, 'peer_flood'), row(old, 'peer_flood')],
            mode='direct',
            now=latest + timedelta(hours=1),
        )
        self.assertEqual(state.peer_flood_count, 1)
        self.assertEqual(state.until, latest + timedelta(hours=24))

    def test_flood_wait_respects_explicit_telegram_time(self):
        event = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        retry = event + timedelta(hours=5)
        state = compute_action_safety(
            [
                row(
                    event,
                    'flood_wait',
                    f'Telegram determinou espera. Não retomar antes de {retry.isoformat()}.',
                )
            ],
            mode='direct',
            now=event + timedelta(hours=1),
        )
        self.assertTrue(state.blocked)
        self.assertEqual(state.kind, 'flood_wait')
        self.assertEqual(state.until, retry)

    def test_direct_and_message_limits_are_independent(self):
        event = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        rows = [row(event, 'peer_flood')]
        direct = compute_action_safety(rows, mode='direct', now=event + timedelta(hours=1))
        messages = compute_action_safety(rows, mode='message', now=event + timedelta(hours=1))
        self.assertTrue(direct.blocked)
        self.assertFalse(messages.blocked)

    def test_recovery_caution_after_pause(self):
        event = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
        state = compute_action_safety(
            [row(event, 'peer_flood')],
            mode='direct',
            now=event + timedelta(hours=25),
        )
        self.assertFalse(state.blocked)
        self.assertTrue(state.recovery_caution)


if __name__ == '__main__':
    unittest.main()
