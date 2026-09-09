"""Cliente mínimo do backend SaaS do Telegram Extractor.

Usa somente a publishable key do Supabase no desktop. Nenhuma chave service-role
ou segredo administrativo é distribuído ao cliente. O refresh token é guardado,
quando possível, no cofre de credenciais do sistema operacional via ``keyring``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import keyring
except Exception:  # pragma: no cover - fallback para ambientes sem backend keyring
    keyring = None


DEFAULT_SUPABASE_URL = 'https://elxzvlbqsodsgygopsxw.supabase.co'
DEFAULT_SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_eOli3lp_qZ9NJhuHkk4sew_eeFRUnuo'
KEYRING_SERVICE = 'Telegram Extractor'
KEYRING_REFRESH_TOKEN = 'supabase_refresh_token'


class SaaSAuthError(RuntimeError):
    pass


@dataclass
class SaaSSession:
    access_token: str
    refresh_token: str
    user_id: str
    email: str


@dataclass
class Entitlements:
    user_id: str
    plan_id: str | None
    plan_name: str
    subscription_status: str
    entitled: bool
    max_telegram_accounts: int
    daily_direct_cap: int
    daily_message_cap: int
    history_days: int
    current_period_start: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> 'Entitlements':
        return cls(
            user_id=str(raw.get('user_id') or ''),
            plan_id=raw.get('plan_id'),
            plan_name=str(raw.get('plan_name') or 'Sem assinatura'),
            subscription_status=str(raw.get('subscription_status') or 'none'),
            entitled=bool(raw.get('entitled')),
            max_telegram_accounts=max(0, int(raw.get('max_telegram_accounts') or 0)),
            daily_direct_cap=max(0, int(raw.get('daily_direct_cap') or 0)),
            daily_message_cap=max(0, int(raw.get('daily_message_cap') or 0)),
            history_days=max(0, int(raw.get('history_days') or 0)),
            current_period_start=raw.get('current_period_start'),
            current_period_end=raw.get('current_period_end'),
            cancel_at_period_end=bool(raw.get('cancel_at_period_end')),
        )


class SaaSAuthClient:
    def __init__(self, url: str | None = None, publishable_key: str | None = None):
        self.url = (
            url
            or os.getenv('TELEGRAM_EXTRACTOR_SUPABASE_URL', '').strip()
            or DEFAULT_SUPABASE_URL
        ).rstrip('/')
        self.publishable_key = (
            publishable_key
            or os.getenv('TELEGRAM_EXTRACTOR_SUPABASE_PUBLISHABLE_KEY', '').strip()
            or DEFAULT_SUPABASE_PUBLISHABLE_KEY
        )
        self.session: SaaSSession | None = None

    # ---------------------------------------------------------------
    # HTTP
    # ---------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        headers = {
            'apikey': self.publishable_key,
            'Accept': 'application/json',
        }
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'

        request = Request(
            self.url + path,
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode('utf-8')
                if not raw:
                    return {}
                return json.loads(raw)
        except HTTPError as exc:
            try:
                raw = exc.read().decode('utf-8')
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {}
            message = (
                data.get('msg')
                or data.get('message')
                or data.get('error_description')
                or data.get('error')
                or f'HTTP {exc.code}'
            )
            raise SaaSAuthError(str(message)) from exc
        except URLError as exc:
            raise SaaSAuthError(f'Não foi possível acessar o servidor: {exc.reason}') from exc
        except TimeoutError as exc:
            raise SaaSAuthError('O servidor demorou demais para responder.') from exc

    # ---------------------------------------------------------------
    # Sessão
    # ---------------------------------------------------------------
    def _save_refresh_token(self, token: str):
        if not token or keyring is None:
            return
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN, token)
        except Exception:
            # Sem armazenamento persistente é melhor pedir login novamente do que
            # gravar token sensível em texto puro.
            pass

    def _load_refresh_token(self) -> str:
        if keyring is None:
            return ''
        try:
            return keyring.get_password(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN) or ''
        except Exception:
            return ''

    def _delete_refresh_token(self):
        if keyring is None:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN)
        except Exception:
            pass

    def _consume_auth_response(self, data: dict[str, Any]) -> SaaSSession | None:
        access_token = str(data.get('access_token') or '')
        refresh_token = str(data.get('refresh_token') or '')
        user = data.get('user') or {}
        user_id = str(user.get('id') or '')
        email = str(user.get('email') or '')
        if not access_token or not refresh_token or not user_id:
            return None
        self.session = SaaSSession(access_token, refresh_token, user_id, email)
        self._save_refresh_token(refresh_token)
        return self.session

    def sign_in(self, email: str, password: str) -> SaaSSession:
        email = str(email or '').strip().lower()
        password = str(password or '')
        if not email or '@' not in email:
            raise SaaSAuthError('Informe um e-mail válido.')
        if not password:
            raise SaaSAuthError('Informe sua senha.')
        data = self._request(
            'POST',
            '/auth/v1/token?grant_type=password',
            {'email': email, 'password': password},
        )
        session = self._consume_auth_response(data)
        if session is None:
            raise SaaSAuthError('O servidor não retornou uma sessão válida.')
        return session

    def sign_up(self, email: str, password: str, display_name: str = '') -> dict[str, Any]:
        email = str(email or '').strip().lower()
        password = str(password or '')
        if not email or '@' not in email:
            raise SaaSAuthError('Informe um e-mail válido.')
        if len(password) < 6:
            raise SaaSAuthError('Use uma senha com pelo menos 6 caracteres.')
        payload: dict[str, Any] = {'email': email, 'password': password}
        if display_name.strip():
            payload['data'] = {'display_name': display_name.strip()}
        data = self._request('POST', '/auth/v1/signup', payload)
        self._consume_auth_response(data)
        return data

    def refresh(self, refresh_token: str | None = None) -> SaaSSession:
        token = refresh_token or (self.session.refresh_token if self.session else '') or self._load_refresh_token()
        if not token:
            raise SaaSAuthError('Nenhuma sessão salva foi encontrada.')
        data = self._request(
            'POST',
            '/auth/v1/token?grant_type=refresh_token',
            {'refresh_token': token},
        )
        session = self._consume_auth_response(data)
        if session is None:
            self._delete_refresh_token()
            raise SaaSAuthError('A sessão salva expirou. Entre novamente.')
        return session

    def restore(self) -> SaaSSession | None:
        token = self._load_refresh_token()
        if not token:
            return None
        try:
            return self.refresh(token)
        except SaaSAuthError:
            self._delete_refresh_token()
            self.session = None
            return None

    def fetch_entitlements(self) -> Entitlements:
        if self.session is None:
            raise SaaSAuthError('Faça login para validar a assinatura.')
        try:
            data = self._request(
                'POST',
                '/rest/v1/rpc/telegram_extractor_my_entitlements',
                {},
                self.session.access_token,
            )
        except SaaSAuthError as first_error:
            # Access tokens expiram rapidamente; uma renovação silenciosa evita
            # pedir senha de novo durante uso normal do agente.
            try:
                self.refresh()
            except SaaSAuthError:
                raise first_error
            data = self._request(
                'POST',
                '/rest/v1/rpc/telegram_extractor_my_entitlements',
                {},
                self.session.access_token,
            )
        if not isinstance(data, dict):
            raise SaaSAuthError('Resposta de assinatura inválida.')
        return Entitlements.from_dict(data)

    def sign_out(self):
        if self.session is not None:
            try:
                self._request('POST', '/auth/v1/logout', {}, self.session.access_token)
            except Exception:
                pass
        self.session = None
        self._delete_refresh_token()
