# Telegram Consent Invites

Projeto Python independente para administração de convites entre comunidades do Telegram usando MTProto/Telethon.

## Recursos

- Login de conta Telegram.
- Seleção de origem e destino.
- Leitura de membros.
- Exclusão de bots e membros já presentes no destino.
- Limite local por execução (padrão: 50).
- Intervalo configurável entre operações.
- `DRY_RUN` para análise sem enviar convites.
- Relatório CSV.
- Tratamento de privacidade, permissões, usuário já membro e limites da API.
- Respeita `FLOOD_WAIT` retornado pelo Telegram e interrompe a execução após a espera, em vez de tentar contorná-lo.

## Instalação

Python 3.10+.

```bash
python -m venv .venv
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` obtidos no portal oficial do Telegram.

Execute:

```bash
python main.py
```

Na primeira execução, o Telethon solicitará o login e poderá pedir código/2FA. A sessão fica em `sessions/` e não deve ser publicada.

## Configuração

```env
MAX_INVITES_PER_RUN=50
MIN_DELAY_SECONDS=15
MAX_DELAY_SECONDS=30
DRY_RUN=false
```

Os intervalos locais não são uma forma de contornar limites do Telegram. Se a API retornar `FLOOD_WAIT`, o programa respeita o tempo indicado.

## Relatórios

São criados em `logs/migration_YYYYMMDD_HHMMSS.csv`.

## Segurança

Nunca publique `.env` nem arquivos `.session`. Use o projeto somente em grupos/canais nos quais você tenha autorização e respeite a privacidade dos usuários e as regras do Telegram.
