# Interface local V3

A V3 mantém o backend e as proteções da V2 e corrige o layout observado em telas Windows com menor altura útil.

## Ajustes

- reserva altura mínima para os seis cards de métricas;
- mantém `Extraídos`, `Admins`, `Já no destino`, `Já processados`, `Fila disponível` e `Nesta rodada` visíveis;
- compacta os painéis inferiores para evitar que as métricas desapareçam;
- conecta automaticamente quando já existe uma sessão Telethon local válida;
- mantém conexão manual disponível;
- `Pausar` e `Parar` ficam visualmente neutros quando não há rodada em execução;
- continua iniciando sempre em `MODO SEGURO · DRY RUN`;
- continua exigindo nova análise após alteração de rota ou modo;
- continua retornando ao DRY RUN depois de uma rodada real.

O launcher `run_local.bat` abre `local_app_v3.py` via `pythonw.exe`.
