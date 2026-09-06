from ui_presenter import format_activity_line, parse_activity_status, status_bucket


def test_formats_added_result():
    line = 'Deise Silva: added — Convite aceito pela API.'
    assert format_activity_line(line) == '✓ Deise Silva · Adicionada'
    assert parse_activity_status(line) == (
        'Deise Silva',
        'added',
        'Convite aceito pela API.',
    )
    assert status_bucket('added') == 'success'


def test_formats_privacy_result():
    assert format_activity_line('Maria: privacy — restricted') == '⚠ Maria · Privacidade'
    assert status_bucket('privacy') == 'restriction'


def test_non_result_line_is_preserved():
    line = 'Fila preparada. Extraídos=538.'
    assert parse_activity_status(line) is None
    assert format_activity_line(line) == line


def test_unknown_status_is_preserved():
    line = 'Maria: qualquer_status — detalhe'
    assert parse_activity_status(line) is None
    assert format_activity_line(line) == line
