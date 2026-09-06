import asyncio
import random
from tkinter import messagebox

import customtkinter as ctk

from local_app import LocalApp, MAX_GUI_BATCH, MIN_REAL_DELAY_SECONDS, TrackingReport
from migrator import MigrationEngine
from models import MigrationStats
from report import ReportWriter
from utils import full_name

SAFE_COLOR = '#22c55e'
REAL_COLOR = '#ef4444'


class LocalAppV2(LocalApp):
    """Segunda versão visual da interface local.

    Mantém o backend já validado e adiciona sinais de segurança mais fortes,
    progresso da rodada e contagem regressiva entre tentativas.
    """

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        # Fail-safe de sessão: a GUI sempre abre em DRY RUN, independentemente do .env.
        self.dry_run_var.set(True)
        self.consent_var.set(False)
        self.dry_switch.select()

        self.mode_badge = ctk.CTkLabel(
            self,
            text='  MODO SEGURO · DRY RUN  ',
            fg_color=SAFE_COLOR,
            text_color='#07140b',
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight='bold'),
        )
        self.mode_badge.place(relx=0.5, y=18, anchor='n')

        self._install_progress_panel()
        self._install_route_guards()
        self._apply_mode_ui()
        self._reset_progress()
        self.start_button.configure(text='▶ Iniciar rodada', state='disabled')
        self.pause_button.configure(text='⏸ Pausar')
        self.stop_button.configure(text='■ Parar')

    def _install_progress_panel(self):
        tab = self.tabs.tab('Operação')

        # Abre espaço entre ações e métricas sem reescrever toda a tela base.
        for child in tab.winfo_children():
            info = child.grid_info()
            if not info or 'row' not in info:
                continue
            row = int(info['row'])
            if row >= 3:
                child.grid_configure(row=row + 1)

        tab.grid_rowconfigure(5, weight=1)
        self.progress_frame = ctk.CTkFrame(tab, corner_radius=12)
        self.progress_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=(2, 8), sticky='ew')
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_title = ctk.CTkLabel(
            self.progress_frame,
            text='Nenhuma rodada em execução',
            font=ctk.CTkFont(size=14, weight='bold'),
        )
        self.progress_title.grid(row=0, column=0, padx=16, pady=(10, 4), sticky='w')

        self.countdown_label = ctk.CTkLabel(
            self.progress_frame,
            text='',
            text_color=('gray40', 'gray70'),
        )
        self.countdown_label.grid(row=0, column=1, padx=16, pady=(10, 4), sticky='e')

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12)
        self.progress_bar.grid(row=1, column=0, columnspan=2, padx=16, pady=(2, 12), sticky='ew')
        self.progress_bar.set(0)

    def _install_route_guards(self):
        self.source_combo.configure(command=lambda _: self._invalidate_prepared('Origem alterada.'))
        self.destination_combo.configure(command=lambda _: self._invalidate_prepared('Destino alterado.'))

    def _invalidate_prepared(self, reason='Configuração alterada.', log=True):
        if self.running:
            return
        self.prepared = None
        self.consent_var.set(False)
        self.start_button.configure(state='disabled')
        self._reset_progress()
        self._set_status(reason)
        if log:
            self._append_log(reason + ' Reanalise a fila antes de iniciar.')

    def _after_connect(self, future):
        super()._after_connect(future)
        if self.connection_badge.cget('text') == '● Conectado':
            self.start_button.configure(state='disabled')
            self.consent_var.set(False)
            self._reset_progress()

    def _analyze_queue(self):
        self.consent_var.set(False)
        self.prepared = None
        self.start_button.configure(state='disabled')
        self._reset_progress()
        super()._analyze_queue()

    def _after_analyze(self, future):
        super()._after_analyze(future)
        if self.prepared is not None:
            self.start_button.configure(state='normal' if self.prepared.queue else 'disabled')
            self.consent_var.set(False)

    def _on_dry_run_change(self):
        self.consent_var.set(False)
        self._apply_mode_ui()
        if self.dry_run_var.get():
            self.consent_check.configure(state='disabled')
        else:
            self.consent_check.configure(state='normal')
            messagebox.showwarning(
                'Modo real ativado',
                'MODO REAL pode enviar convites.\n\n'
                'Nada será executado até você marcar a autorização e confirmar a rodada.',
            )
        self._invalidate_prepared('Modo de execução alterado.', log=False)

    def _apply_mode_ui(self):
        if not hasattr(self, 'mode_badge'):
            return
        if self.dry_run_var.get():
            self.mode_badge.configure(
                text='  MODO SEGURO · DRY RUN  ',
                fg_color=SAFE_COLOR,
                text_color='#07140b',
            )
            self.start_button.configure(fg_color='#1f6aa5', hover_color='#144870')
        else:
            self.mode_badge.configure(
                text='  MODO REAL · ENVIA CONVITES  ',
                fg_color=REAL_COLOR,
                text_color='white',
            )
            self.start_button.configure(fg_color='#b91c1c', hover_color='#991b1b')

    def _start_run(self):
        if self.running:
            return
        if self.prepared is None:
            messagebox.showwarning('Fila', 'Analise a fila antes de iniciar uma rodada.')
            return

        try:
            source, destination = self._selected_route()
            limit, min_delay, max_delay = self._read_run_controls()
        except Exception as exc:
            messagebox.showwarning('Configuração da rodada', str(exc))
            return

        if source.id != self.prepared.source.id or destination.id != self.prepared.destination.id:
            self._invalidate_prepared('Origem ou destino mudou.')
            messagebox.showwarning('Fila desatualizada', 'A rota mudou. Analise a fila novamente.')
            return

        dry_run = bool(self.dry_run_var.get())
        if not dry_run and not self.consent_var.get():
            messagebox.showwarning(
                'Confirmação necessária',
                'Marque a confirmação de autorização antes de uma rodada real.',
            )
            return

        mode = 'DRY RUN' if dry_run else 'REAL'
        batch_size = min(limit, len(self.prepared.queue))
        if not dry_run:
            confirmed = messagebox.askyesno(
                'CONFIRMAR RODADA REAL',
                'ATENÇÃO: esta rodada enviará tentativas reais.\n\n'
                f'Origem: {source.title}\n'
                f'Destino: {destination.title}\n'
                f'Quantidade máxima: {batch_size}\n'
                f'Intervalo operacional: {min_delay:g}–{max_delay:g} s\n\n'
                'A fila exclui admins/owner, bots, bloqueados, membros presentes '
                'e usuários já processados.\n\nDeseja continuar?',
            )
            if not confirmed:
                return

        self.running = True
        self.stop_event.clear()
        self.pause_event.clear()
        self._set_running_controls(True)
        self._set_progress(0, batch_size, 'Preparando rodada...')
        self._set_status(f'Rodada {mode} em preparação...')
        self._append_log(f'Iniciando rodada {mode} com limite {limit}.')

        self._submit(
            self._run_batch_v2(source, destination, limit, min_delay, max_delay, dry_run),
            self._after_run_v2,
        )

    async def _run_batch_v2(self, source, destination, limit, min_delay, max_delay, dry_run):
        prepared = await self._prepare_queue(source, destination)
        batch = prepared.queue[:limit]
        if not batch:
            return MigrationStats(), None, prepared, dry_run

        report = ReportWriter()
        total = MigrationStats()

        def on_result(user_id, username, name, status, reason):
            self.store.record_attempt(
                source.id,
                destination.id,
                user_id,
                username,
                name,
                status,
                reason,
            )
            self._ui(
                lambda: self._append_log(
                    f'{name or user_id}: {status}' + (f' — {reason}' if reason else '')
                )
            )

        tracking_report = TrackingReport(report, on_result)

        try:
            for index, user in enumerate(batch, start=1):
                while self.pause_event.is_set() and not self.stop_event.is_set():
                    await asyncio.sleep(0.25)
                if self.stop_event.is_set():
                    total.stopped = True
                    break

                self._ui(
                    lambda i=index, u=user: self._set_progress(
                        i - 1,
                        len(batch),
                        f'Processando {i}/{len(batch)} · {full_name(u)}',
                    )
                )

                engine = MigrationEngine(
                    self.service.client,
                    destination.entity,
                    max_invites=1,
                    min_delay=0,
                    max_delay=0,
                )
                stats = await engine.run([user], tracking_report, dry_run=dry_run)
                self._merge_stats(total, stats)
                self._ui(
                    lambda i=index: self._set_progress(
                        i,
                        len(batch),
                        f'Concluído {i}/{len(batch)}',
                    )
                )

                if stats.permissions or stats.rate_limited or stats.stopped:
                    total.stopped = True
                    break

                if not dry_run and index < len(batch) and not self.stop_event.is_set():
                    delay = random.uniform(min_delay, max_delay)
                    remaining = delay
                    while remaining > 0:
                        if self.stop_event.is_set():
                            total.stopped = True
                            break

                        while self.pause_event.is_set() and not self.stop_event.is_set():
                            self._ui(lambda: self._set_countdown('Pausado'))
                            await asyncio.sleep(0.25)

                        if self.stop_event.is_set():
                            break

                        self._ui(
                            lambda r=remaining: self._set_countdown(
                                f'Próxima tentativa em {max(0, int(r + 0.999))} s'
                            )
                        )
                        step = min(1.0, remaining)
                        await asyncio.sleep(step)
                        remaining -= step

                    self._ui(lambda: self._set_countdown(''))
                    if self.stop_event.is_set():
                        break
        finally:
            report.close()

        return total, str(report.path), prepared, dry_run

    def _after_run_v2(self, future):
        self.running = False
        self.pause_event.clear()
        self.stop_event.clear()
        self._set_countdown('')

        try:
            stats, report_path, prepared, was_dry_run = future.result()
        except Exception as exc:
            self._set_running_controls(False)
            self._set_status('Rodada encerrada com erro.')
            self._append_log(f'ERRO: {type(exc).__name__}: {exc}')
            self._reset_progress()
            messagebox.showerror('Rodada', f'A execução falhou:\n{exc}')
            return

        self.prepared = prepared
        self._show_prepared(prepared)
        self._refresh_history()

        summary = (
            f'Processados={stats.processed} · Adicionados={stats.added} · '
            f'Privacidade={stats.privacy} · Rate limit={stats.rate_limited} · '
            f'Erros={stats.errors}'
        )
        self._set_status('Rodada concluída.')
        self.progress_title.configure(text=f'Rodada concluída · {stats.processed} processados')
        self._append_log(f'Rodada concluída. {summary}.')
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
        messagebox.showinfo(
            'Rodada concluída',
            f'{summary}\n\nRelatório: {report_path or "nenhum (fila vazia)"}',
        )

    def _set_running_controls(self, running):
        state = 'disabled' if running else 'normal'
        self.connect_button.configure(state=state)
        self.analyze_button.configure(state=state)
        self.source_combo.configure(state=state)
        self.destination_combo.configure(state=state)
        self.dry_switch.configure(state=state)
        self.consent_check.configure(
            state='disabled' if running or self.dry_run_var.get() else 'normal'
        )
        self.start_button.configure(
            state='disabled' if running else (
                'normal' if self.prepared is not None and self.prepared.queue else 'disabled'
            )
        )
        self.pause_button.configure(state='normal' if running else 'disabled')
        self.stop_button.configure(state='normal' if running else 'disabled')
        if not running:
            self.pause_button.configure(text='⏸ Pausar')

    def _toggle_pause(self):
        if not self.running:
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text='⏸ Pausar')
            self._set_status('Retomando a rodada...')
            self._append_log('Rodada retomada.')
        else:
            self.pause_event.set()
            self.pause_button.configure(text='▶ Retomar')
            self._set_status('Pausado entre tentativas.')
            self._set_countdown('Pausado')
            self._append_log('Pausa solicitada. A tentativa em andamento não é interrompida.')

    def _stop_run(self):
        if self.running:
            self.stop_event.set()
            self._set_status('Parada solicitada...')
            self._set_countdown('Parando...')
            self._append_log('Parada solicitada. Nenhuma nova tentativa será iniciada.')

    def _reset_progress(self):
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set(0)
            self.progress_title.configure(text='Nenhuma rodada em execução')
            self.countdown_label.configure(text='')

    def _set_progress(self, current, total, text=None):
        ratio = 0 if total <= 0 else max(0.0, min(1.0, current / total))
        self.progress_bar.set(ratio)
        self.progress_title.configure(text=text or f'Progresso {current}/{total}')

    def _set_countdown(self, text):
        if hasattr(self, 'countdown_label'):
            self.countdown_label.configure(text=text)


if __name__ == '__main__':
    app = LocalAppV2()
    app.mainloop()
