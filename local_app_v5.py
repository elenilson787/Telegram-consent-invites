import customtkinter as ctk

from local_app_v4 import LocalAppV4
from ui_preferences import load_ui_preferences, save_ui_preferences


class LocalAppV5(LocalAppV4):
    """Quinta versão da interface local.

    Refina os cards de métricas e restaura a última rota usada por ID de grupo.
    A preferência é persistida apenas localmente em data/ui_preferences.json.
    """

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self._style_metric_cards()
        self._install_route_memory()

    def _style_metric_cards(self):
        if not hasattr(self, 'compact_metric_labels'):
            return

        for value_label in self.compact_metric_labels.values():
            card = value_label.master
            card.configure(
                fg_color=('#f2f2f2', '#343438'),
                border_width=1,
                border_color=('#d5d5d5', '#47474d'),
                corner_radius=10,
            )

    def _install_route_memory(self):
        self.source_combo.configure(command=lambda _: self._on_route_changed('Origem alterada.'))
        self.destination_combo.configure(command=lambda _: self._on_route_changed('Destino alterado.'))

    def _on_route_changed(self, reason):
        if self.running:
            return
        self._invalidate_prepared(reason)
        self._save_current_route_preferences()

    def _save_current_route_preferences(self):
        source = self.dialog_map.get(self.source_combo.get())
        destination = self.dialog_map.get(self.destination_combo.get())
        if source is None or destination is None or source.id == destination.id:
            return
        try:
            save_ui_preferences(source.id, destination.id)
        except OSError as exc:
            self._append_log(f'Não foi possível salvar a preferência de rota: {exc}')

    def _after_connect(self, future):
        super()._after_connect(future)
        if self.connection_badge.cget('text') != '● Conectado':
            return
        self._restore_last_route()

    def _restore_last_route(self):
        preferences = load_ui_preferences()
        source_id = preferences.get('source_id')
        destination_id = preferences.get('destination_id')
        if source_id is None or destination_id is None:
            return

        labels_by_id = {
            dialog.id: label
            for label, dialog in self.dialog_map.items()
        }
        source_label = labels_by_id.get(source_id)
        destination_label = labels_by_id.get(destination_id)
        if not source_label or not destination_label or source_label == destination_label:
            return

        self.source_combo.set(source_label)
        self.destination_combo.set(destination_label)
        self.prepared = None
        self.consent_var.set(False)
        self.start_button.configure(state='disabled')
        self._sync_compact_metrics()
        self._reset_progress()
        self._set_status('Conectado. Última rota restaurada; analise a fila.')
        self._append_log(
            f'Última rota restaurada: '
            f'{self.dialog_map[source_label].title} → '
            f'{self.dialog_map[destination_label].title}.'
        )

    def _after_analyze(self, future):
        super()._after_analyze(future)
        if self.prepared is not None:
            self._save_current_route_preferences()


if __name__ == '__main__':
    app = LocalAppV5()
    app.mainloop()
