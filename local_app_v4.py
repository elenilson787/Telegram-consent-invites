import customtkinter as ctk

from local_app_v3 import LocalAppV3


class LocalAppV4(LocalAppV3):
    """Quarta versão da interface local.

    Coloca as métricas essenciais dentro do bloco de progresso, evitando que a
    faixa de indicadores desapareça em telas com pouca altura útil.
    """

    METRICS = (
        ('extraidos', 'Extraídos'),
        ('admins', 'Admins'),
        ('destino', 'Já no destino'),
        ('processados', 'Já processados'),
        ('fila', 'Fila disponível'),
        ('rodada', 'Nesta rodada'),
    )

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self._install_compact_metrics()
        self.limit_var.trace_add('write', self._on_limit_changed)
        self._sync_compact_metrics()

    def _install_compact_metrics(self):
        # A faixa antiga ocupava uma linha própria do grid e podia ser cortada
        # pela altura útil do Windows. Ela continua existindo apenas como fonte
        # de compatibilidade, mas fica oculta.
        try:
            legacy_metrics_frame = next(iter(self.metric_labels.values())).master.master
            legacy_metrics_frame.grid_remove()
        except Exception:
            pass

        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_frame.grid_columnconfigure(1, weight=0)

        self.compact_metrics_frame = ctk.CTkFrame(
            self.progress_frame,
            fg_color='transparent',
        )
        self.compact_metrics_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=10,
            pady=(0, 10),
            sticky='ew',
        )

        self.compact_metric_labels = {}
        for column, (key, title) in enumerate(self.METRICS):
            self.compact_metrics_frame.grid_columnconfigure(column, weight=1)
            card = ctk.CTkFrame(
                self.compact_metrics_frame,
                corner_radius=9,
                height=54,
            )
            card.grid(row=0, column=column, padx=3, sticky='ew')
            card.grid_propagate(False)

            value = ctk.CTkLabel(
                card,
                text='—',
                font=ctk.CTkFont(size=18, weight='bold'),
            )
            value.pack(pady=(5, 0))
            ctk.CTkLabel(
                card,
                text=title,
                text_color=('gray40', 'gray70'),
                font=ctk.CTkFont(size=11),
            ).pack(pady=(0, 5))
            self.compact_metric_labels[key] = value

        # Com as métricas dentro do progresso, não precisamos reservar a linha
        # separada da versão anterior.
        tab = self.tabs.tab('Operação')
        tab.grid_rowconfigure(4, minsize=0, weight=0)

    def _show_prepared(self, prepared):
        super()._show_prepared(prepared)
        self._sync_compact_metrics()

    def _sync_compact_metrics(self):
        if not hasattr(self, 'compact_metric_labels'):
            return

        if self.prepared is None:
            for label in self.compact_metric_labels.values():
                label.configure(text='—')
            return

        values = {
            'extraidos': self.prepared.extracted,
            'admins': self.prepared.admins,
            'destino': self.prepared.already_destination,
            'processados': self.prepared.previously_processed,
            'fila': len(self.prepared.queue),
            'rodada': self._current_batch_size(),
        }
        for key, value in values.items():
            self.compact_metric_labels[key].configure(text=str(value))

    def _current_batch_size(self):
        if self.prepared is None:
            return 0
        try:
            limit = int(self.limit_var.get().strip())
        except (TypeError, ValueError):
            return 0
        if limit < 1:
            return 0
        return min(limit, len(self.prepared.queue))

    def _on_limit_changed(self, *_):
        if not hasattr(self, 'compact_metric_labels'):
            return
        if self.prepared is None:
            return
        self.compact_metric_labels['rodada'].configure(text=str(self._current_batch_size()))

    def _invalidate_prepared(self, reason='Configuração alterada.', log=True):
        super()._invalidate_prepared(reason=reason, log=log)
        self._sync_compact_metrics()

    def _after_run_v2(self, future):
        super()._after_run_v2(future)
        self._sync_compact_metrics()


if __name__ == '__main__':
    app = LocalAppV4()
    app.mainloop()
