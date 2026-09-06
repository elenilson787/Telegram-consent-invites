"""V8 da interface local: acabamento visual cyber-neon.

A V8 herda integralmente o comportamento funcional da V7. Este arquivo altera
somente apresentação, hierarquia visual e feedback de estado.
"""

import customtkinter as ctk

from cyber_theme import (
    AMBER,
    BG,
    BG_ALT,
    BORDER,
    CYAN,
    CYAN_SOFT,
    GREEN,
    INPUT,
    MAGENTA,
    MUTED,
    PANEL,
    PANEL_ALT,
    PURPLE,
    RED,
    TEXT,
    WHITE,
    metric_accent,
    mode_palette,
)
from local_app_v7 import LocalAppV7


class LocalAppV8(LocalAppV7):
    """Painel cyber-neon sem alterar regras de negócio ou envio."""

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self.geometry('1460x900')
        self.minsize(1180, 760)
        self.configure(fg_color=BG)
        self._apply_cyber_theme()
        self._apply_mode_ui()
        self._refresh_primary_button()

    @staticmethod
    def _safe_configure(widget, **kwargs):
        try:
            widget.configure(**kwargs)
        except Exception:
            # A camada visual nunca deve impedir o funcionamento da ferramenta
            # caso uma versão de CustomTkinter não aceite uma opção cosmética.
            pass

    def _find_label(self, text):
        for widget in self._walk_widgets(self):
            if not isinstance(widget, ctk.CTkLabel):
                continue
            try:
                if widget.cget('text') == text:
                    return widget
            except Exception:
                continue
        return None

    def _apply_cyber_theme(self):
        self._style_header()
        self._style_tabs()
        self._style_sections()
        self._style_inputs()
        self._style_actions()
        self._style_progress_panel()
        self._style_metrics()
        self._style_text_panels()

    def _style_header(self):
        title = self._find_label('AFILIAPULSE • Telegram Manager')
        if title is not None:
            header = title.master
            self._safe_configure(header, fg_color=BG_ALT)
            self._safe_configure(
                title,
                text_color=TEXT,
                font=ctk.CTkFont(size=27, weight='bold'),
            )

        subtitle = self._find_label('Gerenciamento local de participantes')
        if subtitle is not None:
            self._safe_configure(
                subtitle,
                text='Gerenciamento local de participantes  •  OPERAÇÃO LOCAL / TELEGRAM API',
                text_color=CYAN_SOFT,
                font=ctk.CTkFont(size=12),
            )

        self._safe_configure(
            self.connection_badge,
            fg_color=INPUT,
            corner_radius=8,
            text_color=GREEN,
            font=ctk.CTkFont(size=13, weight='bold'),
        )

    def _style_tabs(self):
        self._safe_configure(
            self.tabs,
            fg_color=BG,
            segmented_button_fg_color=PANEL,
            segmented_button_selected_color=PURPLE,
            segmented_button_selected_hover_color=MAGENTA,
            segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color=PANEL_ALT,
        )

        for tab_name in ('Operação', 'Histórico', 'Exclusões'):
            try:
                tab = self.tabs.tab(tab_name)
            except Exception:
                continue
            self._safe_configure(tab, fg_color=BG)

    def _style_section(self, current_title, new_title, accent):
        label = self._find_label(current_title) or self._find_label(new_title)
        if label is None:
            return
        frame = label.master
        self._safe_configure(
            frame,
            fg_color=PANEL,
            border_width=1,
            border_color=accent,
            corner_radius=12,
        )
        self._safe_configure(
            label,
            text=new_title,
            text_color=accent,
            font=ctk.CTkFont(size=16, weight='bold'),
        )

    def _style_sections(self):
        self._style_section(
            '1. Conexão com o Telegram',
            '01 // Conexão com o Telegram',
            CYAN,
        )
        self._style_section(
            '2. Origem e destino',
            '02 // Route Mapping',
            MAGENTA,
        )
        self._style_section(
            '3. Segurança e ritmo',
            '03 // Execution Protocol',
            CYAN_SOFT,
        )
        self._style_section(
            'Fila automática',
            'QUEUE PREVIEW // Fila automática',
            CYAN,
        )
        self._style_section(
            'Atividade',
            'LIVE ACTIVITY LOG // Atividade',
            PURPLE,
        )

        self._safe_configure(
            self.account_label,
            text_color=GREEN,
            font=ctk.CTkFont(size=12, weight='bold'),
        )

        if hasattr(self, 'route_banner'):
            self._safe_configure(
                self.route_banner,
                fg_color=INPUT,
                text_color=CYAN,
                corner_radius=8,
                font=ctk.CTkFont(size=13, weight='bold'),
            )
            try:
                self.route_banner.grid_configure(ipady=5)
            except Exception:
                pass

    def _style_inputs(self):
        for widget in self._walk_widgets(self):
            if isinstance(widget, ctk.CTkComboBox):
                self._safe_configure(
                    widget,
                    fg_color=INPUT,
                    border_color=BORDER,
                    button_color=PANEL_ALT,
                    button_hover_color=CYAN_SOFT,
                    dropdown_fg_color=PANEL_ALT,
                    dropdown_hover_color='#12315a',
                    text_color=TEXT,
                    dropdown_text_color=TEXT,
                )
            elif isinstance(widget, ctk.CTkEntry):
                self._safe_configure(
                    widget,
                    fg_color=INPUT,
                    border_color=BORDER,
                    text_color=TEXT,
                    placeholder_text_color=MUTED,
                )
            elif isinstance(widget, ctk.CTkCheckBox):
                self._safe_configure(
                    widget,
                    border_color=CYAN_SOFT,
                    fg_color=PURPLE,
                    hover_color=MAGENTA,
                    checkmark_color=WHITE,
                    text_color=TEXT,
                )
            elif isinstance(widget, ctk.CTkSwitch):
                self._safe_configure(
                    widget,
                    progress_color=CYAN,
                    button_color=WHITE,
                    button_hover_color=CYAN_SOFT,
                    text_color=TEXT,
                )

    def _style_actions(self):
        self._safe_configure(
            self.connect_button,
            fg_color='#0b4f78',
            hover_color='#086d9e',
            border_width=1,
            border_color=CYAN,
            text_color=WHITE,
        )
        self._safe_configure(
            self.analyze_button,
            fg_color='#063a55',
            hover_color='#075d82',
            border_width=1,
            border_color=CYAN,
            text_color=WHITE,
        )
        self._safe_configure(
            self.pause_button,
            border_width=1,
            border_color=AMBER,
            text_color=WHITE,
        )
        self._safe_configure(
            self.stop_button,
            border_width=1,
            border_color=RED,
            text_color=WHITE,
        )

        # Demais botões secundários (Histórico/Exclusões) recebem o mesmo idioma visual.
        primary_ids = {
            id(self.connect_button),
            id(self.analyze_button),
            id(self.start_button),
            id(self.pause_button),
            id(self.stop_button),
        }
        for widget in self._walk_widgets(self):
            if not isinstance(widget, ctk.CTkButton) or id(widget) in primary_ids:
                continue
            self._safe_configure(
                widget,
                fg_color=PANEL_ALT,
                hover_color='#12315a',
                border_width=1,
                border_color=BORDER,
                text_color=TEXT,
            )

    def _style_progress_panel(self):
        if not hasattr(self, 'progress_frame'):
            return
        self._safe_configure(
            self.progress_frame,
            fg_color=PANEL,
            border_width=1,
            border_color=CYAN_SOFT,
            corner_radius=12,
        )
        self._safe_configure(
            self.progress_title,
            text_color=TEXT,
            font=ctk.CTkFont(size=14, weight='bold'),
        )
        self._safe_configure(self.countdown_label, text_color=AMBER)
        self._safe_configure(
            self.progress_bar,
            fg_color=BORDER,
            progress_color=CYAN,
            height=10,
        )

    def _style_metrics(self):
        if not hasattr(self, 'compact_metric_labels'):
            return
        for key, value_label in self.compact_metric_labels.items():
            accent = metric_accent(key)
            card = value_label.master
            self._safe_configure(
                card,
                fg_color=PANEL_ALT,
                border_width=1,
                border_color=accent,
                corner_radius=9,
            )
            self._safe_configure(
                value_label,
                text_color=accent,
                font=ctk.CTkFont(size=20, weight='bold'),
            )
            for child in card.winfo_children():
                if child is value_label or not isinstance(child, ctk.CTkLabel):
                    continue
                self._safe_configure(child, text_color=MUTED)

    def _style_text_panels(self):
        mono = ctk.CTkFont(family='Consolas', size=12)
        for textbox, accent in ((self.queue_box, CYAN), (self.log_box, PURPLE)):
            self._safe_configure(
                textbox,
                fg_color='#030914',
                border_width=1,
                border_color=accent,
                text_color='#ccecff',
                font=mono,
                corner_radius=8,
            )

    def _apply_mode_ui(self):
        super()._apply_mode_ui()
        if not hasattr(self, 'mode_badge'):
            return
        palette = mode_palette(bool(self.dry_run_var.get()))
        self._safe_configure(
            self.mode_badge,
            text=f'  {palette["label"]}  ',
            fg_color=palette['badge'],
            text_color=palette['badge_text'],
            corner_radius=9,
            font=ctk.CTkFont(size=13, weight='bold'),
        )
        if hasattr(self, 'start_button'):
            self._safe_configure(
                self.start_button,
                fg_color=palette['cta'],
                hover_color=palette['cta_hover'],
                border_width=1,
                border_color=palette['cta'],
                text_color=WHITE,
            )

    def _refresh_primary_button(self):
        super()._refresh_primary_button()
        if not hasattr(self, 'start_button'):
            return
        palette = mode_palette(bool(self.dry_run_var.get()))
        self._safe_configure(
            self.start_button,
            fg_color=palette['cta'],
            hover_color=palette['cta_hover'],
            border_width=1,
            border_color=palette['cta'],
            text_color=WHITE,
        )

    def _set_running_controls(self, running):
        super()._set_running_controls(running)
        if running:
            self._safe_configure(
                self.pause_button,
                fg_color='#5c4210',
                hover_color='#7a5814',
                border_color=AMBER,
            )
            self._safe_configure(
                self.stop_button,
                fg_color='#66172d',
                hover_color='#86203b',
                border_color=RED,
            )
        else:
            self._safe_configure(
                self.pause_button,
                fg_color='#20263a',
                hover_color='#20263a',
                border_color='#4d5570',
            )
            self._safe_configure(
                self.stop_button,
                fg_color='#20263a',
                hover_color='#20263a',
                border_color='#4d5570',
            )
        self._refresh_primary_button()


if __name__ == '__main__':
    app = LocalAppV8()
    app.mainloop()
