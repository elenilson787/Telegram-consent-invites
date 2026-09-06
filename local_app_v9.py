"""V9: mantém o tema cyber-neon e garante Preview/Atividade visíveis.

A correção é exclusivamente de layout. O backend, filtros, histórico e fluxo de
convites continuam herdados integralmente da V8/V7.
"""

import customtkinter as ctk

from local_app_v8 import LocalAppV8


def layout_profile(screen_height):
    """Retorna dimensões de layout para a altura física disponível da tela."""
    if screen_height <= 900:
        return {
            'compact': True,
            'window_height': 820,
            'queue_row_min': 158,
            'route_row_min': 128,
            'progress_row_min': 112,
            'metric_height': 46,
            'textbox_height': 112,
        }
    return {
        'compact': False,
        'window_height': 900,
        'queue_row_min': 190,
        'route_row_min': 150,
        'progress_row_min': 126,
        'metric_height': 54,
        'textbox_height': 145,
    }


class LocalAppV9(LocalAppV8):
    """V8 responsiva: reserva espaço real para Queue Preview e Activity Log."""

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self._vertical_profile = layout_profile(self.winfo_screenheight())
        self._fit_vertical_layout()

    def _label(self, text):
        return self._find_label(text)

    @staticmethod
    def _grid(widget, **kwargs):
        if widget is None:
            return
        try:
            widget.grid_configure(**kwargs)
        except Exception:
            pass

    @staticmethod
    def _pack(widget, **kwargs):
        if widget is None:
            return
        try:
            widget.pack_configure(**kwargs)
        except Exception:
            pass

    def _fit_vertical_layout(self):
        profile = self._vertical_profile
        self.geometry(f'1460x{profile["window_height"]}')
        self.minsize(1120, 700)

        # O Tabview consumia espaço vertical desnecessário em telas 768/864p.
        self._grid(self.tabs, padx=12, pady=(7, 8))

        tab = self.tabs.tab('Operação')
        tab.grid_rowconfigure(0, minsize=64, weight=0)
        tab.grid_rowconfigure(1, minsize=profile['route_row_min'], weight=0)
        tab.grid_rowconfigure(2, minsize=48, weight=0)
        tab.grid_rowconfigure(3, minsize=profile['progress_row_min'], weight=0)
        tab.grid_rowconfigure(4, minsize=0, weight=0)
        # Esta é a linha do QUEUE PREVIEW + LIVE ACTIVITY LOG.
        tab.grid_rowconfigure(5, minsize=profile['queue_row_min'], weight=1)

        self._compact_header()
        self._compact_connection()
        self._compact_route_and_controls()
        self._compact_actions()
        self._compact_progress()
        self._reserve_bottom_panels()

    def _compact_header(self):
        title = self._label('AFILIAPULSE • Telegram Manager')
        subtitle = self._label(
            'Gerenciamento local de participantes  •  OPERAÇÃO LOCAL / TELEGRAM API'
        )
        self._grid(title, pady=(8, 0))
        self._grid(subtitle, pady=(0, 6))
        if title is not None:
            self._safe_configure(title, font=ctk.CTkFont(size=25, weight='bold'))
        if subtitle is not None:
            self._safe_configure(subtitle, font=ctk.CTkFont(size=11))
        try:
            self.mode_badge.place_configure(y=12)
        except Exception:
            pass

    def _compact_connection(self):
        title = self._label('01 // Conexão com o Telegram')
        if title is None:
            return
        frame = title.master
        self._grid(title, pady=(8, 2))
        self._grid(self.connect_button, pady=(2, 8))
        self._grid(self.account_label, pady=(2, 8))
        self._grid(frame, pady=(3, 3))

    def _compact_route_and_controls(self):
        route_title = self._label('02 // Route Mapping')
        controls_title = self._label('03 // Execution Protocol')

        if route_title is not None:
            route = route_title.master
            self._grid(route_title, pady=(8, 3))
            self._grid(self._label('Grupo A — origem'), pady=(0, 1))
            self._grid(self.source_combo, pady=(0, 5))
            self._grid(self._label('Grupo B — destino'), pady=(0, 1))
            self._grid(self.destination_combo, pady=(0, 8))
            self._grid(route, pady=(3, 3))

        if controls_title is not None:
            controls = controls_title.master
            self._grid(controls_title, pady=(8, 3))
            self._grid(self.dry_switch, pady=(0, 5))
            self._grid(self.consent_check, pady=(2, 8))
            for widget in controls.winfo_children():
                if isinstance(widget, ctk.CTkEntry):
                    self._grid(widget, pady=(1, 4))
                elif isinstance(widget, ctk.CTkLabel) and widget is not controls_title:
                    # Rótulos dos três campos numéricos.
                    text = str(widget.cget('text'))
                    if text.startswith('Limite da rodada') or text in {
                        'Intervalo mín. (s)',
                        'Intervalo máx. (s)',
                    }:
                        self._grid(widget, pady=(0, 0))
            self._grid(controls, pady=(3, 3))

    def _compact_actions(self):
        actions = self.analyze_button.master
        self._grid(actions, pady=(0, 4))
        for button in (
            self.analyze_button,
            self.start_button,
            self.pause_button,
            self.stop_button,
        ):
            self._safe_configure(button, height=29)

        if hasattr(self, 'route_banner'):
            self._grid(self.route_banner, pady=(2, 0), ipady=2)

    def _compact_progress(self):
        self._grid(self.progress_frame, pady=(2, 4))
        self._grid(self.progress_title, pady=(6, 2))
        self._grid(self.countdown_label, pady=(6, 2))
        self._grid(self.progress_bar, pady=(1, 6))

        if hasattr(self, 'compact_metrics_frame'):
            self._grid(self.compact_metrics_frame, pady=(0, 6), padx=8)

        if hasattr(self, 'compact_metric_labels'):
            for value_label in self.compact_metric_labels.values():
                card = value_label.master
                self._safe_configure(card, height=self._vertical_profile['metric_height'])
                try:
                    card.grid_propagate(False)
                except Exception:
                    pass
                self._pack(value_label, pady=(3, 0))
                for child in card.winfo_children():
                    if child is value_label or not isinstance(child, ctk.CTkLabel):
                        continue
                    self._pack(child, pady=(0, 3))

    def _reserve_bottom_panels(self):
        queue_title = self._label('QUEUE PREVIEW // Fila automática')
        log_title = self._label('LIVE ACTIVITY LOG // Atividade')

        for title, textbox in (
            (queue_title, self.queue_box),
            (log_title, self.log_box),
        ):
            if title is None:
                continue
            frame = title.master
            frame.grid_rowconfigure(1, minsize=self._vertical_profile['textbox_height'], weight=1)
            self._grid(frame, pady=(2, 3))
            self._grid(title, pady=(8, 3))
            self._grid(textbox, padx=12, pady=(2, 8), sticky='nsew')
            self._safe_configure(textbox, height=self._vertical_profile['textbox_height'])


if __name__ == '__main__':
    app = LocalAppV9()
    app.mainloop()
