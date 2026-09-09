from dataclasses import dataclass

from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    Channel,
    ChannelParticipantsAdmins,
    Chat,
    ChatParticipantAdmin,
    ChatParticipantCreator,
    User,
)


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
        self._pending_phone: str | None = None
        self._pending_phone_code_hash: str | None = None

    async def connect(self):
        """Conecta uma sessão que já foi autorizada.

        Diferente de ``client.start()``, este método nunca abre prompt no terminal.
        Isso permite que o onboarding seja inteiramente controlado pela GUI.
        """
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError('Esta sessão ainda precisa ser autenticada.')
        return await self.client.get_me()

    async def begin_login(self, phone: str):
        """Inicia login enviando o código para o número informado."""
        phone = str(phone or '').strip()
        if not phone:
            raise ValueError('Informe o número do Telegram com DDI.')
        await self.client.connect()
        if await self.client.is_user_authorized():
            return {'already_authorized': True, 'user': await self.client.get_me()}

        sent = await self.client.send_code_request(phone)
        self._pending_phone = phone
        self._pending_phone_code_hash = getattr(sent, 'phone_code_hash', None)
        return {'already_authorized': False, 'type': getattr(sent, 'type', None)}

    async def complete_login_code(self, code: str):
        """Confirma o código. Retorna ``needs_password`` quando há 2FA."""
        if not self._pending_phone:
            raise RuntimeError('Nenhum login foi iniciado para esta sessão.')
        code = str(code or '').strip().replace(' ', '')
        if not code:
            raise ValueError('Informe o código recebido no Telegram.')
        try:
            user = await self.client.sign_in(
                phone=self._pending_phone,
                code=code,
                phone_code_hash=self._pending_phone_code_hash,
            )
        except SessionPasswordNeededError:
            return {'needs_password': True, 'user': None}
        return {'needs_password': False, 'user': user or await self.client.get_me()}

    async def complete_login_password(self, password: str):
        """Finaliza autenticação de contas com verificação em duas etapas."""
        password = str(password or '')
        if not password:
            raise ValueError('Informe a senha de verificação em duas etapas.')
        user = await self.client.sign_in(password=password)
        return user or await self.client.get_me()

    async def logout(self):
        """Encerra a sessão Telegram atualmente conectada."""
        if not self.client.is_connected():
            await self.client.connect()
        await self.client.log_out()

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

    async def get_admin_ids(self, entity) -> set[int]:
        """Retorna IDs de administradores/owner visíveis pela API do Telegram."""
        if isinstance(entity, Channel):
            ids: set[int] = set()
            async for user in self.client.iter_participants(
                entity,
                filter=ChannelParticipantsAdmins(),
            ):
                if isinstance(user, User):
                    ids.add(user.id)
            return ids

        if isinstance(entity, Chat):
            result = await self.client(
                functions.messages.GetFullChatRequest(chat_id=entity.id)
            )
            participants = getattr(
                getattr(result.full_chat, 'participants', None),
                'participants',
                [],
            )
            return {
                participant.user_id
                for participant in participants
                if isinstance(
                    participant,
                    (ChatParticipantAdmin, ChatParticipantCreator),
                )
            }

        raise TypeError('Tipo de grupo não suportado para identificar administradores.')

    async def export_invite_link(self, entity) -> str:
        result = await self.client(
            functions.messages.ExportChatInviteRequest(peer=entity)
        )
        link = getattr(result, 'link', None)
        if not link:
            raise RuntimeError('O Telegram não retornou um link de convite.')
        return link
