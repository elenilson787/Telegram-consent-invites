import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


class StateStore:
    """Persistência local de histórico, exclusões, mensagens e métricas operacionais."""

    def __init__(self, path='data/local_state.sqlite3'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempt_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    destination_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    name TEXT,
                    status TEXT NOT NULL,
                    reason TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_history_route_user
                    ON attempt_history(source_id, destination_id, user_id);

                CREATE TABLE IF NOT EXISTS exclusions (
                    user_id INTEGER PRIMARY KEY,
                    note TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    destination_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    name TEXT,
                    status TEXT NOT NULL,
                    reason TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_message_history_route_user
                    ON message_history(source_id, destination_id, user_id);
                """
            )

    def add_exclusion(self, user_id: int, note: str = ''):
        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError('O user_id deve ser positivo.')
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO exclusions(user_id, note, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    note=excluded.note
                """,
                (user_id, note.strip(), datetime.now().astimezone().isoformat(timespec='seconds')),
            )

    def remove_exclusion(self, user_id: int):
        with self._connect() as connection:
            connection.execute('DELETE FROM exclusions WHERE user_id = ?', (int(user_id),))

    def excluded_ids(self) -> set[int]:
        with self._connect() as connection:
            rows = connection.execute('SELECT user_id FROM exclusions').fetchall()
        return {int(row['user_id']) for row in rows}

    def list_exclusions(self):
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT user_id, note, created_at FROM exclusions ORDER BY created_at DESC'
            ).fetchall()
        return [dict(row) for row in rows]

    def record_attempt(
        self,
        source_id: int,
        destination_id: int,
        user_id: int,
        username: str | None,
        name: str | None,
        status: str,
        reason: str = '',
    ):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO attempt_history(
                    timestamp, source_id, destination_id, user_id,
                    username, name, status, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().astimezone().isoformat(timespec='seconds'),
                    int(source_id),
                    int(destination_id),
                    int(user_id),
                    username or '',
                    name or '',
                    status,
                    reason or '',
                ),
            )

    def processed_ids(self, source_id: int, destination_id: int) -> set[int]:
        """IDs que já tiveram uma tentativa real nesta rota.

        DRY RUN não bloqueia o usuário para rodadas futuras.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT user_id
                FROM attempt_history
                WHERE source_id = ?
                  AND destination_id = ?
                  AND status <> 'dry_run'
                """,
                (int(source_id), int(destination_id)),
            ).fetchall()
        return {int(row['user_id']) for row in rows}

    def recent_history(self, limit: int = 100):
        limit = max(1, min(int(limit), 1000))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, source_id, destination_id, user_id,
                       username, name, status, reason
                FROM attempt_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def status_counts(self):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS quantity
                FROM attempt_history
                WHERE status <> 'dry_run'
                GROUP BY status
                ORDER BY quantity DESC
                """
            ).fetchall()
        return {row['status']: int(row['quantity']) for row in rows}

    def record_message_attempt(
        self,
        source_id: int,
        destination_id: int,
        user_id: int,
        username: str | None,
        name: str | None,
        status: str,
        reason: str = '',
    ):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO message_history(
                    timestamp, source_id, destination_id, user_id,
                    username, name, status, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().astimezone().isoformat(timespec='seconds'),
                    int(source_id),
                    int(destination_id),
                    int(user_id),
                    username or '',
                    name or '',
                    status,
                    reason or '',
                ),
            )

    def messaged_ids(self, source_id: int, destination_id: int) -> set[int]:
        """Evita repetir mensagens reais na mesma rota.

        Simulações não contam como contato realizado.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT user_id
                FROM message_history
                WHERE source_id = ?
                  AND destination_id = ?
                  AND status <> 'message_dry_run'
                """,
                (int(source_id), int(destination_id)),
            ).fetchall()
        return {int(row['user_id']) for row in rows}

    def recent_message_history(self, limit: int = 100):
        limit = max(1, min(int(limit), 1000))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, source_id, destination_id, user_id,
                       username, name, status, reason
                FROM message_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_day(day_value=None) -> str:
        if day_value is None:
            return datetime.now().astimezone().date().isoformat()
        if isinstance(day_value, datetime):
            return day_value.astimezone().date().isoformat()
        if isinstance(day_value, date):
            return day_value.isoformat()
        return str(day_value)[:10]

    def activity_counts_for_day(self, day_value=None) -> dict:
        """Resumo exato das operações reais de um dia no banco desta conta."""
        day = self._normalize_day(day_value)
        with self._connect() as connection:
            attempt_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS quantity
                FROM attempt_history
                WHERE substr(timestamp, 1, 10) = ?
                  AND status <> 'dry_run'
                GROUP BY status
                """,
                (day,),
            ).fetchall()
            message_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS quantity
                FROM message_history
                WHERE substr(timestamp, 1, 10) = ?
                  AND status <> 'message_dry_run'
                GROUP BY status
                """,
                (day,),
            ).fetchall()

        attempts = {row['status']: int(row['quantity']) for row in attempt_rows}
        messages = {row['status']: int(row['quantity']) for row in message_rows}
        direct_total = sum(attempts.values())
        message_total = sum(messages.values())
        rate_limit_statuses = {'peer_flood', 'flood_wait'}
        message_rate_limit_statuses = {'message_peer_flood', 'message_flood_wait'}

        return {
            'day': day,
            'direct_attempts': direct_total,
            'added': int(attempts.get('added', 0)),
            'direct_rate_limits': sum(attempts.get(status, 0) for status in rate_limit_statuses),
            'direct_errors': int(attempts.get('error', 0)),
            'messages_attempted': message_total,
            'messages_sent': int(messages.get('message_sent', 0)),
            'message_rate_limits': sum(messages.get(status, 0) for status in message_rate_limit_statuses),
            'message_errors': int(messages.get('message_error', 0)),
            'attempt_statuses': attempts,
            'message_statuses': messages,
        }

    def activity_series(self, days: int = 7) -> list[dict]:
        """Retorna resumos diários, do mais antigo para hoje."""
        days = max(1, min(int(days), 90))
        today = datetime.now().astimezone().date()
        return [
            self.activity_counts_for_day(today - timedelta(days=offset))
            for offset in range(days - 1, -1, -1)
        ]
