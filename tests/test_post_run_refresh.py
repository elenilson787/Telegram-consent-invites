from types import SimpleNamespace

from local_app import PreparedQueue
from local_app_v7 import rebuild_prepared_queue


def user(user_id, *, bot=False):
    return SimpleNamespace(id=user_id, bot=bot, username=None, first_name=f'U{user_id}', last_name=None)


def test_rebuild_moves_added_user_to_destination_and_shrinks_queue():
    members = [user(1), user(2), user(3), user(4), user(5)]
    prepared = PreparedQueue(
        source=SimpleNamespace(id=100),
        destination=SimpleNamespace(id=200),
        members=members,
        queue=[members[0], members[1], members[2]],
        extracted=5,
        admins=1,
        bots=0,
        excluded=0,
        already_destination=1,
        previously_processed=0,
        json_path='data/membros.json',
        csv_path='data/membros.csv',
    )

    refreshed = rebuild_prepared_queue(
        prepared,
        source_admin_ids={5},
        destination_ids={1, 4},
        excluded_ids=set(),
        processed_ids={1},
    )

    assert refreshed.already_destination == 2
    assert refreshed.previously_processed == 0
    assert [item.id for item in refreshed.queue] == [2, 3]


def test_rebuild_keeps_failed_processed_user_out_of_queue():
    members = [user(1), user(2), user(3)]
    prepared = PreparedQueue(
        source=SimpleNamespace(id=100),
        destination=SimpleNamespace(id=200),
        members=members,
        queue=members,
        extracted=3,
        admins=0,
        bots=0,
        excluded=0,
        already_destination=0,
        previously_processed=0,
        json_path='data/membros.json',
        csv_path='data/membros.csv',
    )

    refreshed = rebuild_prepared_queue(
        prepared,
        source_admin_ids=set(),
        destination_ids=set(),
        excluded_ids=set(),
        processed_ids={1},
    )

    assert refreshed.already_destination == 0
    assert refreshed.previously_processed == 1
    assert [item.id for item in refreshed.queue] == [2, 3]
