import asyncio
import random
import threading
from dataclasses import dataclass
from tkinter import messagebox

import customtkinter as ctk

from config import Settings
from extractor import save_members
from migrator import MigrationEngine, classify_candidates
from models import MigrationStats
from report import ReportWriter
from state_store import StateStore
from telegram_client import TelegramService
from utils import full_name


APP_TITLE = 'Telegram Consent Invites — Local'
MAX_GUI_BATCH = 20
MIN_REAL_DELAY_SECONDS = 15.0


class AsyncRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


@dataclass
class PreparedQueue:
    source: object
    destination: object
    members: list
    queue: list
    extracted: int
    admins: int
    bots: int
    excluded: int
    already_destination: int
    previously_processed: int
    json_path: str
    csv_path: str


class TrackingReport:
    def __init__(self, base_report, callback):
        self.base_report = base_report
        self.callback = callback

    def write(self, user_id, username, name, status, reason=''):
        self.base_report.write(user_id, username, name, status, reason)
        self.callback(user_id, username, name, status, reason)


class LocalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')

        self.title(APP_TITLE)
        self.geometry('1240x820')
        self.minsize(1080, 720)

        try:
            self.settings = Settings.load(require_explicit_targets=False)
        except Exception as exc:
            messagebox.showerror(
                'Configuração inválida',
                f'{exc}\n\nRevise o arquivo .env e abra a interface novamente.',
            )
            self.after(50, self.destroy)
            return

        self.store = StateStore()
        self.runtime = AsyncRuntime()
        self.service = None
        self.dialogs = []
        self.dialog_map = {}
        self.prepared = None
        self.running = False
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

        self.dry_run_var = ctk.BooleanVar(value=True)
        self.consent_var = ctk.BooleanVar(value=False)
        self.limit_var = ctk.StringVar(value=str(min(self.settings.max_invites_per_run, MAX_GUI_BATCH)))
        self.min_delay_var = ctk.StringVar(value=str(max(self.settings.min_delay_seconds, MIN_REAL_DELAY_SECONDS)))
        self.max_delay_var = ctk.StringVar(
            value=str(max(self.settings.max_delay_seconds, self.settings.min_delay_seconds, MIN_REAL_DELAY_SECONDS))
        )

        self._build_ui()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._refresh_history()
        self._refresh_exclusions()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0, height=74)
        header.grid(row=0, column=0, sticky='ew')
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text='Telegram Consent Invites',
            font=ctk.CTkFont(size=24, weight='bold'),
        ).grid(row=0, column=0, padx=(26, 10), pady=(13, 0), sticky='w')
        ctk.CTkLabel(
            header,
            text='Painel local de migração controlada',
            text_color=('gray40', 'gray70'),
            font=ctk.CTkFont(size=13),
        ).grid(row=1, column=0, padx=(26, 10), pady=(0, 10), sticky='w')

        self.connection_badge = ctk.CTkLabel(
            header,
            text='● Desconectado',
            text_color='#f59e0b',
            font=ctk.CTkFont(size=14, weight='bold'),
        )
        self.connection_badge.grid(row=0, column=2, rowspan=2, padx=26, sticky='e')

        self.tabs = ctk.CTkTabview(self, corner_radius=14)
        self.tabs.grid(row=1, column=0, padx=18, pady=18, sticky='nsew')
        self.tabs.add('Operação')
        self.tabs.add('Histórico')
        self.tabs.add('Exclusões')

        self._build_operation_tab()
        self._build_history_tab()
        self._build_exclusions_tab()

    def _build_operation_tab(self):
        tab = self.tabs.tab('Operação')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        connection = self._card(tab, '1. Conexão com o Telegram', 0, 0, colspan=2)
        connection.grid_columnconfigure(1, weight=1)
        self.connect_button = ctk.CTkButton(
            connection,
            text='Conectar / atualizar grupos',
            command=self._connect,
            width=210,
        )
        self.connect_button.grid(row=1, column=0, padx=16, pady=(6, 16), sticky='w')
        self.account_label = ctk.CTkLabel(
            connection,
            text='Sessão local ainda não conectada.',
            text_color=('gray40', 'gray70'),
        )
        self.account_label.grid(row=1, column=1, padx=16, pady=(6, 16), sticky='w')

        route = self._card(tab, '2. Origem e destino', 1, 0)
        route.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(route, text='Grupo A — origem').grid(row=1, column=0, padx=16, pady=(4, 3), sticky='w')
        self.source_combo = ctk.CTkComboBox(route, values=['Conecte ao Telegram primeiro'], state='disabled')
        self.source_combo.grid(row=2, column=0, padx=16, pady=(0, 10), sticky='ew')
        ctk.CTkLabel(route, text='Grupo B — destino').grid(row=3, column=0, padx=16, pady=(2, 3), sticky='w')
        self.destination_combo = ctk.CTkComboBox(route, values=['Conecte ao Telegram primeiro'], state='disabled')
        self.destination_combo.grid(row=4, column=0, padx=16, pady=(0, 16), sticky='ew')

        controls = self._card(tab, '3. Segurança e ritmo', 1, 1)
        controls.grid_columnconfigure((0, 1, 2), weight=1)
        self.dry_switch = ctk.CTkSwitch(
            controls,
            text='DRY RUN (sem enviar)',
            variable=self.dry_run_var,
            command=self._on_dry_run_change,
        )
        self.dry_switch.grid(row=1, column=0, columnspan=3, padx=16, pady=(4, 10), sticky='w')
        self.dry_switch.select()

        ctk.CTkLabel(controls, text=f'Limite da rodada (1–{MAX_GUI_BATCH})').grid(
            row=2, column=0, padx=(16, 5), sticky='w'
        )
        ctk.CTkLabel(controls, text='Intervalo mín. (s)').grid(row=2, column=1, padx=5, sticky='w')
        ctk.CTkLabel(controls, text='Intervalo máx. (s)').grid(row=2, column=2, padx=(5, 16), sticky='w')

        ctk.CTkEntry(controls, textvariable=self.limit_var).grid(row=3, column=0, padx=(16, 5), pady=(3, 8), sticky='ew')
        ctk.CTkEntry(controls, textvariable=self.min_delay_var).grid(row=3, column=1, padx=5, pady=(3, 8), sticky='ew')
        ctk.CTkEntry(controls, textvariable=self.max_delay_var).grid(row=3, column=2, padx=(5, 16), pady=(3, 8), sticky='ew')

        self.consent_check = ctk.CTkCheckBox(
            controls,
            text='Confirmo que tenho autorização no destino e para esta fila.',
            variable=self.consent_var,
            state='disabled',
        )
        self.consent_check.grid(row=4, column=0, columnspan=3, padx=16, pady=(4, 16), sticky='w')

        actions = ctk.CTkFrame(tab, fg_color='transparent')
        actions.grid(row=2, column=0, columnspan=2, padx=4, pady=(2, 10), sticky='ew')
        actions.grid_columnconfigure(5, weight=1)

        self.analyze_button = ctk.CTkButton(actions, text='Analisar fila', command=self._analyze_queue, state='disabled')
        self.analyze_button.grid(row=0, column=0, padx=(0, 8))
        self.start_button = ctk.CTkButton(
            actions,
            text='Iniciar rodada automática',
            command=self._start_run,
            state='disabled',
        )
        self.start_button.grid(row=0, column=1, padx=8)
        self.pause_button = ctk.CTkButton(
            actions,
            text='Pausar',
            command=self._toggle_pause,
            fg_color='#7c3aed',
            hover_color='#6d28d9',
            state='disabled',
            width=110,
        )
        self.pause_button.grid(row=0, column=2, padx=8)
        self.stop_button = ctk.CTkButton(
            actions,
            text='Parar',
            command=self._stop_run,
            fg_color='#b91c1c',
            hover_color='#991b1b',
            state='disabled',
            width=100,
        )
        self.stop_button.grid(row=0, column=3, padx=8)

        self.run_status = ctk.CTkLabel(
            actions,
            text='Pronto para conectar.',
            text_color=('gray40', 'gray70'),
        )
        self.run_status.grid(row=0, column=5, padx=8, sticky='e')

        metrics = ctk.CTkFrame(tab, fg_color='transparent')
        metrics.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        for i in range(6):
            metrics.grid_columnconfigure(i, weight=1)

        self.metric_labels = {}
        metric_names = [
            ('extraidos', 'Extraídos'),
            ('admins', 'Admins'),
            ('destino', 'Já no destino'),
            ('processados', 'Já processados'),
            ('fila', 'Fila disponível'),
            ('rodada', 'Nesta rodada'),
        ]
        for col, (key, title) in enumerate(metric_names):
            card = ctk.CTkFrame(metrics, corner_radius=12)
            card.grid(row=0, column=col, padx=4, sticky='ew')
            value = ctk.CTkLabel(card, text='—', font=ctk.CTkFont(size=22, weight='bold'))
            value.pack(pady=(10, 0))
            ctk.CTkLabel(card, text=title, text_color=('gray40', 'gray70')).pack(pady=(0, 10))
            self.metric_labels[key] = value

        queue_card = self._card(tab, 'Fila automática', 4, 0)
        queue_card.grid_rowconfigure(1, weight=1)
        queue_card.grid_columnconfigure(0, weight=1)
        self.queue_box = ctk.CTkTextbox(queue_card, wrap='none')
        self.queue_box.grid(row=1, column=0, padx=16, pady=(6, 16), sticky='nsew')
        self.queue_box.insert('end', 'Analise a fila para visualizar os primeiros candidatos elegíveis.\n')
        self.queue_box.configure(state='disabled')

        log_card = self._card(tab, 'Atividade', 4, 1)
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(log_card, wrap='word')
        self.log_box.grid(row=1, column=0, padx=16, pady=(6, 16), sticky='nsew')
        self.log_box.configure(state='disabled')

    def _build_history_tab(self):
        tab = self.tabs.tab('Histórico')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, fg_color='transparent')
        top.grid(row=0, column=0, sticky='ew', pady=(4, 10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text='Últimas tentativas', font=ctk.CTkFont(size=20, weight='bold')).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(top, text='Atualizar', width=110, command=self._refresh_history).grid(row=0, column=2, sticky='e')

        self.history_frame = ctk.CTkScrollableFrame(tab)
        self.history_frame.grid(row=1, column=0, sticky='nsew')
        self.history_frame.grid_columnconfigure(0, weight=1)

    def _build_exclusions_tab(self):
        tab = self.tabs.tab('Exclusões')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            tab,
            text='Usuários bloqueados nunca entram na fila automática.',
            font=ctk.CTkFont(size=18, weight='bold'),
        ).grid(row=0, column=0, pady=(8, 12), sticky='w')

        form = ctk.CTkFrame(tab)
        form.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)
        self.exclusion_id = ctk.CTkEntry(form, placeholder_text='user_id')
        self.exclusion_id.grid(row=0, column=0, padx=(14, 6), pady=14)
        self.exclusion_note = ctk.CTkEntry(form, placeholder_text='Motivo / observação')
        self.exclusion_note.grid(row=0, column=1, padx=6, pady=14, sticky='ew')
        ctk.CTkButton(form, text='Adicionar exclusão', command=self._add_exclusion).grid(
            row=0, column=2, padx=(6, 14), pady=14
        )

        self.exclusions_frame = ctk.CTkScrollableFrame(tab)
        self.exclusions_frame.grid(row=2, column=0, sticky='nsew')
        self.exclusions_frame.grid_columnconfigure(0, weight=1)

    def _card(self, parent, title, row, column, colspan=1):
        frame = ctk.CTkFrame(parent, corner_radius=14)
        frame.grid(row=row, column=column, columnspan=colspan, padx=5, pady=5, sticky='nsew')
        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=17, weight='bold'),
        ).grid(row=0, column=0, columnspan=5, padx=16, pady=(14, 6), sticky='w')
        return frame

    def _connect(self):
        self.connect_button.configure(state='disabled')
        self._set_status('Conectando ao Telegram...')
        self._append_log('Conectando à sessão local do Telegram...')

        async def work():
            if self.service is None:
                self.service = TelegramService(
                    self.settings.api_id,
                    self.settings.api_hash,
                    self.settings.session,
                )
            me = await self.service.connect()
            dialogs = await self.service.list_dialogs()
            return me, dialogs

        self._submit(work(), self._after_connect)

    def _after_connect(self, future):
        self.connect_button.configure(state='normal')
        try:
            me, dialogs = future.result()
        except Exception as exc:
            self.connection_badge.configure(text='● Erro de conexão', text_color='#ef4444')
            self._set_status('Falha ao conectar.')
            self._append_log(f'ERRO: {type(exc).__name__}: {exc}')
            messagebox.showerror('Telegram', f'Não foi possível conectar:\n{exc}')
            return

        self.dialogs = dialogs
        self.dialog_map = {}
        values = []
        for index, dialog in enumerate(dialogs, start=1):
            label = f'{index:02d} · {dialog.title}'
            values.append(label)
            self.dialog_map[label] = dialog

        self.source_combo.configure(values=values, state='normal')
        self.destination_combo.configure(values=values, state='normal')
        if values:
            self.source_combo.set(values[0])
            self.destination_combo.set(values[1] if len(values) > 1 else values[0])

        self.account_label.configure(text=f'Conectado como {full_name(me)} · {len(dialogs)} grupos/canais acessíveis')
        self.connection_badge.configure(text='● Conectado', text_color='#22c55e')
        self.analyze_button.configure(state='normal')
        self.start_button.configure(state='normal')
        self._set_status('Conectado. Escolha origem e destino.')
        self._append_log(f'Conexão concluída. {len(dialogs)} grupos/canais carregados.')

    def _selected_route(self):
        source = self.dialog_map.get(self.source_combo.get())
        destination = self.dialog_map.get(self.destination_combo.get())
        if source is None or destination is None:
            raise ValueError('Selecione origem e destino.')
        if source.id == destination.id:
            raise ValueError('Origem e destino não podem ser iguais.')
        return source, destination

    def _analyze_queue(self):
        try:
            source, destination = self._selected_route()
        except Exception as exc:
            messagebox.showwarning('Rota', str(exc))
            return

        self.analyze_button.configure(state='disabled')
        self._set_status('Analisando participantes...')
        self._append_log(f'Analisando: {source.title} → {destination.title}')

        self._submit(self._prepare_queue(source, destination), self._after_analyze)

    async def _prepare_queue(self, source, destination):
        members = await self.service.get_members(source.entity)
        if not members:
            raise RuntimeError('Nenhum participante acessível foi encontrado na origem.')

        json_path, csv_path, records = save_members(members, source.entity)
        source_admin_ids = await self.service.get_admin_ids(source.entity)
        destination_ids = await self.service.get_member_ids(destination.entity)

        excluded_ids = set(self.settings.excluded_user_ids) | self.store.excluded_ids()
        admins, bots, excluded, already_members, eligible = classify_candidates(
            members,
            destination_ids,
            source_admin_ids,
            excluded_ids,
        )

        processed = self.store.processed_ids(source.id, destination.id)
        queue = [user for user in eligible if user.id not in processed]

        return PreparedQueue(
            source=source,
            destination=destination,
            members=members,
            queue=queue,
            extracted=len(records),
            admins=len(admins),
            bots=len(bots),
            excluded=len(excluded),
            already_destination=len(already_members),
            previously_processed=len([u for u in eligible if u.id in processed]),
            json_path=str(json_path),
            csv_path=str(csv_path),
        )

    def _after_analyze(self, future):
        self.analyze_button.configure(state='normal')
        try:
            prepared = future.result()
        except Exception as exc:
            self._set_status('Falha na análise.')
            self._append_log(f'ERRO na análise: {type(exc).__name__}: {exc}')
            messagebox.showerror('Análise', f'Não foi possível preparar a fila:\n{exc}')
            return

        self.prepared = prepared
        self._show_prepared(prepared)
        self._set_status(f'Fila pronta: {len(prepared.queue)} candidatos disponíveis.')
        self._append_log(
            f'Fila preparada. Extraídos={prepared.extracted}; admins={prepared.admins}; '
            f'bots={prepared.bots}; exclusões={prepared.excluded}; '
            f'já no destino={prepared.already_destination}; '
            f'já processados={prepared.previously_processed}; pendentes={len(prepared.queue)}.'
        )

    def _show_prepared(self, prepared):
        self.metric_labels['extraidos'].configure(text=str(prepared.extracted))
        self.metric_labels['admins'].configure(text=str(prepared.admins))
        self.metric_labels['destino'].configure(text=str(prepared.already_destination))
        self.metric_labels['processados'].configure(text=str(prepared.previously_processed))
        self.metric_labels['fila'].configure(text=str(len(prepared.queue)))

        try:
            batch_limit, _, _ = self._read_run_controls()
        except Exception:
            batch_limit = min(self.settings.max_invites_per_run, MAX_GUI_BATCH)
        self.metric_labels['rodada'].configure(text=str(min(batch_limit, len(prepared.queue))))

        self.queue_box.configure(state='normal')
        self.queue_box.delete('1.0', 'end')
        if not prepared.queue:
            self.queue_box.insert('end', 'Nenhum candidato pendente para esta rota.\n')
        else:
            preview = prepared.queue[:30]
            for index, user in enumerate(preview, start=1):
                username = f'@{user.username}' if getattr(user, 'username', None) else 'sem username'
                self.queue_box.insert(
                    'end',
                    f'{index:02d}. {full_name(user)} · {username} · ID {user.id}\n',
                )
            if len(prepared.queue) > len(preview):
                self.queue_box.insert('end', f'\n… e mais {len(prepared.queue) - len(preview)} candidatos.\n')
        self.queue_box.configure(state='disabled')

    def _read_run_controls(self):
        try:
            limit = int(self.limit_var.get().strip())
            min_delay = float(self.min_delay_var.get().strip())
            max_delay = float(self.max_delay_var.get().strip())
        except ValueError as exc:
            raise ValueError('Limite e intervalos devem ser números válidos.') from exc

        if not 1 <= limit <= MAX_GUI_BATCH:
            raise ValueError(f'O limite da rodada deve ficar entre 1 e {MAX_GUI_BATCH}.')
        if min_delay < 0 or max_delay < min_delay:
            raise ValueError('A faixa de intervalo é inválida.')
        if not self.dry_run_var.get() and min_delay < MIN_REAL_DELAY_SECONDS:
            raise ValueError(
                f'Em modo real, o intervalo mínimo desta interface é '
                f'{int(MIN_REAL_DELAY_SECONDS)} segundos.'
            )
        return limit, min_delay, max_delay

    def _start_run(self):
        if self.running:
            return
        try:
            source, destination = self._selected_route()
            limit, min_delay, max_delay = self._read_run_controls()
        except Exception as exc:
            messagebox.showwarning('Configuração da rodada', str(exc))
            return

        dry_run = bool(self.dry_run_var.get())
        if not dry_run and not self.consent_var.get():
            messagebox.showwarning(
                'Confirmação necessária',
                'Marque a confirmação de autorização antes de uma rodada real.',
            )
            return

        mode = 'DRY RUN' if dry_run else 'REAL'
        if not dry_run:
            confirmed = messagebox.askyesno(
                'Confirmar rodada real',
                f'Iniciar uma rodada automática de até {limit} tentativas?\n\n'
                f'Origem: {source.title}\n'
                f'Destino: {destination.title}\n'
                f'Intervalo operacional: {min_delay:g}–{max_delay:g} s\n\n'
                'A fila será filtrada para remover admins/owner, bots, bloqueados, '
                'membros já presentes e usuários já processados nesta rota.',
            )
            if not confirmed:
                return

        self.running = True
        self.stop_event.clear()
        self.pause_event.clear()
        self._set_running_controls(True)
        self._set_status(f'Rodada {mode} em preparação...')
        self._append_log(f'Iniciando rodada {mode} com limite {limit}.')

        self._submit(
            self._run_batch(source, destination, limit, min_delay, max_delay, dry_run),
            self._after_run,
        )

    async def _run_batch(self, source, destination, limit, min_delay, max_delay, dry_run):
        prepared = await self._prepare_queue(source, destination)
        batch = prepared.queue[:limit]
        if not batch:
            return MigrationStats(), None, prepared

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
                    lambda i=index, u=user: self._set_status(
                        f'Processando {i}/{len(batch)}: {full_name(u)}'
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

                if stats.permissions or stats.rate_limited or stats.stopped:
                    total.stopped = True
                    break

                if not dry_run and index < len(batch) and not self.stop_event.is_set():
                    delay = random.uniform(min_delay, max_delay)
                    self._ui(
                        lambda d=delay: self._set_status(
                            f'Intervalo operacional: próxima tentativa em ~{d:.0f}s'
                        )
                    )
                    elapsed = 0.0
                    while elapsed < delay:
                        if self.stop_event.is_set():
                            total.stopped = True
                            break
                        while self.pause_event.is_set() and not self.stop_event.is_set():
                            await asyncio.sleep(0.25)
                        step = min(0.5, delay - elapsed)
                        await asyncio.sleep(step)
                        elapsed += step
                    if self.stop_event.is_set():
                        break
        finally:
            report.close()

        return total, str(report.path), prepared

    @staticmethod
    def _merge_stats(total, stats):
        total.processed += stats.processed
        total.added += stats.added
        total.already_member += stats.already_member
        total.privacy += stats.privacy
        total.permissions += stats.permissions
        total.rate_limited += stats.rate_limited
        total.skipped += stats.skipped
        total.errors += stats.errors
        total.stopped = total.stopped or stats.stopped

    def _after_run(self, future):
        self.running = False
        self.pause_event.clear()
        self.stop_event.clear()
        self._set_running_controls(False)
        try:
            stats, report_path, prepared = future.result()
        except Exception as exc:
            self._set_status('Rodada encerrada com erro.')
            self._append_log(f'ERRO: {type(exc).__name__}: {exc}')
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
        self._append_log(f'Rodada concluída. {summary}.')
        if report_path:
            self._append_log(f'Relatório CSV: {report_path}')

        messagebox.showinfo(
            'Rodada concluída',
            f'{summary}\n\nRelatório: {report_path or "nenhum (fila vazia)"}',
        )

    def _toggle_pause(self):
        if not self.running:
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text='Pausar')
            self._set_status('Retomando a rodada...')
            self._append_log('Rodada retomada.')
        else:
            self.pause_event.set()
            self.pause_button.configure(text='Retomar')
            self._set_status('Pausado entre tentativas.')
            self._append_log('Pausa solicitada. A tentativa em andamento não é interrompida.')

    def _stop_run(self):
        if self.running:
            self.stop_event.set()
            self._set_status('Parada solicitada...')
            self._append_log('Parada solicitada. Nenhuma nova tentativa será iniciada.')

    def _set_running_controls(self, running):
        normal = 'disabled' if running else 'normal'
        self.connect_button.configure(state=normal)
        self.analyze_button.configure(state=normal)
        self.start_button.configure(state=normal)
        self.source_combo.configure(state=normal)
        self.destination_combo.configure(state=normal)
        self.pause_button.configure(state='normal' if running else 'disabled')
        self.stop_button.configure(state='normal' if running else 'disabled')
        if not running:
            self.pause_button.configure(text='Pausar')

    def _on_dry_run_change(self):
        if self.dry_run_var.get():
            self.consent_check.configure(state='disabled')
            self.consent_var.set(False)
        else:
            self.consent_check.configure(state='normal')

    def _refresh_history(self):
        if not hasattr(self, 'history_frame'):
            return
        for child in self.history_frame.winfo_children():
            child.destroy()

        rows = self.store.recent_history(100)
        if not rows:
            ctk.CTkLabel(
                self.history_frame,
                text='Nenhuma tentativa registrada ainda.',
                text_color=('gray40', 'gray70'),
            ).grid(row=0, column=0, padx=12, pady=20, sticky='w')
            return

        for index, row in enumerate(rows):
            frame = ctk.CTkFrame(self.history_frame, corner_radius=10)
            frame.grid(row=index, column=0, padx=4, pady=4, sticky='ew')
            frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                frame,
                text=row['status'].upper(),
                width=120,
                font=ctk.CTkFont(size=12, weight='bold'),
            ).grid(row=0, column=0, rowspan=2, padx=12, pady=10)

            ctk.CTkLabel(
                frame,
                text=f"{row['name'] or row['user_id']} · ID {row['user_id']}",
                font=ctk.CTkFont(size=14, weight='bold'),
            ).grid(row=0, column=1, padx=8, pady=(8, 0), sticky='w')

            ctk.CTkLabel(
                frame,
                text=row['reason'] or 'Sem observação',
                text_color=('gray40', 'gray70'),
                anchor='w',
            ).grid(row=1, column=1, padx=8, pady=(0, 8), sticky='w')

            ctk.CTkLabel(
                frame,
                text=row['timestamp'].replace('T', ' ')[:19],
                text_color=('gray45', 'gray65'),
            ).grid(row=0, column=2, rowspan=2, padx=12)

    def _add_exclusion(self):
        try:
            user_id = int(self.exclusion_id.get().strip())
            self.store.add_exclusion(user_id, self.exclusion_note.get())
        except Exception as exc:
            messagebox.showwarning('Exclusão', str(exc))
            return
        self.exclusion_id.delete(0, 'end')
        self.exclusion_note.delete(0, 'end')
        self._refresh_exclusions()
        self.prepared = None
        self._append_log(f'Exclusão local adicionada para o ID {user_id}.')

    def _remove_exclusion(self, user_id):
        self.store.remove_exclusion(user_id)
        self._refresh_exclusions()
        self.prepared = None
        self._append_log(f'Exclusão local removida para o ID {user_id}.')

    def _refresh_exclusions(self):
        if not hasattr(self, 'exclusions_frame'):
            return
        for child in self.exclusions_frame.winfo_children():
            child.destroy()

        db_rows = self.store.list_exclusions()
        env_ids = sorted(self.settings.excluded_user_ids)

        row_index = 0
        for user_id in env_ids:
            frame = ctk.CTkFrame(self.exclusions_frame, corner_radius=10)
            frame.grid(row=row_index, column=0, padx=4, pady=4, sticky='ew')
            frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(frame, text=str(user_id), font=ctk.CTkFont(weight='bold')).grid(
                row=0, column=0, padx=12, pady=12
            )
            ctk.CTkLabel(
                frame,
                text='Exclusão definida no .env',
                text_color=('gray40', 'gray70'),
            ).grid(row=0, column=1, padx=8, sticky='w')
            row_index += 1

        for row in db_rows:
            frame = ctk.CTkFrame(self.exclusions_frame, corner_radius=10)
            frame.grid(row=row_index, column=0, padx=4, pady=4, sticky='ew')
            frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                frame,
                text=str(row['user_id']),
                font=ctk.CTkFont(weight='bold'),
            ).grid(row=0, column=0, padx=12, pady=12)
            ctk.CTkLabel(
                frame,
                text=row['note'] or 'Exclusão local',
                text_color=('gray40', 'gray70'),
            ).grid(row=0, column=1, padx=8, sticky='w')
            ctk.CTkButton(
                frame,
                text='Remover',
                width=90,
                fg_color='#b91c1c',
                hover_color='#991b1b',
                command=lambda uid=row['user_id']: self._remove_exclusion(uid),
            ).grid(row=0, column=2, padx=12, pady=8)
            row_index += 1

        if row_index == 0:
            ctk.CTkLabel(
                self.exclusions_frame,
                text='Nenhuma exclusão cadastrada.',
                text_color=('gray40', 'gray70'),
            ).grid(row=0, column=0, padx=12, pady=20, sticky='w')

    def _submit(self, coroutine, callback):
        future = self.runtime.submit(coroutine)
        future.add_done_callback(lambda f: self.after(0, callback, f))

    def _ui(self, callback):
        self.after(0, callback)

    def _append_log(self, text):
        if not hasattr(self, 'log_box'):
            return
        self.log_box.configure(state='normal')
        self.log_box.insert('end', text.rstrip() + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def _set_status(self, text):
        if hasattr(self, 'run_status'):
            self.run_status.configure(text=text)

    def _on_close(self):
        self.stop_event.set()

        async def disconnect():
            if self.service is not None:
                try:
                    await self.service.disconnect()
                except Exception:
                    pass

        try:
            future = self.runtime.submit(disconnect())
            future.add_done_callback(lambda _: self.after(0, self._finish_close))
            self.after(1200, self._finish_close)
        except Exception:
            self._finish_close()

    def _finish_close(self):
        try:
            self.runtime.stop()
        finally:
            try:
                self.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    app = LocalApp()
    app.mainloop()
