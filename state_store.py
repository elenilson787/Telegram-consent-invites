import sqlite3
from datetime import datetime
from pathlib import Path


class StateStore:
    """Persistência local de histórico e exclusões para a interface desktop."""

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
