"""V12: convites por mensagem para destinatários com opt-in explícito.

Mantém a V11 e acrescenta uma aba separada para enviar o link do Grupo B por
mensagem privada. A lista de destinatários não é preenchida automaticamente a
partir da extração: o operador precisa informar IDs que autorizaram o contato.
"""

from tkinter import messagebox

import customtkinter as ctk

from local_app_v11 import LocalAppV11
from message_invites import MessageInviteEngine, parse_opt_in_ids
from utils import full_name


MAX_MESSAGE_BATCH = 20
MIN_MESSAGE_DELAY_SECONDS = 30.0


MESSAGE_STATUS_LABELS = {
    'message_dry_run': 'SIMULAÇÃO',
    'message_sent': 'ENVIADO',
    'message_privacy': 'PRIVACIDADE',
    'message_invalid_user': 'INVÁLIDO',
    'message_flood_wait': 'RATE LIMIT',
    'message_peer_flood': 'PEER FLOOD',
    'message_error': 'ERRO',
}


class LocalAppV12(LocalAppV11):
    """V11 com fluxo de mensagens somente para IDs de opt-in explícito."""

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self.message_invite_link = ''
        self.message_link_destination_id = None
        self.message_link_var = ctk.StringVar(value='Nenhum link carregado ainda.')
        self.message_limit_var = ctk.StringVar(value='5')
        self.message_min_delay_var = ctk.StringVar(value='30')
        self.message_max_delay_var = ctk.StringVar(value='60')
        self.message_consent_var = ctk.BooleanVar(value=False)

        self._build_message_invites_tab()
        self._refresh_message_history()

    def _build_message_invites_tab(self):
        self.tabs.add('Convites por mensagem')
        tab = self.tabs.tab('Convites por mensagem')
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(tab, fg_color='transparent')
        content.grid(row=0, column=0, sticky='nsew', padx=6, pady=6)
        content.grid_columnconfigure(0, weight=1)

        intro = ctk.CTkFrame(content, corner_radius=12)
        intro.grid(row=0, column=0, sticky='ew', padx=4, pady=(4, 8))
        intro.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            intro,
            text='✉ Convites por mensagem — somente opt-in',
            font=ctk.CTkFont(size=19, weight='bold'),
            text_color='#22d3ee',
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 2))
        ctk.CTkLabel(
            intro,
            text=(
                'Use a mesma rota da aba Operação. Cole abaixo apenas IDs de pessoas que '
                'autorizaram receber contato. O app remove admins, bots, excluídos, quem já '
                'está no destino e quem já recebeu uma tentativa real de mensagem.'
            ),
            justify='left',
            wraplength=1180,
            text_color=('gray35', 'gray70'),
        ).grid(row=1, column=0, sticky='w', padx=14, pady=(0, 12))

        link_frame = ctk.CTkFrame(content, corner_radius=12)
        link_frame.grid(row=1, column=0, sticky='ew', padx=4, pady=8)
        link_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            link_frame,
            text='1. Link do Grupo B',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, columnspan=2, sticky='w', padx=14, pady=(10, 4))
        self.message_link_entry = ctk.CTkEntry(
            link_frame,
            textvariable=self.message_link_var,
            state='readonly',
        )
        self.message_link_entry.grid(row=1, column=0, sticky='ew', padx=(14, 8), pady=(2, 12))
        self.message_link_button = ctk.CTkButton(
            link_frame,
            text='Gerar / atualizar link',
            command=self._load_message_invite_link,
            width=170,
        )
        self.message_link_button.grid(row=1, column=1, padx=(0, 14), pady=(2, 12))

        ids_frame = ctk.CTkFrame(content, corner_radius=12)
        ids_frame.grid(row=2, column=0, sticky='ew', padx=4, pady=8)
        ids_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            ids_frame,
            text='2. IDs autorizados / opt-in',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(10, 2))
        ctk.CTkLabel(
            ids_frame,
            text='Aceita um ID por linha ou separados por espaço, vírgula ou ponto e vírgula.',
            text_color=('gray40', 'gray70'),
        ).grid(row=1, column=0, sticky='w', padx=14, pady=(0, 5))
        self.message_ids_box = ctk.CTkTextbox(ids_frame, height=105, wrap='word')
        self.message_ids_box.grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 12))

        template_frame = ctk.CTkFrame(content, corner_radius=12)
        template_frame.grid(row=3, column=0, sticky='ew', padx=4, pady=8)
        template_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            template_frame,
            text='3. Mensagem',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(10, 2))
        ctk.CTkLabel(
            template_frame,
            text='Placeholders: {name} · {destination} · {link}',
            text_color=('gray40', 'gray70'),
        ).grid(row=1, column=0, sticky='w', padx=14, pady=(0, 5))
        self.message_template_box = ctk.CTkTextbox(template_frame, height=120, wrap='word')
        self.message_template_box.grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.message_template_box.insert(
            '1.0',
            'Olá, {name}! Você autorizou receber o convite para o grupo '
            '{destination}. Se quiser participar, entre por aqui:\n{link}',
        )

        controls = ctk.CTkFrame(content, corner_radius=12)
        controls.grid(row=4, column=0, sticky='ew', padx=4, pady=8)
        controls.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(
            controls,
            text='4. Ritmo e confirmação',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, columnspan=3, sticky='w', padx=14, pady=(10, 6))
        ctk.CTkLabel(controls, text=f'Limite (1–{MAX_MESSAGE_BATCH})').grid(
            row=1, column=0, sticky='w', padx=(14, 5)
        )
        ctk.CTkLabel(controls, text='Intervalo mín. (s)').grid(row=1, column=1, sticky='w', padx=5)
        ctk.CTkLabel(controls, text='Intervalo máx. (s)').grid(row=1, column=2, sticky='w', padx=(5, 14))
        ctk.CTkEntry(controls, textvariable=self.message_limit_var).grid(
            row=2, column=0, sticky='ew', padx=(14, 5), pady=(3, 7)
        )
        ctk.CTkEntry(controls, textvariable=self.message_min_delay_var).grid(
            row=2, column=1, sticky='ew', padx=5, pady=(3, 7)
        )
        ctk.CTkEntry(controls, textvariable=self.message_max_delay_var).grid(
            row=2, column=2, sticky='ew', padx=(5, 14), pady=(3, 7)
        )
        self.message_consent_check = ctk.CTkCheckBox(
            controls,
            text='Confirmo que os IDs informados autorizaram receber esta mensagem.',
            variable=self.message_consent_var,
        )
        self.message_consent_check.grid(
            row=3, column=0, columnspan=3, sticky='w', padx=14, pady=(4, 12)
        )

        actions = ctk.CTkFrame(content, fg_color='transparent')
        actions.grid(row=5, column=0, sticky='ew', padx=4, pady=(5, 8))
        actions.grid_columnconfigure(2, weight=1)
        self.message_send_button = ctk.CTkButton(
            actions,
            text='▶ Executar convites por mensagem',
            command=self._start_message_invites,
            width=250,
            height=34,
            fg_color='#db2777',
            hover_color='#be185d',
        )
        self.message_send_button.grid(row=0, column=0, padx=(0, 8))
        self.message_history_button = ctk.CTkButton(
            actions,
            text='Atualizar histórico',
            command=self._refresh_message_history,
            width=150,
        )
        self.message_history_button.grid(row=0, column=1, padx=8)
        self.message_status_label = ctk.CTkLabel(
            actions,
            text='DRY RUN global ativo: a simulação não envia mensagens.' if self.dry_run_var.get()
            else 'Modo real ativo.',
            text_color=('gray40', 'gray70'),
        )
        self.message_status_label.grid(row=0, column=2, sticky='e', padx=8)

        log_frame = ctk.CTkFrame(content, corner_radius=12)
        log_frame.grid(row=6, column=0, sticky='ew', padx=4, pady=8)
        log_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            log_frame,
            text='Atividade de mensagens',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(10, 4))
        self.message_log_box = ctk.CTkTextbox(log_frame, height=110, wrap='word')
        self.message_log_box.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.message_log_box.configure(state='disabled')

        history_card = ctk.CTkFrame(content, corner_radius=12)
        history_card.grid(row=7, column=0, sticky='ew', padx=4, pady=(8, 14))
        history_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            history_card,
            text='Histórico de convites por mensagem',
            font=ctk.CTkFont(size=16, weight='bold'),
        ).grid(row=0, column=0, sticky='w', padx=14, pady=(10, 4))
        self.message_history_frame = ctk.CTkScrollableFrame(history_card, height=190)
        self.message_history_frame.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.message_history_frame.grid_columnconfigure(0, weight=1)

    def _append_message_log(self, text):
        self.message_log_box.configure(state='normal')
        self.message_log_box.insert('end', str(text).rstrip() + '\n')
        self.message_log_box.see('end')
        self.message_log_box.configure(state='disabled')

    def _read_message_controls(self):
        try:
            limit = int(self.message_limit_var.get().strip())
            min_delay = float(self.message_min_delay_var.get().strip())
            max_delay = float(self.message_max_delay_var.get().strip())
        except ValueError as exc:
            raise ValueError('Limite e intervalos de mensagem devem ser números válidos.') from exc

        if not 1 <= limit <= MAX_MESSAGE_BATCH:
            raise ValueError(f'O limite de mensagens deve ficar entre 1 e {MAX_MESSAGE_BATCH}.')
        if min_delay < MIN_MESSAGE_DELAY_SECONDS:
            raise ValueError(
                f'O intervalo mínimo de mensagens deve ser de pelo menos '
                f'{int(MIN_MESSAGE_DELAY_SECONDS)} segundos.'
            )
        if max_delay < min_delay:
            raise ValueError('O intervalo máximo não pode ser menor que o mínimo.')
        return limit, min_delay, max_delay

    def _load_message_invite_link(self):
        if self.running:
            return
        if self.service is None:
            messagebox.showwarning('Convites por mensagem', 'Conecte ao Telegram primeiro.')
            return
        destination = self.dialog_map.get(self.destination_combo.get())
        if destination is None:
            messagebox.showwarning('Convites por mensagem', 'Selecione o Grupo B — destino.')
            return

        self.message_link_button.configure(state='disabled', text='Gerando...')
        self._submit(
            self._export_destination_invite(destination),
            self._after_load_message_invite_link,
        )

    def _after_load_message_invite_link(self, future):
        self.message_link_button.configure(state='normal', text='Gerar / atualizar link')
        try:
            destination, link = future.result()
        except Exception as exc:
            self._append_message_log(f'ERRO ao gerar link: {type(exc).__name__}: {exc}')
            messagebox.showerror(
                'Convites por mensagem',
                f'Não foi possível gerar o link do destino:\n{type(exc).__name__}: {exc}',
            )
            return

        self.message_invite_link = link
        self.message_link_destination_id = destination.id
        self.message_link_var.set(link)
        self.clipboard_clear()
        self.clipboard_append(link)
        self._append_message_log(f'Link do destino carregado: {destination.title}.')

    def _start_message_invites(self):
        if self.running:
            return
        if self.service is None:
            messagebox.showwarning('Convites por mensagem', 'Conecte ao Telegram primeiro.')
            return

        try:
            source, destination = self._selected_route()
            opt_in_ids = parse_opt_in_ids(self.message_ids_box.get('1.0', 'end'))
            limit, min_delay, max_delay = self._read_message_controls()
            template = self.message_template_box.get('1.0', 'end').strip()
        except Exception as exc:
            messagebox.showwarning('Convites por mensagem', str(exc))
            return

        if not opt_in_ids:
            messagebox.showwarning(
                'Convites por mensagem',
                'Informe pelo menos um user_id autorizado/opt-in.',
            )
            return
        if not template:
            messagebox.showwarning('Convites por mensagem', 'A mensagem não pode ficar vazia.')
            return
        if '{link}' not in template:
            messagebox.showwarning(
                'Convites por mensagem',
                'Inclua {link} na mensagem para inserir automaticamente o convite do Grupo B.',
            )
            return

        dry_run = bool(self.dry_run_var.get())
        if not dry_run and not self.message_consent_var.get():
            messagebox.showwarning(
                'Confirmação necessária',
                'Confirme que os IDs informados autorizaram receber a mensagem.',
            )
            return

        if not dry_run:
            confirmed = messagebox.askyesno(
                'Confirmar mensagens reais',
                f'Enviar mensagens para até {min(limit, len(opt_in_ids))} IDs autorizados?\n\n'
                f'Origem de referência: {source.title}\n'
                f'Destino: {destination.title}\n'
                f'Intervalo: {min_delay:g}–{max_delay:g}s\n\n'
                'O app interrompe imediatamente se o Telegram retornar rate limit.',
            )
            if not confirmed:
                return

        self.running = True
        self._set_running_controls(True)
        self.message_send_button.configure(state='disabled')
        self.message_link_button.configure(state='disabled')
        self.message_history_button.configure(state='disabled')
        mode = 'SIMULAÇÃO' if dry_run else 'REAL'
        self.message_status_label.configure(text=f'Convites por mensagem em execução · {mode}')
        self._append_message_log(
            f'Iniciando {mode}: {len(opt_in_ids)} IDs informados, limite {limit}.'
        )
        self._submit(
            self._run_message_invites(
                source,
                destination,
                opt_in_ids,
                template,
                limit,
                min_delay,
                max_delay,
                dry_run,
            ),
            self._after_message_invites,
        )

    async def _run_message_invites(
        self,
        source,
        destination,
        opt_in_ids,
        template,
        limit,
        min_delay,
        max_delay,
        dry_run,
    ):
        members = await self.service.get_members(source.entity)
        source_admin_ids = await self.service.get_admin_ids(source.entity)
        destination_ids = await self.service.get_member_ids(destination.entity)
        excluded_ids = set(self.settings.excluded_user_ids) | self.store.excluded_ids()
        already_messaged = self.store.messaged_ids(source.id, destination.id)
        by_id = {int(user.id): user for user in members}

        selected = []
        filtered = {
            'missing': 0,
            'admins': 0,
            'bots': 0,
            'excluded': 0,
            'already_destination': 0,
            'already_messaged': 0,
        }

        for user_id in opt_in_ids:
            user = by_id.get(int(user_id))
            if user is None:
                filtered['missing'] += 1
            elif user.id in source_admin_ids:
                filtered['admins'] += 1
            elif getattr(user, 'bot', False):
                filtered['bots'] += 1
            elif user.id in excluded_ids:
                filtered['excluded'] += 1
            elif user.id in destination_ids:
                filtered['already_destination'] += 1
            elif user.id in already_messaged:
                filtered['already_messaged'] += 1
            else:
                selected.append(user)

        selected = selected[:limit]

        link = self.message_invite_link
        if self.message_link_destination_id != destination.id:
            link = ''
        if not link:
            if dry_run:
                link = '[LINK_DO_GRUPO_B]'
            else:
                link = await self.service.export_invite_link(destination.entity)

        def report(user_id, username, name, status, reason=''):
            self.store.record_message_attempt(
                source.id,
                destination.id,
                user_id,
                username,
                name,
                status,
                reason,
            )
            label = MESSAGE_STATUS_LABELS.get(status, status.upper())
            self._ui(
                lambda n=name or user_id, s=label: self._append_message_log(f'{n} · {s}')
            )

        engine = MessageInviteEngine(
            self.service.client,
            min_delay=min_delay,
            max_delay=max_delay,
        )
        stats = await engine.run(
            selected,
            report,
            template,
            destination.title,
            link,
            limit=len(selected),
            dry_run=dry_run,
        )
        return stats, filtered, len(selected), link, destination, dry_run

    def _after_message_invites(self, future):
        self.running = False
        self._set_running_controls(False)
        self.message_send_button.configure(state='normal')
        self.message_link_button.configure(state='normal')
        self.message_history_button.configure(state='normal')

        try:
            stats, filtered, selected_count, link, destination, dry_run = future.result()
        except Exception as exc:
            self.message_status_label.configure(text='Falha na execução de mensagens.')
            self._append_message_log(f'ERRO: {type(exc).__name__}: {exc}')
            messagebox.showerror(
                'Convites por mensagem',
                f'A execução falhou:\n{type(exc).__name__}: {exc}',
            )
            return

        if not dry_run and link and link != '[LINK_DO_GRUPO_B]':
            self.message_invite_link = link
            self.message_link_destination_id = destination.id
            self.message_link_var.set(link)

        if not dry_run:
            self.dry_run_var.set(True)
            self._on_dry_run_change()

        self._refresh_message_history()
        filtered_total = sum(filtered.values())
        summary = (
            f'Processados={stats.processed} · Enviados={stats.sent} · '
            f'Ignorados={stats.skipped} · Privacidade={stats.privacy} · '
            f'Rate limit={stats.rate_limited} · Erros={stats.errors}'
        )
        self.message_status_label.configure(
            text='Concluído. Interface voltou ao DRY RUN.' if not dry_run else 'Simulação concluída.'
        )
        self._append_message_log(f'Concluído. {summary}.')
        self._append_message_log(
            'Filtro prévio: '
            f'selecionados={selected_count}; removidos={filtered_total}; '
            f'já no destino={filtered["already_destination"]}; '
            f'já contatados={filtered["already_messaged"]}; '
            f'admins={filtered["admins"]}; excluídos={filtered["excluded"]}; '
            f'bots={filtered["bots"]}; não encontrados={filtered["missing"]}.'
        )

        messagebox.showinfo(
            'Convites por mensagem concluídos',
            f'{summary}\n\n'
            f'IDs elegíveis nesta execução: {selected_count}\n'
            f'IDs filtrados antes do envio: {filtered_total}\n\n'
            'Se houver rate limit, não inicie outra rodada real imediatamente.',
        )

    def _refresh_message_history(self):
        if not hasattr(self, 'message_history_frame'):
            return
        for child in self.message_history_frame.winfo_children():
            child.destroy()

        rows = self.store.recent_message_history(80)
        if not rows:
            ctk.CTkLabel(
                self.message_history_frame,
                text='Nenhum convite por mensagem registrado ainda.',
                text_color=('gray40', 'gray70'),
            ).grid(row=0, column=0, sticky='w', padx=8, pady=12)
            return

        for index, row in enumerate(rows):
            frame = ctk.CTkFrame(self.message_history_frame, corner_radius=8)
            frame.grid(row=index, column=0, sticky='ew', padx=2, pady=3)
            frame.grid_columnconfigure(1, weight=1)
            status = MESSAGE_STATUS_LABELS.get(row['status'], row['status'].upper())
            ctk.CTkLabel(
                frame,
                text=status,
                width=115,
                font=ctk.CTkFont(size=11, weight='bold'),
            ).grid(row=0, column=0, rowspan=2, padx=8, pady=7)
            ctk.CTkLabel(
                frame,
                text=f"{row['name'] or row['user_id']} · ID {row['user_id']}",
                font=ctk.CTkFont(size=12, weight='bold'),
            ).grid(row=0, column=1, sticky='w', padx=6, pady=(6, 0))
            ctk.CTkLabel(
                frame,
                text=row['reason'] or 'Sem observação',
                text_color=('gray40', 'gray70'),
                anchor='w',
            ).grid(row=1, column=1, sticky='w', padx=6, pady=(0, 6))
            ctk.CTkLabel(
                frame,
                text=row['timestamp'].replace('T', ' ')[:19],
                text_color=('gray45', 'gray65'),
            ).grid(row=0, column=2, rowspan=2, padx=8)

    def _set_running_controls(self, running):
        super()._set_running_controls(running)
        if hasattr(self, 'message_send_button'):
            state = 'disabled' if running else 'normal'
            self.message_send_button.configure(state=state)
            self.message_link_button.configure(state=state)
            self.message_history_button.configure(state=state)

    def _on_dry_run_change(self):
        super()._on_dry_run_change()
        if hasattr(self, 'message_status_label') and not self.running:
            self.message_status_label.configure(
                text='DRY RUN global ativo: a simulação não envia mensagens.'
                if self.dry_run_var.get()
                else 'Modo real ativo: confirmação de opt-in será exigida.'
            )


if __name__ == '__main__':
    app = LocalAppV12()
    app.mainloop()
