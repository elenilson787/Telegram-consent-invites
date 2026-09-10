"""V18: polimento comercial do login e da assinatura do Telegram Extractor."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from local_app_v17 import LocalAppV17, LoginWindow, _load_initial_entitlements
from saas_auth import Entitlements, SaaSAuthClient, SaaSAuthError


CREATE_ACCOUNT_COLOR = '#0284c7'
CREATE_ACCOUNT_HOVER_COLOR = '#0369a1'
WHITE = '#ffffff'


def friendly_plan_name(plan_id: str | None, plan_name: str | None) -> str:
    """Converte nomes técnicos de plano em texto voltado ao cliente."""
    normalized_id = str(plan_id or '').strip().lower()
    normalized_name = str(plan_name or '').strip()
    if normalized_id == 'trial' or normalized_name.lower() in {'teste', 'trial'}:
        return 'Teste gratuito'
    return normalized_name or 'Sem assinatura'


def friendly_subscription_status(status: str | None, entitled: bool) -> str:
    """Apresenta o estado da assinatura sem expor códigos internos."""
    normalized = str(status or '').strip().lower()
    labels = {
        'trialing': '🟢 Em período de teste',
        'active': '🟢 Assinatura ativa',
        'past_due': '🟠 Pagamento pendente',
        'paused': '🟠 Assinatura pausada',
        'canceled': '🔴 Assinatura cancelada',
        'cancelled': '🔴 Assinatura cancelada',
        'expired': '🔴 Assinatura expirada',
        'none': '🔴 Sem assinatura',
    }
    if normalized in labels:
        return labels[normalized]
    return '🟢 Acesso ativo' if entitled else '🔴 Acesso indisponível'


def format_account_allowance(current: int, maximum: int) -> str:
    """Formata quantidade de contas com concordância correta em português."""
    current = max(0, int(current))
    maximum = max(0, int(maximum))
    current_text = 'conta cadastrada' if current == 1 else 'contas cadastradas'
    maximum_text = 'permitida' if maximum == 1 else 'permitidas'
    return f'{current} {current_text} de {maximum} {maximum_text}'


def confirmation_email_message(email: str) -> str:
    email = str(email or '').strip()
    destination = f' ({email})' if email else ''
    return (
        f'Verifique no e-mail informado{destination} o link de confirmação para ativar sua conta.\n\n'
        'Depois de confirmar o e-mail, volte ao Telegram Extractor e clique em Entrar.'
    )


def _replace_label_text(root, startswith: str, new_text: str) -> bool:
    """Atualiza um texto herdado sem depender da posição visual do widget."""
    for child in root.winfo_children():
        try:
            text = child.cget('text')
        except Exception:
            text = None
        if isinstance(text, str) and text.startswith(startswith):
            try:
                child.configure(text=new_text)
                return True
            except Exception:
                pass
        if _replace_label_text(child, startswith, new_text):
            return True
    return False


class LoginWindowV18(LoginWindow):
    """Login com contraste e instruções adequadas para o cliente final."""

    def __init__(self, auth: SaaSAuthClient):
        super().__init__(auth)

        # O botão secundário não deve parecer desabilitado no tema claro.
        self.login_button.configure(text_color=WHITE)
        self.signup_button.configure(
            fg_color=CREATE_ACCOUNT_COLOR,
            hover_color=CREATE_ACCOUNT_HOVER_COLOR,
            text_color=WHITE,
            border_width=0,
        )

        _replace_label_text(
            self,
            'Novos usuários recebem o plano Teste',
            'Comece com 7 dias grátis. Seu plano e seus limites são validados com segurança no servidor.',
        )

    def _after_sign_up(self, data, error):
        if error is not None:
            self._set_busy(False, f'Não foi possível criar a conta: {error}')
            return

        # Quando confirmação de e-mail não é exigida, o Supabase já devolve
        # uma sessão e o usuário entra imediatamente.
        if self.auth.session is not None:
            self.authenticated = True
            self.destroy()
            return

        email = self.email_entry.get().strip()
        self.password_entry.delete(0, 'end')
        self._set_busy(
            False,
            'E-mail de confirmação enviado. Confirme o link recebido e depois clique em Entrar.',
        )
        messagebox.showinfo(
            'Confirme seu e-mail',
            confirmation_email_message(email),
        )


class LocalAppV18(LocalAppV17):
    """V17 com linguagem e apresentação de assinatura prontas para comercialização."""

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
            ('direct', 'Teto direto por dia'),
            ('messages', 'Mensagens opt-in por dia'),
            ('history', 'Histórico disponível'),
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
            text='Planos disponíveis',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).pack(anchor='w', padx=16, pady=(12, 4))
        ctk.CTkLabel(
            plans,
            text=(
                'Teste gratuito: 1 conta · Starter: 1 conta · Pro: 3 contas · Business: 10 contas.\n'
                'Os recursos e limites são definidos automaticamente pelo seu plano.'
            ),
            justify='left',
            wraplength=1050,
            text_color=('gray40', 'gray70'),
        ).pack(anchor='w', padx=16, pady=(0, 14))

    def _refresh_subscription_ui(self):
        if not hasattr(self, 'subscription_labels'):
            return

        ent = self.entitlements
        email = self.saas_auth.session.email if self.saas_auth.session else '—'
        local_accounts = len(self.account_profiles.list()) if self.account_profiles else 0

        values = {
            'email': email,
            'plan': friendly_plan_name(ent.plan_id, ent.plan_name),
            'status': friendly_subscription_status(ent.subscription_status, ent.entitled),
            'period': self._format_period(ent.current_period_end),
            'accounts': format_account_allowance(local_accounts, ent.max_telegram_accounts),
            'direct': str(ent.daily_direct_cap),
            'messages': str(ent.daily_message_cap),
            'history': f'{ent.history_days} dia' if ent.history_days == 1 else f'{ent.history_days} dias',
        }
        for key, value in values.items():
            self.subscription_labels[key].configure(text=value)

        if ent.entitled:
            notice = (
                '✓ Plano validado com segurança no servidor. Os recursos e limites são '
                'aplicados automaticamente à sua conta.'
            )
            color = '#22c55e'
        else:
            notice = (
                'Seu plano não possui acesso ativo neste momento. As sessões Telegram locais '
                'continuam preservadas, mas novas conexões e operações ficam bloqueadas até a renovação.'
            )
            color = '#ef4444'
        self.subscription_notice.configure(text=notice, text_color=color)


def main():
    while True:
        auth = SaaSAuthClient()
        entitlements = _load_initial_entitlements(auth)

        if entitlements is None:
            login = LoginWindowV18(auth)
            login.mainloop()
            if not login.authenticated:
                return
            try:
                entitlements = auth.fetch_entitlements()
            except SaaSAuthError as exc:
                messagebox.showerror(
                    'Falha ao validar assinatura',
                    f'Login realizado, mas não foi possível validar o plano: {exc}',
                )
                auth.sign_out()
                continue

        app = LocalAppV18(auth, entitlements)
        app.mainloop()
        if app.request_logout:
            continue
        return


if __name__ == '__main__':
    main()
