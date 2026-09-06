import asyncio
import sys
from config import Settings
from migrator import MigrationEngine
from report import ReportWriter
from telegram_client import TelegramService
from ui import banner, choose_index, confirm, console, print_stats
from utils import full_name


async def main():
    banner()
    try:
        settings = Settings.load()
    except Exception as exc:
        console.print(f'[red]{exc}[/red]')
        return 1

    service = TelegramService(settings.api_id, settings.api_hash, settings.session)
    try:
        console.print('[cyan]Conectando ao Telegram...[/cyan]')
        me = await service.connect()
        console.print(f'[green]✓ Conectado como {full_name(me)} (ID {me.id})[/green]')

        dialogs = await service.list_dialogs()
        if len(dialogs) < 2:
            console.print('[red]São necessários pelo menos dois grupos/canais.[/red]')
            return 1
        from ui import show_dialogs
        show_dialogs(dialogs)
        source = dialogs[choose_index(len(dialogs), 'Origem')]
        destination = dialogs[choose_index(len(dialogs), 'Destino')]
        if source.id == destination.id:
            console.print('[red]Origem e destino não podem ser iguais.[/red]')
            return 1

        console.print(f'Origem: [bold]{source.title}[/bold]')
        console.print(f'Destino: [bold]{destination.title}[/bold]')
        if not confirm('Confirma que administra/tem autorização para operar nesses grupos?'):
            return 0

        console.print('[cyan]Lendo membros da origem...[/cyan]')
        members = await service.get_members(source.entity)
        destination_ids = await service.get_member_ids(destination.entity)
        eligible = [u for u in members if u.id not in destination_ids and not getattr(u, 'bot', False)]
        console.print(f'Membros na origem: {len(members)} | Já no destino: {len(members)-len(eligible)} | Elegíveis: {len(eligible)}')

        report = ReportWriter()
        try:
            dry = settings.dry_run
            if not dry and not confirm('Iniciar as tentativas de adição?'):
                return 0
            if dry:
                console.print('[yellow]DRY_RUN ativo: nenhuma adição será enviada.[/yellow]')
            engine = MigrationEngine(service.client, destination.entity, settings.max_invites_per_run, settings.min_delay_seconds, settings.max_delay_seconds)
            stats = await engine.run(eligible, report, dry_run=dry)
            print_stats(stats)
            console.print(f'[green]✓ Relatório: {report.path}[/green]')
        finally:
            report.close()
        return 0
    except KeyboardInterrupt:
        console.print('[yellow]Interrompido pelo usuário.[/yellow]')
        return 130
    except Exception as exc:
        console.print(f'[red]{type(exc).__name__}: {exc}[/red]')
        return 1
    finally:
        await service.disconnect()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
