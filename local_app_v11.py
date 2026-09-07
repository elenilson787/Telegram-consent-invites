"""V11: adiciona geração/cópia de link de convite do Grupo B.

Mantém integralmente o comportamento da V10 e acrescenta uma alternativa de
entrada voluntária no destino, útil quando convites diretos via API estão
limitados pelo Telegram.
"""

from tkinter import messagebox

import customtkinter as ctk

from local_app_v10 import LocalAppV10


class LocalAppV11(LocalAppV10):
    """V10 com ação de gerar/copiar link de convite do destino."""

    def __init__(self):
        super().__init__()
        if not self.winfo_exists():
            return
        self._install_destination_invite_action()

    def _install_destination_invite_action(self):
        route = self.destination_combo.master
        route.grid_columnconfigure(0, weight=1)
        route.grid_columnconfigure(1, weight=0)

        self.invite_link_button = ctk.CTkButton(
            route,
            text='🔗 Link convite',
            command=self._create_destination_invite_link,
            width=126,
            height=28,
        )
        self.invite_link_button.grid(
            row=4,
            column=1,
            padx=(6, 14),
            pady=(0, 8),
            sticky='e',
        )

        # Reserva espaço para o botão sem comprimir demais o seletor do destino.
        try:
            self.destination_combo.grid_configure(padx=(16, 6))
        except Exception:
            pass

        # Reaplica o acabamento visual da V8/V9 ao novo botão.
        if hasattr(self, '_safe_configure'):
            self._safe_configure(
                self.invite_link_button,
                fg_color='#0b4f78',
                hover_color='#086d9e',
                border_width=1,
                border_color='#00d9ff',
                text_color='white',
            )

    def _create_destination_invite_link(self):
        if self.running:
            return
        if self.service is None:
            messagebox.showwarning(
                'Link de convite',
                'Conecte ao Telegram antes de gerar o link do grupo destino.',
            )
            return

        destination = self.dialog_map.get(self.destination_combo.get())
        if destination is None:
            messagebox.showwarning(
                'Link de convite',
                'Selecione o Grupo B — destino antes de gerar o link.',
            )
            return

        self.invite_link_button.configure(state='disabled', text='Gerando...')
        self._set_status(f'Gerando link de convite para {destination.title}...')
        self._submit(
            self._export_destination_invite(destination),
            self._after_export_destination_invite,
        )

    async def _export_destination_invite(self, destination):
        link = await self.service.export_invite_link(destination.entity)
        return destination, link

    def _after_export_destination_invite(self, future):
        self.invite_link_button.configure(state='normal', text='🔗 Link convite')
        try:
            destination, link = future.result()
        except Exception as exc:
            self._set_status('Não foi possível gerar o link de convite.')
            self._append_log(
                f'ERRO ao gerar link de convite: {type(exc).__name__}: {exc}'
            )
            messagebox.showerror(
                'Link de convite',
                'Não foi possível gerar o link do grupo destino.\n\n'
                'A conta conectada precisa ser administradora do destino e ter '
                f'permissão para convidar usuários.\n\nDetalhe: {type(exc).__name__}: {exc}',
            )
            return

        self.clipboard_clear()
        self.clipboard_append(link)
        self.update_idletasks()
        self._set_status('Link de convite copiado para a área de transferência.')
        self._append_log(
            f'Link de convite do destino gerado e copiado: {destination.title}.'
        )
        messagebox.showinfo(
            'Link de convite',
            f'Link do grupo "{destination.title}" copiado para a área de transferência:\n\n{link}',
        )


if __name__ == '__main__':
    app = LocalAppV11()
    app.mainloop()
