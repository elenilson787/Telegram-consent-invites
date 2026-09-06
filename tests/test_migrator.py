import asyncio
import unittest

from migrator import MigrationEngine, classify_candidates, select_explicit_targets


class FakeUser:
    def __init__(self, user_id, username=None, bot=False):
        self.id = user_id
        self.username = username
        self.first_name = f'User{user_id}'
        self.last_name = None
        self.bot = bot


class FakeReport:
    def __init__(self):
        self.rows = []

    def write(self, user_id, username, name, status, reason=''):
        self.rows.append((user_id, username, name, status, reason))


class NeverCalledClient:
    async def __call__(self, request):
        raise AssertionError('O cliente Telegram não pode ser chamado em DRY_RUN.')


class TestMigrationEngine(unittest.TestCase):
    def test_candidate_classification_excludes_admins_and_manual_ids(self):
        users = [
            FakeUser(1),
            FakeUser(2),
            FakeUser(3, bot=True),
            FakeUser(4),
            FakeUser(5),
        ]

        admins, bots, excluded, already, eligible = classify_candidates(
            users,
            destination_ids={4},
            source_admin_ids={1},
            excluded_user_ids={2},
        )

        self.assertEqual([u.id for u in admins], [1])
        self.assertEqual([u.id for u in bots], [3])
        self.assertEqual([u.id for u in excluded], [2])
        self.assertEqual([u.id for u in already], [4])
        self.assertEqual([u.id for u in eligible], [5])

    def test_admin_exclusion_has_priority_over_other_categories(self):
        users = [FakeUser(1, bot=True), FakeUser(2)]
        admins, bots, excluded, already, eligible = classify_candidates(
            users,
            destination_ids={1, 2},
            source_admin_ids={1},
            excluded_user_ids={1, 2},
        )

        self.assertEqual([u.id for u in admins], [1])
        self.assertEqual(bots, [])
        self.assertEqual([u.id for u in excluded], [2])
        self.assertEqual(already, [])
        self.assertEqual(eligible, [])

    def test_explicit_target_selection_never_substitutes_missing_user(self):
        users = [FakeUser(10), FakeUser(20), FakeUser(30)]
        selected, missing = select_explicit_targets(users, {20, 99})

        self.assertEqual([u.id for u in selected], [20])
        self.assertEqual(missing, {99})

    def test_explicit_target_selection_is_exact(self):
        users = [FakeUser(6879246100), FakeUser(1776570070), FakeUser(8671430555)]
        selected, missing = select_explicit_targets(users, {6879246100})

        self.assertEqual([u.id for u in selected], [6879246100])
        self.assertEqual(missing, set())

    def test_dry_run_never_sends_and_respects_limit(self):
        users = [FakeUser(1), FakeUser(2), FakeUser(3)]
        report = FakeReport()
        engine = MigrationEngine(NeverCalledClient(), object(), max_invites=2, min_delay=0, max_delay=0)

        stats = asyncio.run(engine.run(users, report, dry_run=True))

        self.assertEqual(stats.processed, 2)
        self.assertEqual(stats.added, 0)
        self.assertFalse(stats.stopped)
        self.assertEqual([row[3] for row in report.rows], ['dry_run', 'dry_run'])
        self.assertTrue(all('Nenhuma operação enviada' in row[4] for row in report.rows))

    def test_dry_run_excludes_bots(self):
        users = [FakeUser(1), FakeUser(2, bot=True), FakeUser(3)]
        report = FakeReport()
        engine = MigrationEngine(NeverCalledClient(), object(), max_invites=5, min_delay=0, max_delay=0)

        stats = asyncio.run(engine.run(users, report, dry_run=True))

        self.assertEqual(stats.processed, 2)
        self.assertEqual([row[0] for row in report.rows], [1, 3])


if __name__ == '__main__':
    unittest.main()
