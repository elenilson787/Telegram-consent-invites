import asyncio
import random
from datetime import datetime


def now_string() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def random_delay(min_seconds: float, max_seconds: float) -> float:
    return random.uniform(min_seconds, max_seconds) if max_seconds > min_seconds else float(min_seconds)


async def sleep_with_countdown(seconds: float, callback=None) -> None:
    remaining = int(round(seconds))
    while remaining > 0:
        if callback:
            callback(remaining)
        await asyncio.sleep(1)
        remaining -= 1


def full_name(user) -> str:
    name = ' '.join(x for x in [getattr(user, 'first_name', None), getattr(user, 'last_name', None)] if x).strip()
    return name or getattr(user, 'username', None) or str(getattr(user, 'id', ''))
