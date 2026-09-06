from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def banner():
    console.print(Panel.fit('[bold cyan]TELEGRAM USER MIGRATOR[/bold cyan]\nMigração administrativa via MTProto', border_style='cyan'))


def show_dialogs(dialogs):
    table = Table(title='Chats disponíveis')
    for col in ['#', 'Título', 'Tipo', 'ID', 'Username']:
        table.add_column(col)
    for i, d in enumerate(dialogs, 1):
        table.add_row(str(i), d.title, d.chat_type, str(d.id), d.username or '-')
    console.print(table)


def choose_index(total, label):
    while True:
        try:
            n = int(console.input(f'[bold]{label} [1-{total}]: [/bold]'))
            if 1 <= n <= total:
                return n - 1
        except ValueError:
            pass
        console.print('[red]Escolha inválida.[/red]')


def confirm(message):
    return console.input(f'{message} [s/N]: ').strip().lower() in {'s', 'sim', 'y', 'yes'}


def print_stats(stats):
    table = Table(title='Resultado')
    table.add_column('Indicador')
    table.add_column('Quantidade', justify='right')
    for key, value in [
        ('Processados', stats.processed), ('Adicionados', stats.added),
        ('Já membros', stats.already_member), ('Privacidade', stats.privacy),
        ('Sem permissão', stats.permissions), ('Rate limit', stats.rate_limited),
        ('Ignorados', stats.skipped), ('Erros', stats.errors),
    ]:
        table.add_row(key, str(value))
    console.print(table)
