import asyncio
from datetime import datetime, timedelta, timezone

from telethon import functions
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    PeerFloodError,
    UserAlreadyParticipantError,
    UserChannelsTooMuchError,
    UserKickedError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError,
)
from telethon.tl.types import Chat

from models import MigrationStats
from utils import full_name, random_delay


def classify_candidates(users, destination_ids, source_admin_ids, excluded_user_ids):
    """Separa usuários em categorias mutuamente exclusivas antes do convite."""
    destination_ids = set(destination_ids)
    source_admin_ids = set(source_admin_ids)
    excluded_user_ids = set(excluded_user_ids)

    admins = []
    bots = []
    excluded = []
    already_members = []
    eligible = []

    for user in users:
        if user.id in source_admin_ids:
            admins.append(user)
        elif getattr(user, 'bot', False):
            bots.append(user)
        elif user.id in excluded_user_ids:
            excluded.append(user)
        elif user.id in destination_ids:
            already_members.append(user)
        else:
            eligible.append(user)

    return admins, bots, excluded, already_members, eligible


def select_explicit_targets(eligible_users, target_user_ids):
    """Restringe a execução aos IDs explicitamente selecionados.

    Se nenhum alvo for informado, preserva a lista recebida (útil no DRY RUN geral).
    Retorna também qualquer ID solicitado que não esteja elegível, permitindo que o
    chamador falhe de forma segura em vez de substituir o alvo por outra pessoa.
    """
    users = list(eligible_users)
    target_ids = set(target_user_ids)
    if not target_ids:
        return users, set()

    eligible_by_id = {user.id: user for user in users}
    missing = target_ids - set(eligible_by_id)
    selected = [user for user in users if user.id in target_ids]
    return selected, missing


class MigrationEngine:
    def __init__(self, client, destination, max_invites=5, min_delay=15, max_delay=30):
        self.client = client
        self.destination = destination
        self.max_invites = max_invites
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def invite_one(self, user):
        if isinstance(self.destination, Chat):
            await self.client(functions.messages.AddChatUserRequest(
                chat_id=self.destination.id,
                user_id=user,
                fwd_limit=0,
            ))
            return

        await self.client(functions.channels.InviteToChannelRequest(
            channel=self.destination,
            users=[user],
        ))

    async def run(self, users, report, dry_run=False):
        stats = MigrationStats()
        candidates = [u for u in users if not getattr(u, 'bot', False)]
        batch = candidates[:self.max_invites]

        if dry_run:
            for user in batch:
                report.write(
                    user.id,
                    getattr(user, 'username', None),
                    full_name(user),
                    'dry_run',
                    'Nenhuma operação enviada.',
                )
            stats.processed = len(batch)
            return stats

        for index, user in enumerate(batch):
            stats.processed += 1
            name = full_name(user)
            username = getattr(user, 'username', None)

            try:
                await self.invite_one(user)
                stats.added += 1
                report.write(user.id, username, name, 'added', 'Convite aceito pela API.')
            except UserAlreadyParticipantError:
                stats.already_member += 1
                report.write(user.id, username, name, 'already_member', 'Já é membro.')
            except UserPrivacyRestrictedError as exc:
                stats.privacy += 1
                report.write(user.id, username, name, 'privacy', str(exc))
            except UserNotMutualContactError as exc:
                stats.privacy += 1
                report.write(user.id, username, name, 'not_mutual_contact', str(exc))
            except UserChannelsTooMuchError as exc:
                stats.skipped += 1
                report.write(user.id, username, name, 'user_limit', str(exc))
            except UserKickedError as exc:
                stats.skipped += 1
                report.write(user.id, username, name, 'kicked', str(exc))
            except ChatAdminRequiredError as exc:
                stats.permissions += 1
                report.write(user.id, username, name, 'permission_error', str(exc))
                stats.stopped = True
                break
            except FloodWaitError as exc:
                stats.rate_limited += 1
                seconds = int(getattr(exc, 'seconds', 0) or 0)
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
                report.write(
                    user.id,
                    username,
                    name,
                    'flood_wait',
                    f'Telegram determinou espera de {seconds}s. Não retomar antes de {retry_at.isoformat()}.',
                )
                stats.stopped = True
                break
            except PeerFloodError as exc:
                stats.rate_limited += 1
                report.write(user.id, username, name, 'peer_flood', str(exc))
                stats.stopped = True
                break
            except Exception as exc:
                stats.errors += 1
                report.write(user.id, username, name, 'error', f'{type(exc).__name__}: {exc}')

            if index < len(batch) - 1:
                await asyncio.sleep(random_delay(self.min_delay, self.max_delay))

        if len(candidates) > self.max_invites:
            stats.stopped = True

        return stats
