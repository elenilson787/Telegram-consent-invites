import json
from pathlib import Path

DEFAULT_UI_PREFERENCES_PATH = Path('data/ui_preferences.json')


def load_ui_preferences(path=DEFAULT_UI_PREFERENCES_PATH):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_ui_preferences(source_id, destination_id, path=DEFAULT_UI_PREFERENCES_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'source_id': int(source_id),
        'destination_id': int(destination_id),
    }
    temp_path = path.with_suffix(path.suffix + '.tmp')
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    temp_path.replace(path)
    return payload
