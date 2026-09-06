from ui_preferences import load_ui_preferences, save_ui_preferences


def test_missing_preferences_return_empty_dict(tmp_path):
    path = tmp_path / 'prefs.json'
    assert load_ui_preferences(path) == {}


def test_preferences_round_trip(tmp_path):
    path = tmp_path / 'prefs.json'
    saved = save_ui_preferences(123, 456, path)
    assert saved == {'source_id': 123, 'destination_id': 456}
    assert load_ui_preferences(path) == saved


def test_invalid_preferences_are_ignored(tmp_path):
    path = tmp_path / 'prefs.json'
    path.write_text('{invalid json', encoding='utf-8')
    assert load_ui_preferences(path) == {}
