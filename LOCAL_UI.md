# Interface local

A interface desktop roda inteiramente no Windows e reutiliza a sessão Telethon já configurada no projeto.

## Abrir

1. Atualize o repositório: `git pull`.
2. Garanta que `.venv` e `.env` existam.
3. Dê duplo clique em `run_local.bat` ou execute `./run_local.bat` no PowerShell.

Na primeira abertura após uma atualização, o launcher instala `customtkinter` automaticamente se necessário. Depois disso, a interface é aberta com `pythonw`, sem manter uma janela preta do terminal.

## Modo seguro por padrão

A interface sempre inicia em **MODO SEGURO / DRY RUN**, independentemente do valor salvo em `DRY_RUN` no `.env`.

Para uma rodada real, o operador precisa:

1. desligar o DRY RUN na própria janela;
2. reanalisar a fila;
3. marcar a autorização;
4. confirmar a caixa de diálogo final da rodada real.

Ao trocar origem/destino ou alternar o modo de execução, a fila preparada é invalidada e precisa ser analisada novamente.

## Fluxo

1. Clique em **Conectar / atualizar grupos**.
2. Escolha **Grupo A — origem** e **Grupo B — destino**.
3. Use **Analisar fila** para atualizar a extração e visualizar candidatos elegíveis.
4. A fila remove automaticamente:
   - administradores/owner da origem;
   - bots;
   - IDs definidos em `EXCLUDED_USER_IDS`;
   - exclusões cadastradas na aba **Exclusões**;
   - membros já presentes no destino;
   - usuários que já tiveram uma tentativa real registrada para a mesma rota.
5. Mantenha **DRY RUN** ligado para validar sem enviar operações.
6. Para uma rodada real, desligue o DRY RUN, confirme a autorização e escolha o limite da rodada.

## Progresso da rodada

A versão v2 mostra:

- modo seguro/real em destaque no cabeçalho;
- barra de progresso;
- usuário/posição atual da rodada;
- contagem regressiva até a próxima tentativa real;
- estado de pausa, retomada e parada.

Depois de uma rodada real, a interface retorna automaticamente ao **DRY RUN** e desmarca a autorização.

## Limites da interface

- máximo de 20 candidatos por rodada;
- em modo real, intervalo mínimo de 15 segundos entre tentativas;
- o intervalo pode variar dentro da faixa configurada apenas para distribuir a carga operacional;
- `FloodWait`, `PeerFlood` e erros de permissão interrompem a rodada;
- a interface não tenta contornar restrições de privacidade ou limites da API do Telegram.

## Histórico local

O arquivo `data/local_state.sqlite3` guarda apenas no computador:

- histórico de resultados;
- IDs já processados por rota;
- exclusões adicionadas pela interface.

Ele está no `.gitignore` e não é enviado ao GitHub.

## CLI continua protegido

O `python main.py` continua exigindo `TARGET_USER_IDS` quando `DRY_RUN=false`. A fila automática sem seleção manual existe apenas na interface local, que possui confirmação própria, limite por rodada e histórico persistente.
