"""V13: base comercial multi-contas para o AFILIAPULSE Telegram Manager.

Cada conta Telegram usa sessão e banco local próprios. O onboarding acontece na
GUI (telefone -> código -> 2FA), sem exigir comandos de terminal. Restrições do
Telegram são registradas por conta e nunca provocam rotação automática para
outra conta.
"""

import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from account_profiles import AccountProfileStore, mask_phone
from local_app_v12 import LocalAppV12
from state_store import StateStore
from telegram_client import TelegramService
from utils import full_name


STATUS_LABELS = {
    'active': ('🟢', 'Ativa', '#22c55e'),
    'offline': ('⚪', 'Offline', '#94a3b8'),
    'onboarding': ('🟡', 'Configuração pendente', '#f59e0b'),
    'reauth': ('🟠', 'Reautenticação necessária', '#f97316'),
    'peer_flood': ('🔴', 'Convites pausados · PeerFlood', '#ef4444'),
    'cooldown': ('🟡', 'Cooldown do Telegram', '#f59e0b'),
    'error': ('🔴', 'Erro de conexão', '#ef4444'),
}


class LocalAppV13(LocalAppV12):
    """V12 com perfis Telegram isolados e onboarding guiado."""

    def __init__(self):
        self.account_profiles = None
        self.active_account_id = None
        self._login_services = {}
        super().__init__()
        if not self.winfo_exists():
            return

        self.account_profiles = AccountProfileStore()
        self.account_profiles.ensure_legacy(self.settings.session)
        active = self.account_profiles.active()
        if active is not None:
            self._apply_account_context(active)

        self._install_accounts_tab()
        self.connect_button.configure(command=self._connect_active_account)
        self._refresh_accounts_tab()
        self._refresh_account_scoped_views()

        if not self.account_profiles.list():
            self.after(450, lambda: self.tabs.set('Contas Telegram'))

    # ------------------------------------------------------------------
    # Contexto por conta
    # ------------------------------------------------------------------
    def _apply_account_context(self, profile):
        self.active_account_id = profile.id
        self.settings = replace(self.settings, session=profile.session_path)
        self.store = StateStore(profile.state_path)
        self.prepared = None
        self.dialogs = []
        self.dialog_map = {}
        self.message_invite_link = ''
        self.message_link_destination_id = None
        if hasattr(self, 'message_link_var'):
            self.message_link_var.set('Nenhum link carregado ainda.')

    def _active_profile(self):
        if self.account_profiles is None:
            return None
        return self.account_profiles.get(self.active_account_id) if self.active_account_id else None

    def _refresh_account_scoped_views(self):
        self._refresh_history()
        self._refresh_exclusions()
        self._refresh_message_history()
        try:
            self._invalidate_prepared('Conta Telegram alterada.', log=False)
        except Exception:
            self.prepared = None

    def _connect_active_account(self):
        profile = self._active_profile()
        if profile is None:
            self.tabs.set('Contas Telegram')
            messagebox.showinfo(
                'Conectar Telegram',
                'Adicione sua própria conta Telegram na aba "Contas Telegram" antes de continuar.',
            )
            return
        self._connect()

    def _after_connect(self, future):
        profile = self._active_profile()
        try:
            user, _dialogs = future.result()
        except Exception as exc:
            if profile is not None and self.account_profiles is not None:
                status = 'reauth' if 'autenticada' in str(exc).lower() else 'error'
                self.account_profiles.update(
                    profile.id,
                    status=status,
                    last_error=f'{type(exc).__name__}: {exc}',
                )
        else:
            if profile is not None and self.account_profiles is not None:
                self.account_profiles.update(
                    profile.id,
                    status='active',
                    telegram_user_id=int(user.id),
                    username=getattr(user, 'username', None) or '',
                    display_name=full_name(user),
                    last_error='',
                    cooldown_until='',
                )
        super()._after_connect(future)
        self._refresh_accounts_tab()

    # ------------------------------------------------------------------
    # Aba Contas Telegram
    # ------------------------------------------------------------------
    def _install_accounts_tab(self):
        self.tabs.add('Contas Telegram')
        tab = self.tabs.tab('Contas Telegram')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        intro = ctk.CTkFrame(tab, corner_radius=12)
        intro.grid(row=0, column=0, sticky='ew', padx=6, pady=(6, 10))
        intro.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            intro,
            text='📱 Suas contas Telegram',
            font=ctk.CTkFont(size=21, weight='bold'),
            text_color='#22d3ee',
        ).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 2))
        ctk.CTkLabel(
            intro,
            text=(
                'Cada conta usa uma sessão, histórico, exclusões e estado próprios. '
                'Código de login e senha 2FA são usados apenas durante a autenticação e não são armazenados.'
            ),
            justify='left',
            wraplength=1050,
            text_color=('gray35', 'gray70'),
        ).grid(row=1, column=0, sticky='w', padx=16, pady=(0, 8))

        self.account_plan_label = ctk.CTkLabel(intro, text='', font=ctk.CTkFont(size=12, weight='bold'))
        self.account_plan_label.grid(row=2, column=0, sticky='w', padx=16, pady=(0, 12))
        self.add_account_button = ctk.CTkButton(
            intro,
            text='+ Adicionar minha conta Telegram',
            command=self._add_account,
            width=250,
            height=34,
            fg_color='#7c3aed',
            hover_color='#6d28d9',
        )
        self.add_account_button.grid(row=0, column=1, rowspan=3, padx=16, pady=16)

        self.accounts_frame = ctk.CTkScrollableFrame(tab)
        self.accounts_frame.grid(row=1, column=0, sticky='nsew', padx=6, pady=(0, 8))
        self.accounts_frame.grid_columnconfigure(0, weight=1)

    def _refresh_accounts_tab(self):
        if not hasattr(self, 'accounts_frame') or self.account_profiles is None:
            return
        for child in self.accounts_frame.winfo_children():
            child.destroy()

        profiles = self.account_profiles.list()
        maximum = self.account_profiles.max_accounts()
        self.account_plan_label.configure(
            text=f'Contas do plano/agente: {len(profiles)} de {maximum}'
        )
        self.add_account_button.configure(state='normal' if len(profiles) < maximum else 'disabled')

        if not profiles:
            self._render_empty_onboarding()
            return

        for row, profile in enumerate(profiles):
            self._render_account_card(row, profile)

    def _render_empty_onboarding(self):
        card = ctk.CTkFrame(self.accounts_frame, corner_radius=14, border_width=1, border_color='#0ea5e9')
        card.grid(row=0, column=0, sticky='ew', padx=6, pady=8)
        ctk.CTkLabel(
            card,
            text='Comece conectando seu próprio Telegram',
            font=ctk.CTkFont(size=20, weight='bold'),
        ).pack(anchor='w', padx=18, pady=(18, 8))
        steps = (
            '1. Clique em “Adicionar minha conta Telegram”.',
            '2. Informe um nome para identificar a conta e seu número com DDI (ex.: +55...).',
            '3. Digite o código que o Telegram enviar para você.',
            '4. Se a conta usar verificação em duas etapas, informe a senha 2FA.',
            '5. Pronto: seus grupos aparecerão apenas dentro dessa conta.',
        )
        for step in steps:
            ctk.CTkLabel(card, text=step, anchor='w', justify='left').pack(
                anchor='w', padx=18, pady=3
            )
        ctk.CTkLabel(
            card,
            text='O AFILIAPULSE não salva o código recebido nem a senha 2FA.',
            text_color='#22c55e',
            font=ctk.CTkFont(size=12, weight='bold'),
        ).pack(anchor='w', padx=18, pady=(10, 18))

    def _render_account_card(self, row, profile):
        active = profile.id == self.active_account_id
        icon, status_text, status_color = STATUS_LABELS.get(
            profile.status, ('⚪', profile.status or 'Offline', '#94a3b8')
        )

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

        if profile.status in {'onboarding', 'reauth', 'error'}:
            ctk.CTkButton(
                buttons,
                text='Autenticar',
                width=112,
                command=lambda p=profile: self._begin_profile_login(p),
            ).pack(pady=3)
        if not active and profile.status not in {'onboarding'}:
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

    # ------------------------------------------------------------------
    # Onboarding telefone -> código -> 2FA
    # ------------------------------------------------------------------
    def _add_account(self):
        if self.running:
            return
        try:
            label = simpledialog.askstring(
                'Nova conta Telegram',
                'Dê um nome para identificar esta conta (ex.: Loja Maria):',
                parent=self,
            )
            if label is None:
                return
            profile = self.account_profiles.create_pending(label)
        except Exception as exc:
            messagebox.showwarning('Nova conta Telegram', str(exc))
            return
        self._refresh_accounts_tab()
        self._begin_profile_login(profile)

    def _begin_profile_login(self, profile):
        phone = simpledialog.askstring(
            'Conectar Telegram · telefone',
            'Informe o número da conta com DDI. Exemplo: +55 93 99999-9999',
            parent=self,
        )
        if phone is None:
            return
        phone = phone.strip()
        if not phone:
            messagebox.showwarning('Conectar Telegram', 'Informe um telefone válido.')
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
            phone_masked=mask_phone(phone),
            last_error='',
        )
        self._refresh_accounts_tab()
        self._submit(
            service.begin_login(phone),
            lambda future, account_id=profile.id: self._after_begin_login(account_id, future),
        )

    def _after_begin_login(self, account_id, future):
        service = self._login_services.get(account_id)
        try:
            result = future.result()
        except Exception as exc:
            self._login_failed(account_id, exc)
            return

        if result.get('already_authorized'):
            self._finish_login(account_id, result['user'])
            return

        code = simpledialog.askstring(
            'Conectar Telegram · código',
            'Digite o código enviado pelo Telegram para esta conta:',
            parent=self,
        )
        if code is None:
            return
        self._submit(
            service.complete_login_code(code),
            lambda next_future, aid=account_id: self._after_login_code(aid, next_future),
        )

    def _after_login_code(self, account_id, future):
        service = self._login_services.get(account_id)
        try:
            result = future.result()
        except Exception as exc:
            self._login_failed(account_id, exc)
            return

        if not result.get('needs_password'):
            self._finish_login(account_id, result['user'])
            return

        password = simpledialog.askstring(
            'Conectar Telegram · 2FA',
            'Esta conta usa verificação em duas etapas. Digite a senha 2FA:',
            parent=self,
            show='•',
        )
        if password is None:
            return
        self._submit(
            service.complete_login_password(password),
            lambda next_future, aid=account_id: self._after_login_password(aid, next_future),
        )

    def _after_login_password(self, account_id, future):
        try:
            user = future.result()
        except Exception as exc:
            self._login_failed(account_id, exc)
            return
        self._finish_login(account_id, user)

    def _finish_login(self, account_id, user):
        profile = self.account_profiles.update(
            account_id,
            status='offline',
            telegram_user_id=int(user.id),
            username=getattr(user, 'username', None) or '',
            display_name=full_name(user),
            last_error='',
        )
        service = self._login_services.pop(account_id, None)
        if service is not None:
            self._submit(service.disconnect(), lambda _future: None)
        self._refresh_accounts_tab()
        messagebox.showinfo(
            'Telegram conectado',
            f'Conta "{profile.display_name or profile.label}" autenticada com sucesso.\n\n'
            'Clique em “Ativar conta” para carregar os grupos desta conta.',
        )

    def _login_failed(self, account_id, exc):
        self.account_profiles.update(
            account_id,
            status='reauth',
            last_error=f'{type(exc).__name__}: {exc}',
        )
        service = self._login_services.pop(account_id, None)
        if service is not None:
            self._submit(service.disconnect(), lambda _future: None)
        self._refresh_accounts_tab()
        messagebox.showerror(
            'Falha ao conectar Telegram',
            f'{type(exc).__name__}: {exc}\n\nVocê pode tentar novamente pelo botão Autenticar.',
        )

    # ------------------------------------------------------------------
    # Troca de conta
    # ------------------------------------------------------------------
    def _activate_account(self, profile):
        if self.running:
            messagebox.showwarning('Trocar conta', 'Pare a operação atual antes de trocar de conta.')
            return
        old_service = self.service
        self.service = None
        if old_service is None:
            self._finish_account_switch(profile)
            return
        self._submit(
            old_service.disconnect(),
            lambda _future, p=profile: self._finish_account_switch(p),
        )

    def _finish_account_switch(self, profile):
        self.account_profiles.set_active(profile.id)
        self._apply_account_context(profile)
        self._refresh_account_scoped_views()
        self.source_combo.set('')
        self.destination_combo.set('')
        self.connection_badge.configure(text='● Desconectado', text_color='#f59e0b')
        self.account_label.configure(text=f'Conta ativa: {profile.display_name or profile.label}. Conectando...')
        self._refresh_accounts_tab()
        self._connect()

    # ------------------------------------------------------------------
    # Restrições por conta
    # ------------------------------------------------------------------
    def _record_rate_limit_from_history(self, message_mode=False):
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
                    last_error='Telegram recusou novas ações com PEER_FLOOD. Operações reais pausadas nesta conta.',
                    cooldown_until='',
                )
                self._refresh_accounts_tab()
                return
            if status in {'flood_wait', 'message_flood_wait'}:
                match = re.search(r'Não retomar antes de ([^\.]+)', row.get('reason') or '')
                cooldown = match.group(1).strip() if match else ''
                self.account_profiles.update(
                    profile.id,
                    status='cooldown',
                    last_error='Telegram determinou um período de espera para esta conta.',
                    cooldown_until=cooldown,
                )
                self._refresh_accounts_tab()
                return

    def _real_action_block_reason(self):
        profile = self._active_profile()
        if profile is None:
            return 'Nenhuma conta Telegram está ativa.'
        if profile.status == 'peer_flood':
            return (
                'Esta conta está pausada após PEER_FLOOD. Revise o estado da conta no Telegram '
                'e use “Revisar pausa” na aba Contas Telegram antes de uma nova tentativa real.'
            )
        if profile.status == 'cooldown' and profile.cooldown_until:
            try:
                until = datetime.fromisoformat(profile.cooldown_until)
                if datetime.now().astimezone() < until:
                    return f'Esta conta está em cooldown até {until.astimezone().strftime("%d/%m/%Y %H:%M:%S")}.'
            except ValueError:
                return 'Esta conta está em cooldown determinado pelo Telegram.'
            self.account_profiles.update(
                profile.id,
                status='active',
                cooldown_until='',
                last_error='',
            )
        return ''

    def _review_peer_flood(self, profile):
        confirmed = messagebox.askyesno(
            'Revisar pausa do Telegram',
            'O PEER_FLOOD não informa um horário exato de liberação.\n\n'
            'Só libere esta conta depois de revisar o estado dela no Telegram e decidir fazer '
            'uma nova tentativa controlada.\n\nLiberar operações reais desta conta?',
        )
        if not confirmed:
            return
        self.account_profiles.update(
            profile.id,
            status='active',
            last_error='',
            cooldown_until='',
        )
        self._refresh_accounts_tab()

    def _start_run(self):
        if not self.dry_run_var.get():
            reason = self._real_action_block_reason()
            if reason:
                messagebox.showwarning('Conta Telegram pausada', reason)
                return
        super()._start_run()

    def _after_run_v2(self, future):
        try:
            stats, _report_path, _prepared, was_dry_run = future.result()
        except Exception:
            stats = None
            was_dry_run = True
        if stats is not None and not was_dry_run and stats.rate_limited:
            self._record_rate_limit_from_history(message_mode=False)
        super()._after_run_v2(future)

    def _start_message_invites(self):
        if not self.dry_run_var.get():
            reason = self._real_action_block_reason()
            if reason:
                messagebox.showwarning('Conta Telegram pausada', reason)
                return
        super()._start_message_invites()

    def _after_message_invites(self, future):
        try:
            stats, _filtered, _selected_count, _link, _destination, dry_run = future.result()
        except Exception:
            stats = None
            dry_run = True
        if stats is not None and not dry_run and stats.rate_limited:
            self._record_rate_limit_from_history(message_mode=True)
        super()._after_message_invites(future)


if __name__ == '__main__':
    app = LocalAppV13()
    app.mainloop()
