from dataclasses import dataclass
from typing import Optional


@dataclass
class MigrationStats:
    processed: int = 0
    added: int = 0
    already_member: int = 0
    privacy: int = 0
    permissions: int = 0
    rate_limited: int = 0
    skipped: int = 0
    errors: int = 0
    stopped: bool = False
