import time

import customtkinter as ctk

from local_app_v5 import LocalAppV5
from ui_presenter import format_activity_line, parse_activity_status, status_bucket


class LocalAppV6(LocalAppV5):
    """Sexta versão da interface local com acabamento de produto.

    Mantém o backend validado e melhora apenas apresentação, feedback da rodada
    e clareza operacional.
    """

    def __init__(self):
        self.live_counts = {
            'processed': 0,
            'added': 0,
            'ignored': 0,
            'restrictions': 0,
            'errors': 0,
        }
        self._run_started_at = None
        super().__init__()
        if not self.winfo_exists():
            return

        self._apply_product_branding()
        self._install_route_banner()
        self._install_live_summary()
        self._refresh_route_banner()
        self._refresh_live_summary()
        self._refresh_primary_button()
        self._apply_mode_ui()

    def _walk_widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self._walk_widgets(child)

    def _apply_product_branding(self):
        self.title('AFILIAPULSE • Telegram Manager')
        replacements = {
            'Telegram Consent Invites': 'AFILIAPULSE • Telegram Manager',
            'Painel local de migração controlada': 'Gerenciamento local de participantes',
        }
        for widget in self._walk_widgets(self):
            if not isinstance(widget, ctk.CTkLabel):
                continue
            try:
                text = widget.cget('text')
            except Exception:
                continue
            if text in replacements:
                widget.configure(text=replacements[text])

    def _install_route_banner(self):
        actions = self.analyze_button.master
        self.route_banner = ctk.CTkLabel(
            actions,
            text='Escolha a rota de operação',
            text_color=('#1d4ed8', '#93c5fd'),
            font=ctk.CTkFont(size=13, weight='bold'),
            anchor='w',
        )
        self.route_banner.grid(
            row=1,
            column=0,
            columnspan=6,
            padx=(2, 8),
            pady=(7, 0),
            sticky='ew',
        )

    def _install_live_summary(self):
        # Coloca o resumo entre a barra de progresso e os cards de métricas.
        self.compact_metrics_frame.grid_configure(row=3, pady=(2, 8))
        self.live_summary_label = ctk.CTkLabel(
            self.progress_frame,
            text='',
            text_color=('gray35', 'gray70'),
            font=ctk.CTkFont(size=12),
            anchor='w',
        )
        self.live_summary_label.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=12,
            pady=(0, 2),
            sticky='ew',
        )

    def _refresh_route_banner(self):
        if not hasattr(self, 'route_banner'):
            return
        source = self.dialog_map.get(self.source_combo.get()) if self.dialog_map else None
        destination = self.dialog_map.get(self.destination_combo.get()) if self.dialog_map else None
        if source is None or destination is None or source.id == destination.id:
            self.route_banner.configure(text='Escolha uma origem e um destino diferentes')
            return
        self.route_banner.configure(
            text=f'ROTA ATUAL   {source.title}   →   {destination.title}'
        )

    def _refresh_live_summary(self):
        if not hasattr(self, 'live_summary_label'):
            return
        counts = self.live_counts
        self.live_summary_label.configure(
            text=(
                f'Processados {counts["processed"]}   ·   '
                f'✓ Adicionados {counts["added"]}   ·   '
                f'↪ Ignorados {counts["ignored"]}   ·   '
                f'⚠ Restrições {counts["restrictions"]}   ·   '
                f'✕ Erros {counts["errors"]}'
            )
        )

    def _reset_live_counts(self):
        for key in self.live_counts:
            self.live_counts[key] = 0
        self._refresh_live_summary()

    def _register_activity_status(self, status):
        self.live_counts['processed'] += 1
        bucket = status_bucket(status)
        if bucket == 'success':
            self.live_counts['added'] += 1
        elif bucket == 'ignored':
            self.live_counts['ignored'] += 1
        elif bucket == 'restriction':
            self.live_counts['restrictions'] += 1
        elif bucket == 'error':
            self.live_counts['errors'] += 1
        self._refresh_live_summary()

    def _append_log(self, text):
        parsed = parse_activity_status(text)
        if parsed:
            _name, status, _reason = parsed
            self._register_activity_status(status)
            text = format_activity_line(text)
        super()._append_log(text)

    def _refresh_primary_button(self):
        if not hasattr(self, 'start_button'):
            return
        if self.running:
            self.start_button.configure(text='RODADA EM ANDAMENTO', width=250)
            return
        if self.prepared is not None and self.prepared.queue:
            size = self._current_batch_size()
            noun = 'PARTICIPANTE' if size == 1 else 'PARTICIPANTES'
            self.start_button.configure(
                text=f'▶ INICIAR RODADA — {size} {noun}',
                width=250,
                font=ctk.CTkFont(size=12, weight='bold'),
            )
        else:
            self.start_button.configure(
                text='▶ INICIAR RODADA',
                width=210,
                font=ctk.CTkFont(size=12, weight='bold'),
            )

    def _apply_mode_ui(self):
        super()._apply_mode_ui()
        if not hasattr(self, 'mode_badge'):
            return
        if self.dry_run_var.get():
            self.mode_badge.configure(text='  MODO SEGURO · DRY RUN  ')
        else:
            self.mode_badge.configure(text='  MODO REAL · ENVIO ATIVO  ')

    def _on_limit_changed(self, *args):
        super()._on_limit_changed(*args)
        self._refresh_primary_button()

    def _on_route_changed(self, reason):
        super()._on_route_changed(reason)
        self._refresh_route_banner()
        self._refresh_primary_button()

    def _restore_last_route(self):
        super()._restore_last_route()
        self._refresh_route_banner()
        self._refresh_primary_button()

    def _after_connect(self, future):
        super()._after_connect(future)
        self._refresh_route_banner()
        self._refresh_primary_button()

    def _after_analyze(self, future):
        super()._after_analyze(future)
        self._refresh_route_banner()
        self._refresh_primary_button()

    def _invalidate_prepared(self, reason='Configuração alterada.', log=True):
        super()._invalidate_prepared(reason=reason, log=log)
        self._refresh_route_banner()
        self._refresh_primary_button()

    def _start_run(self):
        self._reset_live_counts()
        self._run_started_at = None
        super()._start_run()
        if self.running:
            self._run_started_at = time.monotonic()
            self._refresh_primary_button()

    def _set_running_controls(self, running):
        super()._set_running_controls(running)
        self._refresh_primary_button()

    def _after_run_v2(self, future):
        self.running = False
        self.pause_event.clear()
        self.stop_event.clear()
        self._set_countdown('')

        duration = 0.0
        if self._run_started_at is not None:
            duration = max(0.0, time.monotonic() - self._run_started_at)
        self._run_started_at = None

        try:
            stats, report_path, prepared, was_dry_run = future.result()
        except Exception as exc:
            self._set_running_controls(False)
            self._set_status('Rodada encerrada com erro.')
            self._append_log(f'ERRO: {type(exc).__name__}: {exc}')
            self._reset_progress()
            self._show_error_dialog(exc)
            return

        self.prepared = prepared
        self._show_prepared(prepared)
        self._refresh_history()

        self._set_status('Rodada concluída.')
        self.progress_title.configure(text=f'Rodada concluída · {stats.processed} processados')
        self._append_log(
            'Rodada concluída. '
            f'Processados={stats.processed}; adicionados={stats.added}; '
            f'privacidade={stats.privacy}; rate limit={stats.rate_limited}; '
            f'erros={stats.errors}.'
        )
        if report_path:
            self._append_log(f'Relatório CSV: {report_path}')

        # Uma rodada real nunca deixa a próxima execução armada.
        if not was_dry_run:
            self.dry_run_var.set(True)
            self.dry_switch.select()
            self.consent_var.set(False)
            self._apply_mode_ui()
            self._append_log('Segurança: interface retornou automaticamente ao DRY RUN após a rodada real.')

        self._set_running_controls(False)
        self.start_button.configure(state='normal' if prepared.queue else 'disabled')
        self._refresh_primary_button()
        self._refresh_live_summary()
        self._show_round_summary(stats, report_path, duration, was_dry_run)

    def _show_error_dialog(self, exc):
        from tkinter import messagebox
        messagebox.showerror('Rodada', f'A execução falhou:\n{exc}')

    @staticmethod
    def _format_duration(seconds):
        total = max(0, int(round(seconds)))
        minutes, secs = divmod(total, 60)
        if minutes:
            return f'{minutes}m {secs:02d}s'
        return f'{secs}s'

    def _show_round_summary(self, stats, report_path, duration, was_dry_run):
        dialog = ctk.CTkToplevel(self)
        dialog.title('Rodada concluída')
        dialog.geometry('470x410')
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        mode = 'DRY RUN' if was_dry_run else 'MODO REAL'
        ctk.CTkLabel(
            dialog,
            text='Rodada concluída',
            font=ctk.CTkFont(size=24, weight='bold'),
        ).pack(pady=(24, 2))
        ctk.CTkLabel(
            dialog,
            text=mode,
            text_color=('gray40', 'gray70'),
            font=ctk.CTkFont(size=12, weight='bold'),
        ).pack(pady=(0, 18))

        grid = ctk.CTkFrame(dialog, corner_radius=12)
        grid.pack(fill='x', padx=28, pady=4)
        rows = [
            ('Processados', stats.processed),
            ('✓ Adicionados', stats.added),
            ('↪ Já membros / ignorados', stats.already_member + stats.skipped),
            ('⚠ Privacidade / restrições', stats.privacy + stats.permissions + stats.rate_limited),
            ('✕ Erros', stats.errors),
            ('Duração', self._format_duration(duration)),
        ]
        for row, (label, value) in enumerate(rows):
            ctk.CTkLabel(grid, text=label, anchor='w').grid(
                row=row, column=0, padx=18, pady=7, sticky='w'
            )
            ctk.CTkLabel(
                grid,
                text=str(value),
                font=ctk.CTkFont(size=14, weight='bold'),
            ).grid(row=row, column=1, padx=18, pady=7, sticky='e')
        grid.grid_columnconfigure(0, weight=1)

        if report_path:
            ctk.CTkLabel(
                dialog,
                text=f'Relatório salvo em: {report_path}',
                text_color=('gray45', 'gray65'),
                wraplength=410,
                font=ctk.CTkFont(size=11),
            ).pack(padx=24, pady=(12, 8))

        buttons = ctk.CTkFrame(dialog, fg_color='transparent')
        buttons.pack(fill='x', padx=28, pady=(8, 22))
        buttons.grid_columnconfigure((0, 1), weight=1)

        def open_history():
            dialog.destroy()
            self.tabs.set('Histórico')

        ctk.CTkButton(buttons, text='Fechar', command=dialog.destroy).grid(
            row=0, column=0, padx=(0, 6), sticky='ew'
        )
        ctk.CTkButton(buttons, text='Ver histórico', command=open_history).grid(
            row=0, column=1, padx=(6, 0), sticky='ew'
        )


if __name__ == '__main__':
    app = LocalAppV6()
    app.mainloop()
