"""Paleta e helpers visuais da interface cyber-neon local.

Este módulo contém apenas apresentação. Nenhuma regra de Telegram, fila,
convite, limite ou histórico deve depender destas constantes.
"""

BG = '#050816'
BG_ALT = '#071020'
PANEL = '#09152b'
PANEL_ALT = '#0b1b35'
INPUT = '#0a1730'
BORDER = '#17355f'
TEXT = '#e8f4ff'
MUTED = '#7f9fbd'
CYAN = '#00e5ff'
CYAN_SOFT = '#16b8ff'
PURPLE = '#8b5cf6'
MAGENTA = '#ff2bd6'
GREEN = '#23f58b'
AMBER = '#ffbd38'
RED = '#ff426f'
WHITE = '#f8fbff'

METRIC_ACCENTS = {
    'extraidos': CYAN_SOFT,
    'admins': GREEN,
    'destino': PURPLE,
    'processados': AMBER,
    'fila': CYAN,
    'rodada': MAGENTA,
}


def metric_accent(key):
    """Retorna a cor de destaque de um card de métrica."""
    return METRIC_ACCENTS.get(key, CYAN)


def mode_palette(dry_run):
    """Cores do badge e CTA principal para modo seguro ou real."""
    if dry_run:
        return {
            'badge': GREEN,
            'badge_text': '#02170e',
            'cta': MAGENTA,
            'cta_hover': '#d91bbb',
            'label': 'MODO SEGURO • DRY RUN',
        }
    return {
        'badge': RED,
        'badge_text': WHITE,
        'cta': RED,
        'cta_hover': '#d92f59',
        'label': 'MODO REAL • ENVIO ATIVO',
    }


def activity_level_color(level):
    """Mapeia níveis visuais do log para cores neon."""
    normalized = str(level or '').strip().lower()
    if normalized in {'success', 'added', 'ok'}:
        return GREEN
    if normalized in {'warn', 'warning', 'privacy', 'restriction'}:
        return AMBER
    if normalized in {'error', 'failed', 'rate_limit'}:
        return RED
    return CYAN
