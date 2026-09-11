"""V19: proteção adaptativa contra PeerFlood/FloodWait por conta e por ação.

Convites diretos deixam de ser tratados como uma função sempre disponível: se o
Telegram registrar PeerFlood, o Telegram Extractor bloqueia novas inclusões reais
por um período interno conservador. Análise, histórico, DRY RUN e geração de link
continuam disponíveis. A política não é um limite oficial do Telegram e não tenta
contornar seus mecanismos anti-spam.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from local_app_v18 import LoginWindowV18, LocalAppV18, _load_initial_entitlements
from saas_auth import SaaSAuthClient, SaaSAuthError
from safety_policy import compute_action_safety, format_local_datetime


class LocalAppV19(LocalAppV18):
    """V18 com bloqueio adaptativo e comunicação explícita de segurança."""

    def __init__(self, auth, entitlements):
        super().__init__(auth, entitlements)
        if not self.winfo_exists():
            return
        self._install_direct_safety_banner()
        self._sync_adaptive_safety_profile()
        self._refresh_safety_ui()

    # ------------------------------------------------------------------
    # Política derivada do histórico da conta ativa
    # ------------------------------------------------------------------
    def _action_safety(self, mode='direct'):
        if self.store is None:
            return compute_action_safety([], mode=mode)
        rows = (
            self.store.recent_message_history(1000)
            if mode == 'message'
            else self.store.recent_history(1000)
        )
        return compute_action_safety(rows, mode=mode)

    def _sync_adaptive_safety_profile(self):
        """Espelha a pausa calculada no card da conta sem depender de reinício."""
        if self.account_profiles is None:
            return
        profile = self._active_profile()
        if profile is None:
            return

        direct = self._action_safety('direct')
        messages = self._action_safety('message')

        if direct.blocked:
            kind_label = 'PEER_FLOOD' if direct.kind == 'peer_flood' else 'FLOOD_WAIT'
            until_text = format_local_datetime(direct.until)
            self.account_profiles.update(
                profile.id,
                status='peer_flood' if direct.kind == 'peer_flood' else 'cooldown',
                last_error=(
                    f'Convites diretos pausados por segurança após {kind_label}. '
                    f'Pausa interna até {until_text}. Análise e links continuam disponíveis.'
                ),
                cooldown_until=direct.until_iso,
            )
            self._refresh_accounts_tab()
            return

        if messages.blocked:
            kind_label = 'PEER_FLOOD' if messages.kind == 'peer_flood' else 'FLOOD_WAIT'
            until_text = format_local_datetime(messages.until)
            self.account_profiles.update(
                profile.id,
                status='peer_flood' if messages.kind == 'peer_flood' else 'cooldown',
                last_error=(
                    f'Mensagens opt-in pausadas por segurança após {kind_label} até {until_text}.'
                ),
                cooldown_until=messages.until_iso,
            )
            self._refresh_accounts_tab()
            return

        if profile.status in {'peer_flood', 'cooldown'}:
            self.account_profiles.update(
                profile.id,
                status='active' if self.service is not None else 'offline',
                last_error='',
                cooldown_until='',
            )
            self._refresh_accounts_tab()

    # ------------------------------------------------------------------
    # Aviso permanente na Operação
    # ------------------------------------------------------------------
    def _install_direct_safety_banner(self):
        controls_title = self._find_label('03 // Execution Protocol')
        if controls_title is None:
            controls_title = self._find_label('3. Segurança e ritmo')
        if controls_title is None:
            self.direct_safety_banner = None
            return

        controls = controls_title.master
        self.direct_safety_banner = ctk.CTkLabel(
            controls,
            text='',
            anchor='w',
            justify='left',
            wraplength=720,
            font=ctk.CTkFont(size=11, weight='bold'),
        )
        self.direct_safety_banner.grid(
            row=5,
            column=0,
            columnspan=3,
            sticky='ew',
            padx=16,
            pady=(0, 10),
        )

    def _refresh_safety_ui(self):
        direct = self._action_safety('direct')
        if direct.blocked:
            until_text = format_local_datetime(direct.until)
            if direct.kind == 'peer_flood':
                text = (
                    f'🔴 Convites diretos pausados até {until_text} · '
                    f'{direct.peer_flood_count} PeerFlood(s) recente(s). '
                    'Use análise ou Link convite enquanto a pausa estiver ativa.'
                )
            else:
                text = (
                    f'🟠 Convites diretos em FloodWait até {until_text}. '
                    'Nenhuma nova inclusão real será permitida antes desse horário.'
                )
            color = '#ef4444' if direct.kind == 'peer_flood' else '#f97316'
        elif direct.recovery_caution:
            text = (
                '🟡 Pausa de segurança encerrada. Retomada cautelosa: a primeira rodada real '
                'será limitada automaticamente a 1 participante.'
            )
            color = '#f59e0b'
        else:
            text = (
                '🟢 Convites diretos sem pausa interna ativa. Limites do Telegram continuam '
                'dinâmicos; Link convite é o método recomendado para entrada voluntária.'
            )
            color = '#22c55e'

        if getattr(self, 'direct_safety_banner', None) is not None:
            self.direct_safety_banner.configure(text=text, text_color=color)
        self._refresh_safety_button()

    def _refresh_safety_button(self):
        if not hasattr(self, 'start_button') or self.running:
            return
        direct = self._action_safety('direct')
        real_mode = not bool(self.dry_run_var.get())
        if direct.blocked and real_mode:
            self.start_button.configure(
                state='disabled',
                text='🔒 CONVITES DIRETOS PAUSADOS',
            )
            return

        try:
            self._refresh_primary_button()
        except Exception:
            pass
        can_start = self.service is not None and bool(self.dialog_map)
        self.start_button.configure(state='normal' if can_start else 'disabled')

    # ------------------------------------------------------------------
    # Saúde: mostra exatamente o que está pausado
    # ------------------------------------------------------------------
    def _health_state(self, profile, today, direct_cap, message_cap):
        direct = self._action_safety('direct')
        if direct.blocked:
            return (
                '🔴 CONVITES DIRETOS PAUSADOS',
                '#ef4444',
                (
                    f'Inclusões diretas bloqueadas pelo Telegram Extractor até '
                    f'{format_local_datetime(direct.until)} após {direct.kind.upper()}. '
                    'Análise de grupos, histórico, DRY RUN e links de convite continuam disponíveis.'
                ),
            )

        messages = self._action_safety('message')
        if messages.blocked:
            return (
                '🟠 MENSAGENS PAUSADAS',
                '#f97316',
                (
                    f'Mensagens opt-in pausadas até {format_local_datetime(messages.until)}. '
                    'Convites diretos são avaliados separadamente.'
                ),
            )

        if direct.recovery_caution:
            return (
                '🟡 RETOMADA CAUTELOSA',
                '#f59e0b',
                'A pausa interna terminou recentemente. A primeira rodada real será reduzida a 1 participante.',
            )
        return super()._health_state(profile, today, direct_cap, message_cap)

    def _refresh_health(self):
        super()._refresh_health()
        if hasattr(self, 'health_recommendation'):
            direct = self._action_safety('direct')
            if direct.blocked:
                suffix = (
                    '\nMétodo recomendado durante a pausa: gere um Link convite para entrada voluntária. '
                    'A pausa é uma proteção interna do Telegram Extractor, não um prazo oficial do Telegram.'
                )
                current = self.health_recommendation.cget('text') or ''
                if suffix.strip() not in current:
                    self.health_recommendation.configure(text=current + suffix)

    # ------------------------------------------------------------------
    # Bloqueios por ação; não usa rotação de contas para escapar de limite
    # ------------------------------------------------------------------
    def _real_action_block_reason(self):
        # A V19 faz a avaliação por tipo de ação abaixo. Evita que um PeerFlood
        # direto bloqueie, por acidente, recursos que não usam InviteToChannel.
        return ''

    def _start_run(self):
        if not self.dry_run_var.get():
            safety = self._action_safety('direct')
            if safety.blocked:
                messagebox.showwarning(
                    'Convites diretos pausados',
                    f'O Telegram Extractor bloqueou novas inclusões diretas até '
                    f'{format_local_datetime(safety.until)}.\n\n'
                    'Motivo: proteção após limitação do Telegram. '
                    'Análise, histórico e Link convite continuam disponíveis.\n\n'
                    'Não troque automaticamente de conta para tentar contornar esta pausa.',
                )
                self.tabs.set('Saúde')
                self._refresh_safety_ui()
                return

            if safety.recovery_caution:
                try:
                    requested = int(self.limit_var.get().strip())
                except Exception:
                    requested = 1
                if requested > 1:
                    self.limit_var.set('1')
                    messagebox.showinfo(
                        'Retomada cautelosa',
                        'A pausa de segurança terminou recentemente. Para proteger a conta, '
                        'esta primeira rodada real foi limitada a 1 participante.',
                    )
        super()._start_run()

    def _start_message_invites(self):
        if not self.dry_run_var.get():
            safety = self._action_safety('message')
            if safety.blocked:
                messagebox.showwarning(
                    'Mensagens temporariamente pausadas',
                    f'O envio de mensagens opt-in está pausado até '
                    f'{format_local_datetime(safety.until)} após limitação do Telegram.',
                )
                self.tabs.set('Saúde')
                return
            if safety.recovery_caution:
                try:
                    requested = int(self.message_limit_var.get().strip())
                except Exception:
                    requested = 1
                if requested > 1:
                    self.message_limit_var.set('1')
        super()._start_message_invites()

    def _review_peer_flood(self, profile):
        safety = self._action_safety('direct')
        if safety.blocked:
            messagebox.showinfo(
                'Pausa de segurança ativa',
                f'Esta pausa não pode ser liberada manualmente antes de '
                f'{format_local_datetime(safety.until)}.\n\n'
                'Ela foi calculada a partir do histórico real desta conta. '
                'Use análise, histórico ou Link convite enquanto aguarda.',
            )
            self.tabs.set('Saúde')
            return
        super()._review_peer_flood(profile)

    # ------------------------------------------------------------------
    # Recalcula a proteção sempre que o estado muda
    # ------------------------------------------------------------------
    def _record_rate_limit_from_history(self, message_mode=False):
        super()._record_rate_limit_from_history(message_mode=message_mode)
        self._sync_adaptive_safety_profile()
        self._refresh_safety_ui()
        self._refresh_health()

    def _after_connect(self, future):
        super()._after_connect(future)
        self._sync_adaptive_safety_profile()
        self._refresh_safety_ui()

    def _after_analyze(self, future):
        super()._after_analyze(future)
        self._refresh_safety_ui()

    def _after_run_v2(self, future):
        super()._after_run_v2(future)
        self._sync_adaptive_safety_profile()
        self._refresh_safety_ui()
        self._refresh_health()

    def _after_message_invites(self, future):
        super()._after_message_invites(future)
        self._sync_adaptive_safety_profile()
        self._refresh_safety_ui()
        self._refresh_health()

    def _on_dry_run_change(self):
        super()._on_dry_run_change()
        self._refresh_safety_ui()

    def _set_running_controls(self, running):
        super()._set_running_controls(running)
        if not running:
            self._refresh_safety_ui()


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

        app = LocalAppV19(auth, entitlements)
        app.mainloop()
        if app.request_logout:
            continue
        return


if __name__ == '__main__':
    main()
