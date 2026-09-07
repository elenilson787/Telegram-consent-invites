import asyncio

from message_invites import MessageInviteEngine, parse_opt_in_ids, render_invite_message


class FakeUser:
    def __init__(self, user_id, first_name='Pessoa', username=None):
        self.id = user_id
        self.first_name = first_name
        self.last_name = None
        self.username = username


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, user, message):
        self.sent.append((user.id, message))


def test_parse_opt_in_ids_accepts_common_separators_and_deduplicates():
    assert parse_opt_in_ids('10\n20, 30;20 40') == [10, 20, 30, 40]


def test_parse_opt_in_ids_rejects_invalid_values():
    try:
        parse_opt_in_ids('10, abc')
    except ValueError as exc:
        assert 'ID inválido' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError para ID inválido.')


def test_render_invite_message_replaces_supported_placeholders():
    user = FakeUser(10, first_name='Ana')
    text = render_invite_message(
        'Olá {name}. Entre em {destination}: {link}',
        user,
        'Grupo Beta',
        'https://t.me/+teste',
    )
    assert text == 'Olá Ana. Entre em Grupo Beta: https://t.me/+teste'


def test_dry_run_never_sends_message():
    client = FakeClient()
    user = FakeUser(10, first_name='Ana')
    rows = []

    def report(*args):
        rows.append(args)

    engine = MessageInviteEngine(client, min_delay=0, max_delay=0)
    stats = asyncio.run(
        engine.run(
            [user],
            report,
            'Olá {name}: {link}',
            'Grupo Beta',
            '[LINK_DO_GRUPO_B]',
            limit=1,
            dry_run=True,
        )
    )

    assert stats.processed == 1
    assert stats.sent == 0
    assert client.sent == []
    assert rows[0][3] == 'message_dry_run'


def test_real_run_sends_only_selected_batch():
    client = FakeClient()
    users = [FakeUser(1, 'Ana'), FakeUser(2, 'Bia')]
    rows = []

    def report(*args):
        rows.append(args)

    engine = MessageInviteEngine(client, min_delay=0, max_delay=0)
    stats = asyncio.run(
        engine.run(
            users,
            report,
            'Olá {name}: {link}',
            'Grupo Beta',
            'https://t.me/+teste',
            limit=1,
            dry_run=False,
        )
    )

    assert stats.processed == 1
    assert stats.sent == 1
    assert client.sent == [(1, 'Olá Ana: https://t.me/+teste')]
    assert rows[0][3] == 'message_sent'
