# Telegram Consent Invites

Projeto Python independente para administração controlada de convites entre comunidades do Telegram usando MTProto/Telethon.

## Fluxo

1. Conectar a conta Telegram.
2. Listar grupos/canais acessíveis.
3. Escolher o Grupo A (origem).
4. Tentar enumerar os participantes que a API disponibiliza para a conta autenticada.
5. Salvar a extração em JSON e CSV.
6. Escolher o Grupo B (destino autorizado).
7. Enumerar o destino e excluir bots e usuários que já são membros.
8. Executar primeiro em `DRY_RUN`.
9. Somente depois, se autorizado, habilitar tentativas reais limitadas.
10. Registrar o resultado individual em CSV.

O usuário **não precisa ser administrador do Grupo A**. A extração é tentada sempre que a API do Telegram permitir enumerar os participantes daquele chat. Isso não garante que todos os membros estarão acessíveis e não representa autorização automática para adicioná-los a outro grupo.

## Recursos

- Login de conta Telegram.
- Seleção de origem e destino.
- Leitura dos membros acessíveis.
- Extração reutilizável em JSON e CSV.
- Exclusão de bots e membros já presentes no destino.
- Limite local por execução.
- Intervalo configurável entre operações reais.
- `DRY_RUN` que não envia nenhuma solicitação de convite.
- Relatório CSV por usuário.
- Tratamento de privacidade, permissões, usuário já membro e limites da API.
- Interrupção segura em `FloodWait` e `PeerFlood`, sem bypass ou repetição automática.
- Suporte separado a supergrupos/canais e grupos básicos do Telegram.

## Instalação

Requer Python 3.10+.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Preencha no `.env` apenas as suas credenciais obtidas no portal oficial do Telegram:

```env
TELEGRAM_API_ID=SEU_API_ID
TELEGRAM_API_HASH=SEU_API_HASH
TELEGRAM_SESSION=sessions/main

MAX_INVITES_PER_RUN=5
MIN_DELAY_SECONDS=15
MAX_DELAY_SECONDS=30
DRY_RUN=true
```

A configuração de exemplo é deliberadamente segura: **DRY RUN ativo e no máximo 5 candidatos por rodada**.

Execute:

```bash
python main.py
```

Na primeira execução, o Telethon solicitará login e poderá pedir código/2FA. A sessão fica em `sessions/` e não deve ser publicada.

## Primeiro teste obrigatório — DRY RUN

Mantenha:

```env
DRY_RUN=true
MAX_INVITES_PER_RUN=5
```

O teste é considerado bem-sucedido quando:

- a conta conecta;
- os grupos são listados;
- o Grupo A pode ser selecionado sem exigir administração;
- os participantes acessíveis são extraídos;
- JSON e CSV são gravados;
- o Grupo B pode ser selecionado;
- os membros já existentes no destino são detectados;
- bots são ignorados separadamente;
- os candidatos aparecem no relatório como `dry_run`;
- **nenhuma solicitação de convite é enviada**.

Os arquivos de extração são criados em `data/` e preservam, quando disponíveis:

```text
user_id
access_hash
first_name
last_name
username
bot
source_group_id
source_group_title
extracted_at
```

Os relatórios da rodada são criados em `logs/migration_YYYYMMDD_HHMMSS.csv`.

## Segundo teste — adição real controlada

Somente depois de validar o DRY RUN, altere conscientemente:

```env
DRY_RUN=false
MAX_INVITES_PER_RUN=5
```

O programa ainda solicitará confirmação antes de qualquer tentativa real.

Resultados possíveis incluem:

- `added`
- `already_member`
- `privacy`
- `not_mutual_contact`
- `user_limit`
- `kicked`
- `permission_error`
- `flood_wait`
- `peer_flood`
- `error`

Se o Telegram retornar `FloodWait`, a rodada é interrompida e o relatório registra o prazo indicado. O programa não tenta novamente automaticamente. `PeerFlood` e falta de permissão também interrompem a rodada.

## Segurança

Nunca publique:

- `.env`
- `*.session`
- `sessions/`

Não implemente bypass de privacidade, `FloodWait`, `PeerFlood`, bloqueios ou outras proteções do Telegram. Use o projeto somente com a conta autenticada do próprio operador e em destinos nos quais exista autorização para realizar a operação.

## Testes automatizados

```bash
python -m compileall -q .
python -m unittest discover -s tests -p "test_*.py" -v
```

O GitHub Actions executa compilação e testes unitários em Python 3.10 e 3.12.
