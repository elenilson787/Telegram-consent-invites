"""Política conservadora de segurança para limites do Telegram.

O Telegram não publica um teto universal confiável para convites. Este módulo
não tenta prever nem contornar os mecanismos anti-spam. Ele transforma sinais
reais registrados no histórico (PeerFlood/FloodWait) em pausas internas do
Telegram Extractor, evitando novas tentativas enquanto a conta está em risco.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


PEER_FLOOD_WINDOW_DAYS = 14
PEER_FLOOD_BACKOFF_HOURS = (24, 72, 168)  # 1º, 2º, 3º+ evento recente
RECOVERY_CAUTION_HOURS = 24


@dataclass(frozen=True)
class ActionSafetyState:
    mode: str
    blocked: bool
    kind: str
    until: datetime | None
    peer_flood_count: int
    last_peer_flood_at: datetime | None
    last_restriction_at: datetime | None
    recovery_caution: bool = False

    @property
    def until_iso(self) -> str:
        return self.until.isoformat(timespec='seconds') if self.until else ''


def _now_local() -> datetime:
    return datetime.now().astimezone()


def parse_timestamp(value) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_now_local().tzinfo)
    return parsed.astimezone()


def parse_flood_wait_until(reason: str) -> datetime | None:
    match = re.search(r'Não retomar antes de (.+?)\.?$', str(reason or '').strip())
    if not match:
        return None
    return parse_timestamp(match.group(1).strip())


def peer_flood_pause_hours(recent_count: int) -> int:
    count = max(1, int(recent_count))
    if count == 1:
        return PEER_FLOOD_BACKOFF_HOURS[0]
    if count == 2:
        return PEER_FLOOD_BACKOFF_HOURS[1]
    return PEER_FLOOD_BACKOFF_HOURS[2]


def _status_names(mode: str) -> tuple[str, str]:
    if mode == 'message':
        return 'message_peer_flood', 'message_flood_wait'
    return 'peer_flood', 'flood_wait'


def compute_action_safety(rows, mode: str = 'direct', now: datetime | None = None) -> ActionSafetyState:
    """Calcula a pausa vigente a partir do histórico da própria conta.

    PeerFlood usa backoff interno conservador: 24h no primeiro evento recente,
    72h no segundo e 7 dias a partir do terceiro. A contagem considera eventos
    dentro de 14 dias do PeerFlood mais recente; após uma janela limpa, reinicia.

    FloodWait sempre respeita o horário explícito informado pelo Telegram.
    """
    now = (now or _now_local()).astimezone()
    peer_status, wait_status = _status_names(mode)

    peer_events: list[datetime] = []
    wait_events: list[tuple[datetime, datetime]] = []

    for row in list(rows or []):
        status = str(row.get('status') or '')
        timestamp = parse_timestamp(row.get('timestamp'))
        if timestamp is None:
            continue
        if status == peer_status:
            peer_events.append(timestamp)
        elif status == wait_status:
            until = parse_flood_wait_until(row.get('reason') or '')
            if until is not None:
                wait_events.append((timestamp, until))

    peer_events.sort(reverse=True)
    wait_events.sort(key=lambda item: item[0], reverse=True)

    latest_peer = peer_events[0] if peer_events else None
    recent_count = 0
    peer_until = None
    if latest_peer is not None:
        window_start = latest_peer - timedelta(days=PEER_FLOOD_WINDOW_DAYS)
        recent_count = sum(1 for event in peer_events if event >= window_start)
        peer_until = latest_peer + timedelta(hours=peer_flood_pause_hours(recent_count))

    active_waits = [(event_at, until) for event_at, until in wait_events if until > now]
    latest_wait_at = wait_events[0][0] if wait_events else None
    wait_until = max((until for _event_at, until in active_waits), default=None)

    candidates: list[tuple[str, datetime]] = []
    if peer_until is not None and peer_until > now:
        candidates.append(('peer_flood', peer_until))
    if wait_until is not None and wait_until > now:
        candidates.append(('flood_wait', wait_until))

    kind = ''
    until = None
    if candidates:
        kind, until = max(candidates, key=lambda item: item[1])

    restriction_dates = [value for value in (latest_peer, latest_wait_at) if value is not None]
    last_restriction = max(restriction_dates) if restriction_dates else None

    recovery_caution = bool(
        latest_peer
        and peer_until
        and now >= peer_until
        and now < peer_until + timedelta(hours=RECOVERY_CAUTION_HOURS)
    )

    return ActionSafetyState(
        mode=mode,
        blocked=until is not None,
        kind=kind,
        until=until,
        peer_flood_count=recent_count,
        last_peer_flood_at=latest_peer,
        last_restriction_at=last_restriction,
        recovery_caution=recovery_caution,
    )


def format_local_datetime(value: datetime | None) -> str:
    if value is None:
        return 'horário não disponível'
    return value.astimezone().strftime('%d/%m/%Y %H:%M')
