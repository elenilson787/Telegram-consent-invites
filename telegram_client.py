from dataclasses import dataclass
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User


@dataclass
class ChatInfo:
    entity: object
    title: str
    chat_type: str
    id: int
    username: str | None


class TelegramService:
    def __init__(self, api_id: int, api_hash: str, session: str):
        self.client = TelegramClient(session, api_id, api_hash)

    async def connect(self):
        await self.client.start()
        if not await self.client.is_user_authorized():
            raise RuntimeError('A conta não foi autorizada.')
        return await self.client.get_me()

    async def disconnect(self):
        await self.client.disconnect()

    async def list_dialogs(self) -> list[ChatInfo]:
        result = []
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, (Channel, Chat)):
                continue
            result.append(ChatInfo(
                entity=entity,
                title=getattr(entity, 'title', None) or dialog.name or str(dialog.id),
                chat_type='canal/supergrupo' if isinstance(entity, Channel) else 'grupo',
                id=dialog.id,
                username=getattr(entity, 'username', None),
            ))
        return sorted(result, key=lambda x: x.title.lower())

    async def get_members(self, entity):
        members = []
        async for user in self.client.iter_participants(entity):
            if isinstance(user, User):
                members.append(user)
        return members

    async def get_member_ids(self, entity) -> set[int]:
        ids = set()
        async for user in self.client.iter_participants(entity):
            if isinstance(user, User):
                ids.add(user.id)
        return ids
