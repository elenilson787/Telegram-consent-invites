"""V16: primeira camada comercial de saúde operacional do Telegram Extractor.

Esta versão não tenta inferir ou prometer um limite oficial do Telegram.
Ela aplica tetos operacionais próprios, por conta, usando o histórico local para
informar consumo diário, restrições e uso dos últimos sete dias.
"""

import os
from tkinter import messagebox

import customtkinter as ctk

from local_app_v15 import LocalAppV15


BRAND_NAME = 'Telegram Extractor'
DEFAULT_DIRECT_DAILY_CAP = 20
DEFAULT_MESSAGE_DAILY_CAP = 20


class LocalAppV16(LocalAppV15):
    """V15 com branding independente e centro de saúde/limites por conta."""

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self._apply_telegram_extractor_branding()
        self._install_health_tab()
        self._refresh_health()

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------
    def _apply_telegram_extractor_branding(self):
        self.title(BRAND_NAME)
        exact_replacements = {
            'AFILIAPULSE • Telegram Manager': 'TELEGRAM EXTRACTOR',
            'Gerenciamento local de participantes': 'Extração, gestão e convites controlados',
            'Gerenciamento local de participantes  •  OPERAÇÃO LOCAL / TELEGRAM API': (
                'Extração, gestão e convites controlados  •  OPERAÇÃO LOCAL / TELEGRAM API'
            ),
        }
        for widget in self._walk_widgets(self):
            if not isinstance(widget, ctk.CTkLabel):
                continue
            try:
                text = widget.cget('text')
            except Exception:
                continue
            replacement = exact_replacements.get(text)
            if replacement:
                widget.configure(text=replacement)

    def _show_provisioning_notice(self):
        messagebox.showwarning(
            'Agente Telegram não provisionado',
            'Esta instalação ainda não recebeu as credenciais técnicas do aplicativo Telegram.\n\n'
            f'Na versão comercial elas serão entregues ao agente após login/licença do {BRAND_NAME}, '
            'sem o cliente precisar conhecer API_ID ou API_HASH.\n\n'
            'Nesta build de desenvolvimento, mantenha TELEGRAM_API_ID e TELEGRAM_API_HASH no .env.',
        )

    def _finish_login(self, account_id, user):
        """Mantém a prevenção de duplicatas com o novo branding."""
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
                f'Esta conta Telegram já está cadastrada no {BRAND_NAME}.\n\n'
                f'Conta existente: {existing_name} · {existing_username}\n\n'
                'A tentativa duplicada foi descartada e não ocupa um novo slot do plano.',
            )
            return

        # Pula apenas a implementação de duplicidade da V15; usa a finalização
        # padrão da V13 através do ancestral direto da V15.
        from local_app_v13 import LocalAppV13
        LocalAppV13._finish_login(self, account_id, user)
        self._refresh_health()

    # ------------------------------------------------------------------
    # Tetos operacionais próprios do produto
    # ------------------------------------------------------------------
    @staticmethod
    def _read_positive_int(names, default, maximum=1000):
        for name in names:
            raw = os.getenv(name, '').strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value > 0:
                return min(value, maximum)
        return default

    def _direct_daily_cap(self):
        return self._read_positive_int(
            ('TELEGRAM_EXTRACTOR_DAILY_DIRECT_CAP', 'AFILIAPULSE_DAILY_DIRECT_CAP'),
            DEFAULT_DIRECT_DAILY_CAP,
        )

    def _message_daily_cap(self):
        return self._read_positive_int(
            ('TELEGRAM_EXTRACTOR_DAILY_MESSAGE_CAP', 'AFILIAPULSE_DAILY_MESSAGE_CAP'),
            DEFAULT_MESSAGE_DAILY_CAP,
        )

    # ------------------------------------------------------------------
    # Aba Saúde
    # ------------------------------------------------------------------
    def _install_health_tab(self):
        self.tabs.add('Saúde')
        tab = self.tabs.tab('Saúde')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(tab, corner_radius=12, border_width=1, border_color='#22d3ee')
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=(6, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text='🛡️ Saúde da conta Telegram',
            font=ctk.CTkFont(size=20, weight='bold'),
            text_color='#22d3ee',
        ).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 2))
        self.health_account_label = ctk.CTkLabel(
            header,
            text='Nenhuma conta ativa',
            font=ctk.CTkFont(size=13, weight='bold'),
        )
        self.health_account_label.grid(row=1, column=0, sticky='w', padx=16, pady=(0, 12))

        self.health_status_badge = ctk.CTkLabel(
            header,
            text='⚪ Sem dados',
            font=ctk.CTkFont(size=14, weight='bold'),
            text_color='#94a3b8',
        )
        self.health_status_badge.grid(row=0, column=1, rowspan=2, sticky='e', padx=(12, 16))

        ctk.CTkButton(
            header,
            text='Atualizar',
            width=95,
            command=self._refresh_health,
        ).grid(row=0, column=2, rowspan=2, sticky='e', padx=(0, 16))

        metrics = ctk.CTkFrame(tab, fg_color='transparent')
        metrics.grid(row=1, column=0, sticky='ew', padx=3, pady=4)
        self.health_metric_labels = {}
        metric_defs = (
            ('direct_attempts', 'Tentativas diretas hoje'),
            ('added', 'Adicionados hoje'),
            ('messages_sent', 'Mensagens opt-in'),
            ('rate_limits', 'Rate limits hoje'),
            ('direct_remaining', 'Saldo direto'),
            ('message_remaining', 'Saldo mensagens'),
        )
        for column, (key, title) in enumerate(metric_defs):
            metrics.grid_columnconfigure(column, weight=1)
            card = ctk.CTkFrame(metrics, corner_radius=10, border_width=1, border_color='#334155')
            card.grid(row=0, column=column, sticky='ew', padx=3)
            value = ctk.CTkLabel(
                card,
                text='—',
                font=ctk.CTkFont(size=22, weight='bold'),
                text_color='#22d3ee',
            )
            value.pack(pady=(10, 0))
            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=11),
                text_color=('gray45', 'gray70'),
            ).pack(pady=(0, 10))
            self.health_metric_labels[key] = value

        usage = ctk.CTkFrame(tab, corner_radius=12)
        usage.grid(row=2, column=0, sticky='ew', padx=6, pady=8)
        usage.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            usage,
            text='Orçamento operacional diário',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, columnspan=3, sticky='w', padx=16, pady=(12, 2))
        ctk.CTkLabel(
            usage,
            text=(
                'Referência interna do Telegram Extractor — não é um limite oficial do Telegram. '
                'O Telegram pode restringir uma conta antes destes valores.'
            ),
            wraplength=1080,
            justify='left',
            text_color='#f59e0b',
        ).grid(row=1, column=0, columnspan=3, sticky='w', padx=16, pady=(0, 10))

        ctk.CTkLabel(usage, text='Inclusões diretas').grid(row=2, column=0, sticky='w', padx=16, pady=6)
        self.direct_usage_bar = ctk.CTkProgressBar(usage)
        self.direct_usage_bar.grid(row=2, column=1, sticky='ew', padx=8, pady=6)
        self.direct_usage_text = ctk.CTkLabel(usage, text='0 / 0', width=100)
        self.direct_usage_text.grid(row=2, column=2, padx=(8, 16), pady=6)

        ctk.CTkLabel(usage, text='Mensagens opt-in').grid(row=3, column=0, sticky='w', padx=16, pady=(6, 14))
        self.message_usage_bar = ctk.CTkProgressBar(usage)
        self.message_usage_bar.grid(row=3, column=1, sticky='ew', padx=8, pady=(6, 14))
        self.message_usage_text = ctk.CTkLabel(usage, text='0 / 0', width=100)
        self.message_usage_text.grid(row=3, column=2, padx=(8, 16), pady=(6, 14))

        info = ctk.CTkFrame(tab, fg_color='transparent')
        info.grid(row=3, column=0, sticky='ew', padx=3, pady=4)
        info.grid_columnconfigure((0, 1), weight=1)

        history_card = ctk.CTkFrame(info, corner_radius=12)
        history_card.grid(row=0, column=0, sticky='nsew', padx=3)
        history_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            history_card,
            text='Últimos 7 dias',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 4))
        self.health_week_box = ctk.CTkTextbox(history_card, height=185, wrap='none')
        self.health_week_box.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.health_week_box.configure(state='disabled')

        protection_card = ctk.CTkFrame(info, corner_radius=12)
        protection_card.grid(row=0, column=1, sticky='nsew', padx=3)
        ctk.CTkLabel(
            protection_card,
            text='Proteções ativas',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).pack(anchor='w', padx=14, pady=(12, 5))
        protections = (
            '✓ Para imediatamente em PeerFlood',
            '✓ Respeita FloodWait e cooldown',
            '✓ Não repete usuários já processados',
            '✓ Filtra admins, bots e duplicados',
            '✓ Exige confirmação no modo real',
            '✓ Retorna ao DRY RUN após cada rodada',
            '✓ Histórico e restrições isolados por conta',
            '✓ Teto operacional diário por conta',
        )
        for text in protections:
            ctk.CTkLabel(
                protection_card,
                text=text,
                anchor='w',
                justify='left',
                text_color='#22c55e',
            ).pack(anchor='w', padx=14, pady=3)

        self.health_recommendation = ctk.CTkLabel(
            tab,
            text='',
            anchor='w',
            justify='left',
            wraplength=1180,
            font=ctk.CTkFont(size=13, weight='bold'),
        )
        self.health_recommendation.grid(row=4, column=0, sticky='new', padx=12, pady=(8, 14))

    def _health_snapshot(self):
        if self.store is None:
            return None
        today = self.store.activity_counts_for_day()
        week = self.store.activity_series(7)
        direct_cap = self._direct_daily_cap()
        message_cap = self._message_daily_cap()
        return today, week, direct_cap, message_cap

    def _health_state(self, profile, today, direct_cap, message_cap):
        if profile is None:
            return '⚪ Sem conta ativa', '#94a3b8', 'Adicione ou ative uma conta Telegram para começar.'
        if profile.status == 'peer_flood':
            return (
                '🔴 PAUSADA · PeerFlood',
                '#ef4444',
                'O Telegram recusou novas ações nesta conta. Operações reais permanecem pausadas até revisão manual.',
            )
        if profile.status == 'cooldown':
            detail = f' até {profile.cooldown_until}' if profile.cooldown_until else ''
            return (
                '🟠 COOLDOWN',
                '#f97316',
                f'O Telegram determinou espera para esta conta{detail}. Não execute novas ações reais durante o cooldown.',
            )

        total_rate_limits = today['direct_rate_limits'] + today['message_rate_limits']
        direct_ratio = today['direct_attempts'] / max(1, direct_cap)
        message_ratio = today['messages_attempted'] / max(1, message_cap)
        if total_rate_limits:
            return (
                '🟠 ATENÇÃO',
                '#f97316',
                'Houve rate limit hoje. Revise o histórico antes de iniciar outra operação real.',
            )
        if direct_ratio >= 1 or message_ratio >= 1:
            return (
                '🟡 TETO OPERACIONAL',
                '#f59e0b',
                'O orçamento operacional interno de hoje foi alcançado. O modo real fica bloqueado para o tipo de ação esgotado.',
            )
        if direct_ratio >= 0.8 or message_ratio >= 0.8:
            return (
                '🟡 ATENÇÃO',
                '#f59e0b',
                'A conta está próxima do teto operacional interno de hoje. Evite aumentar ritmo ou lote.',
            )
        return (
            '🟢 NORMAL',
            '#22c55e',
            'Conta dentro da referência operacional interna. Isso não garante ausência de limites do Telegram.',
        )

    def _latest_restriction_text(self):
        rows = []
        try:
            rows.extend(self.store.recent_history(100))
            rows.extend(self.store.recent_message_history(100))
        except Exception:
            return 'Última restrição: indisponível.'
        restricted = [
            row for row in rows
            if row.get('status') in {
                'peer_flood', 'flood_wait', 'message_peer_flood', 'message_flood_wait'
            }
        ]
        if not restricted:
            return 'Última restrição: nenhuma registrada no histórico desta conta.'
        row = max(restricted, key=lambda item: item.get('timestamp', ''))
        when = str(row.get('timestamp', '')).replace('T', ' ')[:19]
        return f'Última restrição: {row.get("status", "").upper()} em {when}.'

    def _refresh_health(self):
        if not hasattr(self, 'health_metric_labels'):
            return
        profile = self._active_profile()
        try:
            today, week, direct_cap, message_cap = self._health_snapshot()
        except Exception as exc:
            self.health_status_badge.configure(text='🔴 Erro ao calcular', text_color='#ef4444')
            self.health_recommendation.configure(text=f'Não foi possível calcular a saúde da conta: {exc}')
            return

        identity = 'Nenhuma conta ativa'
        if profile is not None:
            identity = profile.display_name or profile.label
            if profile.username:
                identity += f' · @{profile.username}'
        self.health_account_label.configure(text=identity)

        rate_limits = today['direct_rate_limits'] + today['message_rate_limits']
        direct_remaining = max(0, direct_cap - today['direct_attempts'])
        message_remaining = max(0, message_cap - today['messages_attempted'])
        values = {
            'direct_attempts': today['direct_attempts'],
            'added': today['added'],
            'messages_sent': today['messages_sent'],
            'rate_limits': rate_limits,
            'direct_remaining': direct_remaining,
            'message_remaining': message_remaining,
        }
        for key, value in values.items():
            self.health_metric_labels[key].configure(text=str(value))

        self.direct_usage_bar.set(min(1.0, today['direct_attempts'] / max(1, direct_cap)))
        self.message_usage_bar.set(min(1.0, today['messages_attempted'] / max(1, message_cap)))
        self.direct_usage_text.configure(text=f'{today["direct_attempts"]} / {direct_cap}')
        self.message_usage_text.configure(text=f'{today["messages_attempted"]} / {message_cap}')

        status_text, status_color, recommendation = self._health_state(
            profile, today, direct_cap, message_cap
        )
        self.health_status_badge.configure(text=status_text, text_color=status_color)
        self.health_recommendation.configure(
            text=f'{recommendation}\n{self._latest_restriction_text()}',
            text_color=status_color,
        )

        lines = ['DATA       DIRETAS  ADICIONADOS  MENSAGENS  LIMITES']
        for row in week:
            day = row['day'][8:10] + '/' + row['day'][5:7]
            limits = row['direct_rate_limits'] + row['message_rate_limits']
            lines.append(
                f'{day:<10} {row["direct_attempts"]:^8} {row["added"]:^11} '
                f'{row["messages_sent"]:^10} {limits:^7}'
            )
        self.health_week_box.configure(state='normal')
        self.health_week_box.delete('1.0', 'end')
        self.health_week_box.insert('1.0', '\n'.join(lines))
        self.health_week_box.configure(state='disabled')

    # ------------------------------------------------------------------
    # Guarda de orçamento operacional
    # ------------------------------------------------------------------
    def _enforce_daily_budget(self, mode: str, requested: int) -> bool:
        today = self.store.activity_counts_for_day()
        if mode == 'direct':
            used = today['direct_attempts']
            cap = self._direct_daily_cap()
            field = self.limit_var
            label = 'tentativas de inclusão direta'
        else:
            used = today['messages_attempted']
            cap = self._message_daily_cap()
            field = self.message_limit_var
            label = 'mensagens opt-in'

        remaining = max(0, cap - used)
        if remaining <= 0:
            messagebox.showwarning(
                'Teto operacional diário',
                f'O Telegram Extractor já utilizou o teto interno de {cap} {label} nesta conta hoje.\n\n'
                'Este valor é uma proteção do produto, não um limite oficial do Telegram. '
                'O Telegram pode restringir a conta antes desse número.',
            )
            self._refresh_health()
            return False

        if requested > remaining:
            field.set(str(remaining))
            messagebox.showinfo(
                'Lote ajustado ao saldo diário',
                f'Você solicitou {requested}, mas restam {remaining} {label} no orçamento operacional de hoje.\n\n'
                f'O lote foi ajustado automaticamente para {remaining}.',
            )
        return True

    def _start_run(self):
        if not self.dry_run_var.get():
            try:
                requested = int(self.limit_var.get().strip())
            except Exception:
                requested = 1
            if not self._enforce_daily_budget('direct', requested):
                return
        super()._start_run()

    def _start_message_invites(self):
        if not self.dry_run_var.get():
            try:
                requested = int(self.message_limit_var.get().strip())
            except Exception:
                requested = 1
            if not self._enforce_daily_budget('message', requested):
                return
        super()._start_message_invites()

    # ------------------------------------------------------------------
    # Atualizações automáticas da saúde
    # ------------------------------------------------------------------
    def _apply_account_context(self, profile):
        super()._apply_account_context(profile)
        self._refresh_health()

    def _refresh_accounts_tab(self):
        super()._refresh_accounts_tab()
        self._refresh_health()

    def _after_connect(self, future):
        super()._after_connect(future)
        self._refresh_health()

    def _after_run_v2(self, future):
        super()._after_run_v2(future)
        self._refresh_health()

    def _after_message_invites(self, future):
        super()._after_message_invites(future)
        self._refresh_health()

    def _review_peer_flood(self, profile):
        super()._review_peer_flood(profile)
        self._refresh_health()


if __name__ == '__main__':
    app = LocalAppV16()
    app.mainloop()
