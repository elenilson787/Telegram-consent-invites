from pathlib import Path

import customtkinter as ctk

from local_app_v2 import LocalAppV2


class LocalAppV3(LocalAppV2):
    """Terceira versão da interface local.

    Ajusta o layout para resoluções menores, mantém as métricas sempre visíveis
    e reconecta automaticamente quando uma sessão Telethon local já existe.
    """

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return

        self._compact_operation_layout()
        self._apply_idle_button_style()
        self.after(350, self._auto_connect_existing_session)

    def _compact_operation_layout(self):
        tab = self.tabs.tab('Operação')

        # A linha 4 contém os seis cards de métricas. Na V2 ela podia ser
        # comprimida até desaparecer quando a janela tinha pouca altura útil.
        tab.grid_rowconfigure(4, minsize=76, weight=0)
        tab.grid_rowconfigure(5, minsize=135, weight=1)

        # Deixa os cards inferiores compactos, preservando espaço para métricas.
        for child in tab.winfo_children():
            info = child.grid_info()
            if not info or 'row' not in info:
                continue
            row = int(info['row'])
            if row == 5:
                child.grid_configure(pady=(2, 4))

        # Aumenta um pouco a área útil sem exigir tela cheia.
        self.geometry('1240x840')

    def _session_file_exists(self):
        session = Path(self.settings.session)
        candidates = [session]
        if session.suffix != '.session':
            candidates.append(Path(str(session) + '.session'))
        return any(path.exists() for path in candidates)

    def _auto_connect_existing_session(self):
        if self.running or self.service is not None:
            return
        if not self._session_file_exists():
            return
        self._append_log('Sessão local encontrada. Conectando automaticamente...')
        self._connect()

    def _set_running_controls(self, running):
        super()._set_running_controls(running)
        if running:
            self.pause_button.configure(fg_color='#7c3aed', hover_color='#6d28d9')
            self.stop_button.configure(fg_color='#b91c1c', hover_color='#991b1b')
        else:
            self._apply_idle_button_style()

    def _apply_idle_button_style(self):
        # Botões indisponíveis ficam visualmente neutros, não apenas com texto cinza.
        self.pause_button.configure(fg_color='#3f3f46', hover_color='#3f3f46')
        self.stop_button.configure(fg_color='#3f3f46', hover_color='#3f3f46')

    def _after_connect(self, future):
        super()._after_connect(future)
        if self.connection_badge.cget('text') == '● Conectado':
            self._set_status('Conectado. Escolha a rota e analise a fila.')


if __name__ == '__main__':
    app = LocalAppV3()
    app.mainloop()
