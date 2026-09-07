import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    UserIdInvalidError,
    UserPrivacyRestrictedError,
)

from utils import full_name, random_delay


@dataclass
class MessageInviteStats:
    processed: int = 0
    sent: int = 0
    privacy: int = 0
    skipped: int = 0
    rate_limited: int = 0
    errors: int = 0
    stopped: bool = False


def parse_opt_in_ids(text: str) -> list[int]:
    """Lê IDs explícitos separados por espaço, vírgula, ponto e vírgula ou linha."""
    raw = (text or '').strip()
    if not raw:
        return []

    ids: list[int] = []
    seen: set[int] = set()
    for token in re.split(r'[\s,;]+', raw):
        if not token:
            continue
        try:
            user_id = int(token)
        except ValueError as exc:
            raise ValueError(f'ID inválido na lista de opt-in: {token!r}.') from exc
        if user_id <= 0:
            raise ValueError('Todos os IDs de opt-in devem ser positivos.')
        if user_id not in seen:
            seen.add(user_id)
            ids.append(user_id)
    return ids


def render_invite_message(template: str, user, destination_title: str, invite_link: str) -> str:
    """Renderiza apenas placeholders explícitos e previsíveis."""
    text = (template or '').strip()
    if not text:
        raise ValueError('A mensagem de convite não pode ficar vazia.')

    return (
        text.replace('{name}', full_name(user))
        .replace('{destination}', destination_title or '')
        .replace('{link}', invite_link or '')
    )


class MessageInviteEngine:
    """Envia convites por mensagem somente para a lista explícita recebida."""

    def __init__(self, client, min_delay=30.0, max_delay=60.0):
        self.client = client
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)

    async def run(
        self,
        users,
        report,
        template: str,
        destination_title: str,
        invite_link: str,
        limit: int,
        dry_run: bool = False,
    ) -> MessageInviteStats:
        stats = MessageInviteStats()
        batch = list(users)[: max(0, int(limit))]

        for index, user in enumerate(batch):
            stats.processed += 1
            user_id = int(user.id)
            username = getattr(user, 'username', None)
            name = full_name(user)
            message = render_invite_message(template, user, destination_title, invite_link)

            if dry_run:
                report(
                    user_id,
                    username,
                    name,
                    'message_dry_run',
                    'Simulação: nenhuma mensagem foi enviada.',
                )
                continue

            try:
                await self.client.send_message(user, message)
                stats.sent += 1
                report(
                    user_id,
                    username,
                    name,
                    'message_sent',
                    'Mensagem de convite enviada.',
                )
            except UserPrivacyRestrictedError as exc:
                stats.privacy += 1
                report(user_id, username, name, 'message_privacy', str(exc))
            except UserIdInvalidError as exc:
                stats.skipped += 1
                report(
                    user_id,
                    username,
                    name,
                    'message_invalid_user',
                    f'Usuário não aceito pela API para mensagem: {exc}',
                )
            except FloodWaitError as exc:
                stats.rate_limited += 1
                seconds = int(getattr(exc, 'seconds', 0) or 0)
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
                report(
                    user_id,
                    username,
                    name,
                    'message_flood_wait',
                    f'Telegram determinou espera de {seconds}s. Não retomar antes de {retry_at.isoformat()}.',
                )
                stats.stopped = True
                break
            except PeerFloodError as exc:
                stats.rate_limited += 1
                report(user_id, username, name, 'message_peer_flood', str(exc))
                stats.stopped = True
                break
            except Exception as exc:
                stats.errors += 1
                report(
                    user_id,
                    username,
                    name,
                    'message_error',
                    f'{type(exc).__name__}: {exc}',
                )

            if index < len(batch) - 1 and not stats.stopped:
                await asyncio.sleep(random_delay(self.min_delay, self.max_delay))

        return stats
