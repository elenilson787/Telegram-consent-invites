import csv
import json
from datetime import datetime, timezone
from pathlib import Path


EXTRACTION_FIELDS = [
    'user_id',
    'access_hash',
    'first_name',
    'last_name',
    'username',
    'bot',
    'source_group_id',
    'source_group_title',
    'extracted_at',
]


def user_record(user, source):
    return {
        'user_id': user.id,
        'access_hash': getattr(user, 'access_hash', None),
        'first_name': getattr(user, 'first_name', None),
        'last_name': getattr(user, 'last_name', None),
        'username': getattr(user, 'username', None),
        'bot': bool(getattr(user, 'bot', False)),
        'source_group_id': source.id,
        'source_group_title': getattr(source, 'title', str(source)),
        'extracted_at': datetime.now(timezone.utc).isoformat(),
    }


def save_members(users, source, output_dir='data'):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    records = [user_record(u, source) for u in users]
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = Path(output_dir) / f'membros_{stamp}.json'
    csv_path = Path(output_dir) / f'membros_{stamp}.csv'

    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=EXTRACTION_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    return json_path, csv_path, records
