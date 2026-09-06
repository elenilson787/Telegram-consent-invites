import asyncio
from telethon import functions
from telethon.errors import (
    ChatAdminRequiredError, FloodWaitError, PeerFloodError,
    UserAlreadyParticipantError, UserChannelsTooMuchError,
    UserKickedError, UserNotMutualContactError, UserPrivacyRestrictedError,
)
from models import MigrationStats
from utils import full_name, random_delay


class MigrationEngine:
    def __init__(self, client, destination, max_invites=50, min_delay=15, max_delay=30):
        self.client = client
        self.destination = destination
        self.max_invites = max_invites
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def invite_one(self, user):
        await self.client(functions.channels.InviteToChannelRequest(
            channel=self.destination,
            users=[user],
        ))

    async def run(self, users, report, dry_run=False):
        stats = MigrationStats()
        users = [u for u in users if not getattr(u, 'bot', False)]
        existing = set()
        try:
            async for member in self.client.iter_participants(self.destination):
                existing.add(member.id)
        except Exception:
            pass
        candidates = [u for u in users if u.id not in existing]

        if dry_run:
            for u in candidates[:self.max_invites]:
                report.write(u.id, getattr(u, 'username', None), full_name(u), 'dry_run', 'Nenhuma operação enviada.')
            stats.skipped = min(len(candidates), self.max_invites)
            return stats

        for user in candidates:
            if stats.processed >= self.max_invites:
                stats.stopped = True
                break
            stats.processed += 1
            name, username = full_name(user), getattr(user, 'username', None)
            try:
                await self.invite_one(user)
                stats.added += 1
                report.write(user.id, username, name, 'added', 'Convite aceito pela API.')
            except UserAlreadyParticipantError:
                stats.already_member += 1
                report.write(user.id, username, name, 'already_member', 'Já é membro.')
            except (UserPrivacyRestrictedError, UserNotMutualContactError) as exc:
                stats.privacy += 1
                report.write(user.id, username, name, 'privacy', str(exc))
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
                report.write(user.id, username, name, 'flood_wait', f'Telegram determinou espera de {seconds}s.')
                await asyncio.sleep(seconds)
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

            if stats.processed < min(len(candidates), self.max_invites):
                await asyncio.sleep(random_delay(self.min_delay, self.max_delay))
        return stats
