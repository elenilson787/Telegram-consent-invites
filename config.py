import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f'Variável obrigatória ausente no .env: {name}')
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session: str
    max_invites_per_run: int
    min_delay_seconds: float
    max_delay_seconds: float
    dry_run: bool

    @classmethod
    def load(cls) -> 'Settings':
        api_id = int(required('TELEGRAM_API_ID'))
        api_hash = required('TELEGRAM_API_HASH')
        session = os.getenv('TELEGRAM_SESSION', 'sessions/main').strip() or 'sessions/main'

        # Defaults deliberadamente seguros: sem configuração explícita,
        # nenhuma adição real é enviada e a rodada fica limitada a 5 candidatos.
        max_invites = int(os.getenv('MAX_INVITES_PER_RUN', '5'))
        min_delay = float(os.getenv('MIN_DELAY_SECONDS', '15'))
        max_delay = float(os.getenv('MAX_DELAY_SECONDS', '30'))
        dry_run = os.getenv('DRY_RUN', 'true').lower() in {'1', 'true', 'yes', 'sim'}

        if api_id <= 0:
            raise ValueError('TELEGRAM_API_ID deve ser um inteiro positivo.')
        if max_invites < 1 or min_delay < 0 or max_delay < min_delay:
            raise ValueError('Configuração de limite/delay inválida.')

        Path(session).parent.mkdir(parents=True, exist_ok=True)
        Path('logs').mkdir(exist_ok=True)
        return cls(api_id, api_hash, session, max_invites, min_delay, max_delay, dry_run)
