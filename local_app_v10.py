"""V10: aumenta o teto configurável por rodada sem alterar o motor de convites.

A interface anterior limitava localmente o campo "Limite da rodada" a 20.
Esta versão eleva somente esse teto da GUI para 100, preservando DRY RUN,
confirmação explícita, intervalo mínimo real, filtros e interrupções por limites
do Telegram.
"""

import local_app
import local_app_v2

# Teto da interface. O operador continua escolhendo o tamanho efetivo da rodada
# no campo "Limite da rodada"; não significa que 100 usuários serão sempre
# processados, pois a execução pode parar antes diante de restrições da API.
MAX_GUI_BATCH = 100
local_app.MAX_GUI_BATCH = MAX_GUI_BATCH
local_app_v2.MAX_GUI_BATCH = MAX_GUI_BATCH

from local_app_v9 import LocalAppV9


class LocalAppV10(LocalAppV9):
    """V9 com teto de lote configurável ampliado de 20 para 100."""


if __name__ == '__main__':
    app = LocalAppV10()
    app.mainloop()
