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


def parse_user_ids(value: str, variable_name: str = 'USER_IDS') -> frozenset[int]:
    ids: set[int] = set()
    for item in value.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            user_id = int(item)
        except ValueError as exc:
            raise ValueError(
                f'{variable_name} contém um ID inválido: {item!r}. '
                'Use apenas IDs numéricos separados por vírgula.'
            ) from exc
        if user_id <= 0:
            raise ValueError(f'{variable_name} aceita apenas IDs positivos.')
        ids.add(user_id)
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session: str
    max_invites_per_run: int
    min_delay_seconds: float
    max_delay_seconds: float
    dry_run: bool
    excluded_user_ids: frozenset[int]
    target_user_ids: frozenset[int]

    @property
    def telegram_app_provisioned(self) -> bool:
        return self.api_id > 0 and bool(self.api_hash.strip())

    @classmethod
    def load(cls, require_explicit_targets: bool = True) -> 'Settings':
        """Carrega a configuração local.

        O CLI mantém ``require_explicit_targets=True`` por padrão e exige as
        credenciais técnicas do aplicativo Telegram. A interface desktop usa
        ``False``: ela pode abrir antes do provisionamento para mostrar onboarding
        e gerenciamento de contas. O envio/conexão só é liberado quando as
        credenciais do aplicativo estiverem disponíveis.
        """
        raw_api_id = os.getenv('TELEGRAM_API_ID', '').strip()
        raw_api_hash = os.getenv('TELEGRAM_API_HASH', '').strip()

        if require_explicit_targets:
            api_id = int(required('TELEGRAM_API_ID'))
            api_hash = required('TELEGRAM_API_HASH')
        else:
            try:
                api_id = int(raw_api_id) if raw_api_id else 0
            except ValueError as exc:
                raise ValueError('TELEGRAM_API_ID deve ser um inteiro positivo.') from exc
            api_hash = raw_api_hash

        session = os.getenv('TELEGRAM_SESSION', 'sessions/main').strip() or 'sessions/main'

        max_invites = int(os.getenv('MAX_INVITES_PER_RUN', '5'))
        min_delay = float(os.getenv('MIN_DELAY_SECONDS', '15'))
        max_delay = float(os.getenv('MAX_DELAY_SECONDS', '30'))
        dry_run = os.getenv('DRY_RUN', 'true').lower() in {'1', 'true', 'yes', 'sim'}
        excluded_user_ids = parse_user_ids(
            os.getenv('EXCLUDED_USER_IDS', ''),
            'EXCLUDED_USER_IDS',
        )
        target_user_ids = parse_user_ids(
            os.getenv('TARGET_USER_IDS', ''),
            'TARGET_USER_IDS',
        )

        if api_id < 0:
            raise ValueError('TELEGRAM_API_ID deve ser um inteiro positivo.')
        if raw_api_id and api_id == 0:
            raise ValueError('TELEGRAM_API_ID deve ser maior que zero.')
        if require_explicit_targets and api_id <= 0:
            raise ValueError('TELEGRAM_API_ID deve ser um inteiro positivo.')
        if require_explicit_targets and not api_hash:
            raise ValueError('TELEGRAM_API_HASH é obrigatório.')
        if max_invites < 1 or min_delay < 0 or max_delay < min_delay:
            raise ValueError('Configuração de limite/delay inválida.')
        overlap = excluded_user_ids & target_user_ids
        if overlap:
            ids = ', '.join(str(x) for x in sorted(overlap))
            raise ValueError(
                f'Os mesmos IDs não podem estar em EXCLUDED_USER_IDS e TARGET_USER_IDS: {ids}'
            )
        if require_explicit_targets and not dry_run and not target_user_ids:
            raise ValueError(
                'DRY_RUN=false exige TARGET_USER_IDS. '
                'Defina explicitamente os usuários autorizados para a tentativa real.'
            )
        if require_explicit_targets and not dry_run and len(target_user_ids) > max_invites:
            raise ValueError(
                'TARGET_USER_IDS contém mais usuários do que MAX_INVITES_PER_RUN. '
                'Aumente o limite conscientemente ou reduza os alvos.'
            )

        Path(session).parent.mkdir(parents=True, exist_ok=True)
        Path('logs').mkdir(exist_ok=True)
        Path('data').mkdir(exist_ok=True)
        return cls(
            api_id,
            api_hash,
            session,
            max_invites,
            min_delay,
            max_delay,
            dry_run,
            excluded_user_ids,
            target_user_ids,
        )
