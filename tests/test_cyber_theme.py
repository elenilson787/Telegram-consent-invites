from cyber_theme import (
    AMBER,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    activity_level_color,
    metric_accent,
    mode_palette,
)


def test_metric_accents_are_stable():
    assert metric_accent('extraidos')
    assert metric_accent('admins') == GREEN
    assert metric_accent('processados') == AMBER
    assert metric_accent('rodada') == MAGENTA
    assert metric_accent('desconhecido') == CYAN


def test_safe_and_real_mode_palettes_are_distinct():
    safe = mode_palette(True)
    real = mode_palette(False)

    assert safe['badge'] == GREEN
    assert safe['cta'] == MAGENTA
    assert 'DRY RUN' in safe['label']

    assert real['badge'] == RED
    assert real['cta'] == RED
    assert 'ENVIO ATIVO' in real['label']


def test_activity_level_colors():
    assert activity_level_color('success') == GREEN
    assert activity_level_color('privacy') == AMBER
    assert activity_level_color('error') == RED
    assert activity_level_color('info') == CYAN
