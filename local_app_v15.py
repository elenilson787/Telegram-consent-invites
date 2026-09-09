"""V15: correções de onboarding e duplicidade de contas Telegram.

- Normaliza telefones brasileiros antes de chamar a API.
- Impede cadastrar duas sessões para o mesmo telegram_user_id.
- Só exibe "Ativar conta" depois de autenticação concluída.
"""

from tkinter import messagebox, simpledialog

import customtkinter as ctk

from account_profiles import mask_phone, normalize_phone
from local_app_v14 import LocalAppV14
from telegram_client import TelegramService


class LocalAppV15(LocalAppV14):
    """V14 com onboarding corrigido para uso comercial."""

    def _begin_profile_login(self, profile):
        if not self._telegram_app_ready():
            self._show_provisioning_notice()
            return

        phone = simpledialog.askstring(
            'Conectar Telegram · telefone',
            'Informe o telefone. Para Brasil você pode usar:\n'
            '(93) 99999-9999, 93999999999 ou +55 93 99999-9999',
            parent=self,
        )
        if phone is None:
            return

        try:
            normalized_phone = normalize_phone(phone)
        except ValueError as exc:
            messagebox.showwarning('Conectar Telegram', str(exc))
            return

        service = TelegramService(
            self.settings.api_id,
            self.settings.api_hash,
            profile.session_path,
        )
        self._login_services[profile.id] = service
        self.account_profiles.update(
            profile.id,
            status='onboarding',
            phone_masked=mask_phone(normalized_phone),
            last_error='',
        )
        self._refresh_accounts_tab()
        self._submit(
            service.begin_login(normalized_phone),
            lambda future, account_id=profile.id: self._after_begin_login(account_id, future),
        )

    def _finish_login(self, account_id, user):
        """Finaliza somente se a identidade Telegram ainda não estiver cadastrada."""
        duplicate = self.account_profiles.find_by_telegram_user_id(
            int(user.id),
            exclude_account_id=account_id,
        )
        if duplicate is not None:
            service = self._login_services.pop(account_id, None)
            self.account_profiles.remove(account_id)
            self._refresh_accounts_tab()

            if service is not None:
                self._submit(
                    self._close_duplicate_session(service),
                    lambda _future: None,
                )

            existing_name = duplicate.display_name or duplicate.label
            existing_username = f'@{duplicate.username}' if duplicate.username else 'sem username'
            messagebox.showwarning(
                'Conta Telegram já cadastrada',
                'Esta conta Telegram já está cadastrada no AFILIAPULSE.\n\n'
                f'Conta existente: {existing_name} · {existing_username}\n\n'
                'A tentativa duplicada foi descartada e não ocupa um novo slot do plano.',
            )
            return

        super()._finish_login(account_id, user)

    @staticmethod
    async def _close_duplicate_session(service):
        """Encerra apenas a nova sessão duplicada criada durante o teste."""
        try:
            await service.logout()
        except Exception:
            try:
                await service.disconnect()
            except Exception:
                pass

    def _render_account_card(self, row, profile):
        """Renderiza ações coerentes com o estado real de autenticação."""
        active = profile.id == self.active_account_id
        icon, status_text, status_color = self._account_status_style(profile)

        card = ctk.CTkFrame(
            self.accounts_frame,
            corner_radius=12,
            border_width=1,
            border_color='#22d3ee' if active else '#334155',
        )
        card.grid(row=row, column=0, sticky='ew', padx=5, pady=5)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text='ATIVA' if active else 'CONTA',
            width=75,
            text_color='#22d3ee' if active else '#94a3b8',
            font=ctk.CTkFont(size=11, weight='bold'),
        ).grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12)

        identity = profile.display_name or profile.label
        username = f'@{profile.username}' if profile.username else 'sem username salvo'
        ctk.CTkLabel(
            card,
            text=f'{identity}  ·  {username}',
            font=ctk.CTkFont(size=15, weight='bold'),
        ).grid(row=0, column=1, sticky='w', padx=6, pady=(10, 1))
        ctk.CTkLabel(
            card,
            text=f'{icon} {status_text}  ·  {profile.phone_masked or "telefone não armazenado"}',
            text_color=status_color,
        ).grid(row=1, column=1, sticky='w', padx=6, pady=1)

        detail = profile.last_error or (
            f'Cooldown até {profile.cooldown_until}' if profile.cooldown_until else
            f'Sessão local isolada: {profile.session_path}'
        )
        ctk.CTkLabel(
            card,
            text=detail,
            text_color=('gray45', 'gray65'),
            wraplength=760,
            justify='left',
        ).grid(row=2, column=1, sticky='w', padx=6, pady=(1, 10))

        buttons = ctk.CTkFrame(card, fg_color='transparent')
        buttons.grid(row=0, column=2, rowspan=3, padx=12, pady=10)

        authentication_pending = profile.status in {'onboarding', 'reauth', 'error'}
        authenticated = bool(profile.telegram_user_id)

        if authentication_pending:
            ctk.CTkButton(
                buttons,
                text='Autenticar',
                width=112,
                command=lambda p=profile: self._begin_profile_login(p),
            ).pack(pady=3)

        # Nunca permite ativar um perfil que ainda não concluiu autenticação.
        if not active and authenticated and not authentication_pending:
            ctk.CTkButton(
                buttons,
                text='Ativar conta',
                width=112,
                command=lambda p=profile: self._activate_account(p),
            ).pack(pady=3)

        if profile.status == 'peer_flood':
            ctk.CTkButton(
                buttons,
                text='Revisar pausa',
                width=112,
                fg_color='#92400e',
                hover_color='#78350f',
                command=lambda p=profile: self._review_peer_flood(p),
            ).pack(pady=3)

    def _account_status_style(self, profile):
        # Usa o mesmo mapa de status da V13 sem importar detalhes internos da UI.
        from local_app_v13 import STATUS_LABELS

        return STATUS_LABELS.get(
            profile.status,
            ('⚪', profile.status or 'Offline', '#94a3b8'),
        )


if __name__ == '__main__':
    app = LocalAppV15()
    app.mainloop()
