"""V17: login SaaS, assinatura e entitlements server-side do Telegram Extractor."""

from __future__ import annotations

import os
import threading
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from local_app_v16 import LocalAppV16
from saas_auth import Entitlements, SaaSAuthClient, SaaSAuthError


LICENSE_REFRESH_MS = 5 * 60 * 1000


class LoginWindow(ctk.CTk):
    """Porta de entrada do produto antes de qualquer sessão Telegram ser usada."""

    def __init__(self, auth: SaaSAuthClient):
        super().__init__()
        self.auth = auth
        self.authenticated = False
        self.title('Telegram Extractor • Login')
        self.geometry('520x530')
        self.minsize(500, 500)
        self.grid_columnconfigure(0, weight=1)
        self.protocol('WM_DELETE_WINDOW', self.destroy)

        card = ctk.CTkFrame(self, corner_radius=16, border_width=1, border_color='#22d3ee')
        card.grid(row=0, column=0, sticky='nsew', padx=38, pady=35)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text='TELEGRAM EXTRACTOR',
            font=ctk.CTkFont(size=27, weight='bold'),
            text_color='#22d3ee',
        ).grid(row=0, column=0, padx=28, pady=(30, 4))
        ctk.CTkLabel(
            card,
            text='Entre para validar seu plano e liberar o agente Telegram.',
            wraplength=400,
            justify='center',
            text_color=('gray40', 'gray70'),
        ).grid(row=1, column=0, padx=28, pady=(0, 24))

        self.email_entry = ctk.CTkEntry(card, placeholder_text='E-mail', height=42)
        self.email_entry.grid(row=2, column=0, sticky='ew', padx=32, pady=7)
        self.password_entry = ctk.CTkEntry(
            card, placeholder_text='Senha', show='•', height=42
        )
        self.password_entry.grid(row=3, column=0, sticky='ew', padx=32, pady=7)
        self.password_entry.bind('<Return>', lambda _event: self._sign_in())

        self.status_label = ctk.CTkLabel(
            card,
            text='',
            wraplength=390,
            justify='left',
            text_color='#f59e0b',
        )
        self.status_label.grid(row=4, column=0, sticky='w', padx=32, pady=(4, 6))

        self.login_button = ctk.CTkButton(
            card,
            text='Entrar',
            height=42,
            command=self._sign_in,
            fg_color='#7c3aed',
            hover_color='#6d28d9',
        )
        self.login_button.grid(row=5, column=0, sticky='ew', padx=32, pady=(8, 5))

        self.signup_button = ctk.CTkButton(
            card,
            text='Criar conta',
            height=38,
            command=self._sign_up,
            fg_color='transparent',
            border_width=1,
            border_color='#22d3ee',
        )
        self.signup_button.grid(row=6, column=0, sticky='ew', padx=32, pady=5)

        ctk.CTkLabel(
            card,
            text=(
                'Novos usuários recebem o plano Teste por 7 dias. '
                'A assinatura e os limites são validados no servidor.'
            ),
            wraplength=390,
            justify='center',
            font=ctk.CTkFont(size=11),
            text_color=('gray45', 'gray65'),
        ).grid(row=7, column=0, padx=32, pady=(18, 26))

        self.after(150, self.email_entry.focus_set)

    def _set_busy(self, busy: bool, text: str = ''):
        state = 'disabled' if busy else 'normal'
        self.login_button.configure(state=state)
        self.signup_button.configure(state=state)
        self.status_label.configure(text=text)

    def _credentials(self):
        return self.email_entry.get().strip(), self.password_entry.get()

    def _run(self, function, callback):
        def worker():
            try:
                result = function()
                error = None
            except Exception as exc:  # resposta exibida na thread principal
                result = None
                error = exc
            self.after(0, callback, result, error)

        threading.Thread(target=worker, daemon=True).start()

    def _sign_in(self):
        email, password = self._credentials()
        self._set_busy(True, 'Validando login...')
        self._run(
            lambda: self.auth.sign_in(email, password),
            self._after_sign_in,
        )

    def _after_sign_in(self, _session, error):
        if error is not None:
            self._set_busy(False, f'Não foi possível entrar: {error}')
            return
        self.authenticated = True
        self.destroy()

    def _sign_up(self):
        email, password = self._credentials()
        self._set_busy(True, 'Criando conta...')
        self._run(
            lambda: self.auth.sign_up(email, password),
            self._after_sign_up,
        )

    def _after_sign_up(self, data, error):
        if error is not None:
            self._set_busy(False, f'Não foi possível criar a conta: {error}')
            return
        if self.auth.session is not None:
            self.authenticated = True
            self.destroy()
            return
        self._set_busy(
            False,
            'Conta criada. Confirme o e-mail enviado pelo Supabase e depois clique em Entrar.',
        )


class LocalAppV17(LocalAppV16):
    """V16 com licença, plano e limite de contas validados no Supabase."""

    def __init__(self, auth: SaaSAuthClient, entitlements: Entitlements):
        self.saas_auth = auth
        self.entitlements = entitlements
        self.request_logout = False
        self._license_refresh_running = False
        self._apply_entitlement_env(entitlements)
        super().__init__()
        if not self.winfo_exists():
            return
        self._install_subscription_tab()
        self._refresh_subscription_ui()
        if not entitlements.entitled:
            self.tabs.set('Assinatura')
        self.after(LICENSE_REFRESH_MS, self._periodic_license_refresh)

    # ------------------------------------------------------------------
    # Startup / licença
    # ------------------------------------------------------------------
    def _auto_connect_existing_session(self):
        if getattr(self, 'entitlements', None) and self.entitlements.entitled:
            super()._auto_connect_existing_session()

    @staticmethod
    def _apply_entitlement_env(entitlements: Entitlements):
        os.environ['TELEGRAM_EXTRACTOR_MAX_ACCOUNTS'] = str(
            max(1, entitlements.max_telegram_accounts)
        )
        os.environ['TELEGRAM_EXTRACTOR_DAILY_DIRECT_CAP'] = str(
            max(1, entitlements.daily_direct_cap)
        )
        os.environ['TELEGRAM_EXTRACTOR_DAILY_MESSAGE_CAP'] = str(
            max(1, entitlements.daily_message_cap)
        )

    def _license_guard(self, action='usar este recurso') -> bool:
        ent = getattr(self, 'entitlements', None)
        if ent is not None and ent.entitled:
            return True
        messagebox.showwarning(
            'Assinatura necessária',
            f'Não é possível {action} porque esta assinatura não está ativa.\n\n'
            'Abra a aba Assinatura para consultar o plano e a validade.',
        )
        if hasattr(self, 'tabs'):
            self.tabs.set('Assinatura')
        return False

    def _allowed_account_ids(self) -> set[str]:
        if self.account_profiles is None or not self.entitlements.entitled:
            return set()
        maximum = max(0, self.entitlements.max_telegram_accounts)
        profiles = self.account_profiles.list()
        if maximum <= 0:
            return set()

        active_id = self.active_account_id
        ordered = []
        if active_id:
            ordered.extend([p for p in profiles if p.id == active_id])
        ordered.extend([p for p in profiles if p.id != active_id])
        return {p.id for p in ordered[:maximum]}

    def _add_account(self):
        if not self._license_guard('adicionar uma conta Telegram'):
            return
        current = len(self.account_profiles.list()) if self.account_profiles else 0
        maximum = self.entitlements.max_telegram_accounts
        if current >= maximum:
            messagebox.showinfo(
                'Limite do plano',
                f'Seu plano {self.entitlements.plan_name} permite {maximum} conta(s) Telegram.\n\n'
                'Para adicionar outra conta será necessário um plano com limite maior.',
            )
            self.tabs.set('Assinatura')
            return
        super()._add_account()

    def _begin_profile_login(self, profile):
        if not self._license_guard('autenticar uma conta Telegram'):
            return
        super()._begin_profile_login(profile)

    def _activate_account(self, profile):
        if not self._license_guard('ativar uma conta Telegram'):
            return
        if profile.id not in self._allowed_account_ids():
            messagebox.showwarning(
                'Conta fora do limite do plano',
                f'O plano {self.entitlements.plan_name} permite '
                f'{self.entitlements.max_telegram_accounts} conta(s) Telegram.\n\n'
                'Esta conta local está preservada, mas fica bloqueada até o plano permitir mais contas.',
            )
            self.tabs.set('Assinatura')
            return
        super()._activate_account(profile)

    def _connect_active_account(self):
        if not self._license_guard('conectar o Telegram'):
            return
        profile = self._active_profile()
        if profile is not None and profile.id not in self._allowed_account_ids():
            messagebox.showwarning('Limite do plano', 'Esta conta está fora do limite atual do plano.')
            return
        super()._connect_active_account()

    def _start_run(self):
        if not self._license_guard('iniciar uma rodada real ou simulada'):
            return
        super()._start_run()

    def _start_message_invites(self):
        if not self._license_guard('executar convites por mensagem'):
            return
        super()._start_message_invites()

    # ------------------------------------------------------------------
    # Aba Assinatura
    # ------------------------------------------------------------------
    def _install_subscription_tab(self):
        self.tabs.add('Assinatura')
        tab = self.tabs.tab('Assinatura')
        tab.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(tab, corner_radius=14, border_width=1, border_color='#7c3aed')
        card.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text='💳 Minha assinatura',
            font=ctk.CTkFont(size=21, weight='bold'),
            text_color='#c084fc',
        ).grid(row=0, column=0, columnspan=2, sticky='w', padx=18, pady=(16, 10))

        fields = (
            ('email', 'Conta'),
            ('plan', 'Plano'),
            ('status', 'Status'),
            ('period', 'Validade'),
            ('accounts', 'Contas Telegram'),
            ('direct', 'Teto direto / dia'),
            ('messages', 'Mensagens opt-in / dia'),
            ('history', 'Histórico do plano'),
        )
        self.subscription_labels = {}
        for row, (key, title) in enumerate(fields, start=1):
            ctk.CTkLabel(
                card,
                text=title,
                width=180,
                anchor='w',
                font=ctk.CTkFont(weight='bold'),
            ).grid(row=row, column=0, sticky='w', padx=(18, 8), pady=6)
            label = ctk.CTkLabel(card, text='—', anchor='w', justify='left')
            label.grid(row=row, column=1, sticky='w', padx=(8, 18), pady=6)
            self.subscription_labels[key] = label

        buttons = ctk.CTkFrame(card, fg_color='transparent')
        buttons.grid(row=10, column=0, columnspan=2, sticky='ew', padx=18, pady=(16, 16))
        ctk.CTkButton(
            buttons,
            text='Atualizar assinatura',
            command=self._refresh_license_now,
            width=170,
        ).pack(side='left', padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text='Sair da conta',
            command=self._logout_saas,
            width=130,
            fg_color='#991b1b',
            hover_color='#7f1d1d',
        ).pack(side='left', padx=8)

        self.subscription_notice = ctk.CTkLabel(
            tab,
            text='',
            wraplength=1050,
            justify='left',
            anchor='w',
        )
        self.subscription_notice.grid(row=1, column=0, sticky='ew', padx=16, pady=8)

        plans = ctk.CTkFrame(tab, corner_radius=12)
        plans.grid(row=2, column=0, sticky='ew', padx=8, pady=8)
        ctk.CTkLabel(
            plans,
            text='Planos preparados no servidor',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).pack(anchor='w', padx=16, pady=(12, 4))
        ctk.CTkLabel(
            plans,
            text=(
                'Teste: 1 conta · Starter: 1 conta · Pro: 3 contas · Business: 10 contas.\n'
                'O checkout será conectado ao provedor de pagamento na próxima etapa; '
                'o aplicativo já consome o plano exclusivamente do servidor.'
            ),
            justify='left',
            wraplength=1050,
            text_color=('gray40', 'gray70'),
        ).pack(anchor='w', padx=16, pady=(0, 14))

    @staticmethod
    def _format_period(value: str | None) -> str:
        if not value:
            return 'Sem data de expiração'
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone()
            return dt.strftime('%d/%m/%Y %H:%M')
        except Exception:
            return str(value)

    def _refresh_subscription_ui(self):
        if not hasattr(self, 'subscription_labels'):
            return
        ent = self.entitlements
        email = self.saas_auth.session.email if self.saas_auth.session else '—'
        local_accounts = len(self.account_profiles.list()) if self.account_profiles else 0
        status_text = ent.subscription_status.upper()
        if ent.entitled:
            status_text = '🟢 ' + status_text
        else:
            status_text = '🔴 ' + status_text

        values = {
            'email': email,
            'plan': f'{ent.plan_name} ({ent.plan_id or "—"})',
            'status': status_text,
            'period': self._format_period(ent.current_period_end),
            'accounts': f'{local_accounts} cadastrada(s) / {ent.max_telegram_accounts} permitida(s)',
            'direct': str(ent.daily_direct_cap),
            'messages': str(ent.daily_message_cap),
            'history': f'{ent.history_days} dias',
        }
        for key, value in values.items():
            self.subscription_labels[key].configure(text=value)

        if ent.entitled:
            notice = (
                '✓ Assinatura validada no servidor. Os limites desta instalação são derivados '
                'do plano acima e não podem ser aumentados editando o arquivo local.'
            )
            color = '#22c55e'
        else:
            notice = (
                'Assinatura sem acesso ativo. As sessões Telegram locais permanecem preservadas, '
                'mas conexão, novas contas e operações ficam bloqueadas até a renovação.'
            )
            color = '#ef4444'
        self.subscription_notice.configure(text=notice, text_color=color)

    # ------------------------------------------------------------------
    # Renovação periódica dos entitlements
    # ------------------------------------------------------------------
    def _refresh_license_now(self):
        if self._license_refresh_running:
            return
        self._license_refresh_running = True
        if hasattr(self, 'subscription_notice'):
            self.subscription_notice.configure(text='Validando assinatura no servidor...', text_color='#f59e0b')

        def worker():
            try:
                result = self.saas_auth.fetch_entitlements()
                error = None
            except Exception as exc:
                result = None
                error = exc
            self.after(0, self._after_license_refresh, result, error)

        threading.Thread(target=worker, daemon=True).start()

    def _after_license_refresh(self, entitlements, error):
        self._license_refresh_running = False
        if error is not None:
            if hasattr(self, 'subscription_notice'):
                self.subscription_notice.configure(
                    text=f'Não foi possível validar agora: {error}. O último estado válido foi preservado.',
                    text_color='#f59e0b',
                )
            return

        was_entitled = self.entitlements.entitled
        self.entitlements = entitlements
        self._apply_entitlement_env(entitlements)
        self._refresh_subscription_ui()
        self._refresh_accounts_tab()
        self._refresh_health()

        if was_entitled and not entitlements.entitled:
            self._lock_after_subscription_loss()
            messagebox.showwarning(
                'Assinatura sem acesso',
                'A assinatura deixou de permitir uso do Telegram Extractor. '
                'As sessões locais foram preservadas e as operações foram bloqueadas.',
            )
            self.tabs.set('Assinatura')

    def _periodic_license_refresh(self):
        if self.winfo_exists():
            self._refresh_license_now()
            self.after(LICENSE_REFRESH_MS, self._periodic_license_refresh)

    def _lock_after_subscription_loss(self):
        service = getattr(self, 'service', None)
        self.service = None
        if service is not None:
            try:
                self._submit(service.disconnect(), lambda _future: None)
            except Exception:
                pass
        if hasattr(self, 'connection_badge'):
            self.connection_badge.configure(text='● Assinatura inativa', text_color='#ef4444')

    def _logout_saas(self):
        if not messagebox.askyesno(
            'Sair da conta',
            'Sair do Telegram Extractor? As sessões Telegram locais não serão apagadas.',
        ):
            return
        self.saas_auth.sign_out()
        self.request_logout = True
        self._lock_after_subscription_loss()
        self.destroy()


def _load_initial_entitlements(auth: SaaSAuthClient) -> Entitlements | None:
    session = auth.restore()
    if session is None:
        return None
    try:
        return auth.fetch_entitlements()
    except SaaSAuthError:
        return None


def main():
    while True:
        auth = SaaSAuthClient()
        entitlements = _load_initial_entitlements(auth)

        if entitlements is None:
            login = LoginWindow(auth)
            login.mainloop()
            if not login.authenticated:
                return
            try:
                entitlements = auth.fetch_entitlements()
            except SaaSAuthError as exc:
                # Uma autenticação válida sem resposta de assinatura não libera o agente.
                messagebox.showerror(
                    'Falha ao validar assinatura',
                    f'Login realizado, mas não foi possível validar o plano: {exc}',
                )
                auth.sign_out()
                continue

        app = LocalAppV17(auth, entitlements)
        app.mainloop()
        if app.request_logout:
            continue
        return


if __name__ == '__main__':
    main()
