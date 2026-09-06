KNOWN_STATUSES = {
    'dry_run',
    'added',
    'already_member',
    'privacy',
    'not_mutual_contact',
    'user_limit',
    'kicked',
    'permission_error',
    'flood_wait',
    'peer_flood',
    'error',
}

STATUS_PRESENTATION = {
    'dry_run': ('◌', 'Simulação', 'neutral'),
    'added': ('✓', 'Adicionada', 'success'),
    'already_member': ('↪', 'Já era membro', 'ignored'),
    'privacy': ('⚠', 'Privacidade', 'restriction'),
    'not_mutual_contact': ('⚠', 'Contato não permitido', 'restriction'),
    'user_limit': ('↪', 'Limite do usuário', 'ignored'),
    'kicked': ('↪', 'Usuário bloqueado no grupo', 'ignored'),
    'permission_error': ('⛔', 'Sem permissão', 'restriction'),
    'flood_wait': ('⏱', 'Rate limit do Telegram', 'restriction'),
    'peer_flood': ('⏱', 'Rate limit do Telegram', 'restriction'),
    'error': ('✕', 'Erro', 'error'),
}


def parse_activity_status(text):
    """Retorna (nome, status, motivo) para linhas de resultado do migrador."""
    if ': ' not in text:
        return None
    name, rest = text.split(': ', 1)
    status, separator, reason = rest.partition(' — ')
    if status not in KNOWN_STATUSES:
        return None
    return name.strip(), status, reason.strip() if separator else ''


def format_activity_line(text):
    parsed = parse_activity_status(text)
    if not parsed:
        return text
    name, status, _ = parsed
    icon, label, _bucket = STATUS_PRESENTATION[status]
    return f'{icon} {name} · {label}'


def status_bucket(status):
    presentation = STATUS_PRESENTATION.get(status)
    return presentation[2] if presentation else None
