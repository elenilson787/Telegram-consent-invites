import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _env_first(*names: str, default: str = '') -> str:
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return default


def normalize_phone(phone: str, default_country_code: str | None = None) -> str:
    """Normaliza telefone para E.164 antes de chamar a API do Telegram.

    A instalação brasileira usa ``55`` como DDI padrão. Assim entradas como
    ``(93) 99999-9999`` ou ``93999999999`` viram ``+5593999999999``. Números
    já informados com ``+`` ou ``00`` preservam o DDI explícito.
    """
    raw = str(phone or '').strip()
    if not raw:
        raise ValueError('Informe o número do Telegram com DDI ou DDD + número.')

    explicit_international = raw.startswith('+') or raw.startswith('00')
    digits = re.sub(r'\D+', '', raw)
    if raw.startswith('00') and digits.startswith('00'):
        digits = digits[2:]

    if not digits:
        raise ValueError('O telefone deve conter números.')

    default_country_code = (
        str(
            default_country_code
            or _env_first(
                'TELEGRAM_EXTRACTOR_DEFAULT_COUNTRY_CODE',
                'AFILIAPULSE_DEFAULT_COUNTRY_CODE',
                default='55',
            )
        )
        .strip()
        .lstrip('+')
    )
    if not default_country_code.isdigit():
        default_country_code = '55'

    if explicit_international:
        normalized_digits = digits
    elif digits.startswith(default_country_code) and len(digits) in {12, 13}:
        normalized_digits = digits
    elif len(digits) in {10, 11}:
        normalized_digits = default_country_code + digits
    else:
        # Permite outros países quando o usuário informou o DDI sem o sinal +.
        normalized_digits = digits

    if not 8 <= len(normalized_digits) <= 15:
        raise ValueError(
            'Número inválido. Informe DDI + DDD + número, por exemplo +55 93 99999-9999.'
        )

    if normalized_digits.startswith('55') and len(normalized_digits) not in {12, 13}:
        raise ValueError(
            'Número brasileiro inválido. Use DDD + telefone, por exemplo (93) 99999-9999.'
        )

    return '+' + normalized_digits


def mask_phone(phone: str) -> str:
    digits = re.sub(r'\D+', '', str(phone or ''))
    if not digits:
        return ''
    if len(digits) <= 4:
        return '*' * max(0, len(digits) - 2) + digits[-2:]
    return f'+{digits[:2]} •••• {digits[-4:]}'


@dataclass
class TelegramAccountProfile:
    id: str
    label: str
    session_path: str
    state_path: str
    status: str = 'offline'
    telegram_user_id: int | None = None
    username: str = ''
    display_name: str = ''
    phone_masked: str = ''
    last_error: str = ''
    cooldown_until: str = ''
    created_at: str = ''
    updated_at: str = ''

    @classmethod
    def from_dict(cls, raw: dict):
        allowed = {field.name for field in fields(cls)}
        payload = {key: value for key, value in dict(raw or {}).items() if key in allowed}
        return cls(**payload)


class AccountProfileStore:
    """Registro local das contas Telegram conectadas ao agente desktop.

    O arquivo guarda apenas metadados. A autenticação real permanece nos arquivos
    ``.session`` separados de cada perfil.
    """

    def __init__(self, path='data/telegram_accounts.json'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _empty(self):
        return {'active_account_id': '', 'accounts': []}

    def _load(self):
        if not self.path.exists():
            return self._empty()
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return self._empty()
        if not isinstance(raw, dict):
            return self._empty()
        raw.setdefault('active_account_id', '')
        raw.setdefault('accounts', [])
        return raw

    def _save(self):
        temp = self.path.with_suffix(self.path.suffix + '.tmp')
        temp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        temp.replace(self.path)

    def list(self) -> list[TelegramAccountProfile]:
        profiles = [TelegramAccountProfile.from_dict(item) for item in self._data['accounts']]
        return sorted(profiles, key=lambda profile: (profile.label or profile.id).lower())

    def get(self, account_id: str) -> TelegramAccountProfile | None:
        for profile in self.list():
            if profile.id == account_id:
                return profile
        return None

    def find_by_telegram_user_id(
        self,
        telegram_user_id: int | None,
        exclude_account_id: str | None = None,
    ) -> TelegramAccountProfile | None:
        if not telegram_user_id:
            return None
        target = int(telegram_user_id)
        for profile in self.list():
            if exclude_account_id and profile.id == exclude_account_id:
                continue
            if profile.telegram_user_id and int(profile.telegram_user_id) == target:
                return profile
        return None

    def active(self) -> TelegramAccountProfile | None:
        account_id = str(self._data.get('active_account_id') or '')
        return self.get(account_id) if account_id else None

    def set_active(self, account_id: str):
        if self.get(account_id) is None:
            raise KeyError(f'Conta Telegram não encontrada: {account_id}')
        self._data['active_account_id'] = account_id
        self._save()

    def max_accounts(self) -> int:
        """Limite provisório até a política vir do SaaS/licença."""
        raw = _env_first(
            'TELEGRAM_EXTRACTOR_MAX_ACCOUNTS',
            'AFILIAPULSE_MAX_TELEGRAM_ACCOUNTS',
            default='3',
        )
        try:
            value = int(raw)
        except ValueError:
            value = 3
        return max(1, min(value, 50))

    def create_pending(self, label: str) -> TelegramAccountProfile:
        if len(self.list()) >= self.max_accounts():
            raise ValueError(
                f'O plano atual permite até {self.max_accounts()} conta(s) Telegram.'
            )
        label = str(label or '').strip() or 'Conta Telegram'
        account_id = secrets.token_hex(5)
        created = now_iso()
        profile = TelegramAccountProfile(
            id=account_id,
            label=label,
            session_path=f'sessions/accounts/{account_id}/telegram',
            state_path=f'data/accounts/{account_id}/state.sqlite3',
            status='onboarding',
            created_at=created,
            updated_at=created,
        )
        Path(profile.session_path).parent.mkdir(parents=True, exist_ok=True)
        Path(profile.state_path).parent.mkdir(parents=True, exist_ok=True)
        self._data['accounts'].append(asdict(profile))
        if not self._data.get('active_account_id'):
            self._data['active_account_id'] = profile.id
        self._save()
        return profile

    def update(self, account_id: str, **changes) -> TelegramAccountProfile:
        for index, raw in enumerate(self._data['accounts']):
            if raw.get('id') != account_id:
                continue
            raw = dict(raw)
            raw.update(changes)
            raw['updated_at'] = now_iso()
            profile = TelegramAccountProfile.from_dict(raw)
            self._data['accounts'][index] = asdict(profile)
            self._save()
            return profile
        raise KeyError(f'Conta Telegram não encontrada: {account_id}')

    def remove(self, account_id: str):
        self._data['accounts'] = [
            raw for raw in self._data['accounts'] if raw.get('id') != account_id
        ]
        if self._data.get('active_account_id') == account_id:
            self._data['active_account_id'] = (
                self._data['accounts'][0]['id'] if self._data['accounts'] else ''
            )
        self._save()

    def ensure_legacy(self, session_path: str, state_path='data/local_state.sqlite3'):
        """Importa a sessão V12 existente sem mover arquivos nem perder histórico."""
        if self.list():
            return self.active()
        session_file = Path(str(session_path) + '.session')
        if not session_file.exists():
            return None
        created = now_iso()
        profile = TelegramAccountProfile(
            id='legacy-main',
            label='Conta principal',
            session_path=str(session_path),
            state_path=str(state_path),
            status='offline',
            created_at=created,
            updated_at=created,
        )
        self._data['accounts'] = [asdict(profile)]
        self._data['active_account_id'] = profile.id
        self._save()
        return profile
