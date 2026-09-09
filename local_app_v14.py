"""V14: endurecimento da base comercial multi-contas.

Preserva restrições por conta durante reconexões e impede tentativas de login
quando as credenciais técnicas do aplicativo Telegram ainda não foram
provisionadas. Essas credenciais nunca são hardcodadas no repositório.
"""

import re
from datetime import datetime
from tkinter import messagebox

from local_app_v13 import LocalAppV13


class LocalAppV14(LocalAppV13):
    """V13 com provisionamento seguro e persistência de restrições."""

    def _telegram_app_ready(self):
        return bool(getattr(self.settings, 'telegram_app_provisioned', False))

    def _show_provisioning_notice(self):
        messagebox.showwarning(
            'Agente Telegram não provisionado',
            'Esta instalação ainda não recebeu as credenciais técnicas do aplicativo Telegram.\n\n'
            'Na versão comercial elas serão entregues ao agente após login/licença do AFILIAPULSE, '
            'sem o cliente precisar conhecer API_ID ou API_HASH.\n\n'
            'Nesta build de desenvolvimento, mantenha TELEGRAM_API_ID e TELEGRAM_API_HASH no .env.',
        )

    def _auto_connect_existing_session(self):
        if not self._telegram_app_ready():
            return
        super()._auto_connect_existing_session()

    def _connect_active_account(self):
        if not self._telegram_app_ready():
            self._show_provisioning_notice()
            self.tabs.set('Contas Telegram')
            return
        super()._connect_active_account()

    def _begin_profile_login(self, profile):
        if not self._telegram_app_ready():
            self._show_provisioning_notice()
            return
        super()._begin_profile_login(profile)

    def _after_connect(self, future):
        """Reconectar não libera PeerFlood/cooldown já persistidos."""
        profile = self._active_profile()
        preserved = None
        if profile is not None and profile.status in {'peer_flood', 'cooldown'}:
            preserved = {
                'status': profile.status,
                'last_error': profile.last_error,
                'cooldown_until': profile.cooldown_until,
            }

        super()._after_connect(future)

        if preserved and profile is not None:
            try:
                future.result()
            except Exception:
                return
            self.account_profiles.update(profile.id, **preserved)
            self._refresh_accounts_tab()

    def _record_rate_limit_from_history(self, message_mode=False):
        """Associa a limitação somente à conta ativa e preserva FloodWait exato."""
        profile = self._active_profile()
        if profile is None:
            return
        rows = (
            self.store.recent_message_history(5)
            if message_mode else
            self.store.recent_history(5)
        )
        for row in rows:
            status = row.get('status', '')
            if status in {'peer_flood', 'message_peer_flood'}:
                self.account_profiles.update(
                    profile.id,
                    status='peer_flood',
                    last_error=(
                        'Telegram recusou novas ações com PEER_FLOOD. '
                        'Operações reais pausadas somente nesta conta.'
                    ),
                    cooldown_until='',
                )
                self._refresh_accounts_tab()
                return

            if status in {'flood_wait', 'message_flood_wait'}:
                reason = row.get('reason') or ''
                match = re.search(r'Não retomar antes de (.+)\.$', reason)
                cooldown = match.group(1).strip() if match else ''
                self.account_profiles.update(
                    profile.id,
                    status='cooldown',
                    last_error='Telegram determinou um período de espera para esta conta.',
                    cooldown_until=cooldown,
                )
                self._refresh_accounts_tab()
                return

    def _on_close(self):
        """Marca conexão normal como offline sem apagar restrições persistidas."""
        profile = self._active_profile()
        if profile is not None and profile.status == 'active':
            self.account_profiles.update(profile.id, status='offline')
        super()._on_close()


if __name__ == '__main__':
    app = LocalAppV14()
    app.mainloop()
