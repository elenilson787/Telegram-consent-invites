import asyncio
import sys
from config import Settings
from extractor import save_members
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

        # A origem pode ser um grupo do qual a conta é apenas participante.
        # A API do Telegram determina se os participantes estão enumeráveis.
        console.print('[cyan]Lendo membros da origem...[/cyan]')
        try:
            members = await service.get_members(source.entity)
        except Exception as exc:
            console.print(f'[red]Não foi possível listar os participantes da origem: {type(exc).__name__}: {exc}[/red]')
            return 1

        if not members:
            console.print('[yellow]Nenhum participante acessível foi encontrado.[/yellow]')
            return 0

        # Salva os dados extraídos antes de qualquer tentativa de adição.
        json_path, csv_path, records = save_members(members, source.entity)
        console.print(f'[green]✓ Extração salva em:[/green] {json_path}')
        console.print(f'[green]✓ Cópia CSV salva em:[/green] {csv_path}')
        console.print(f'Participantes extraídos: [bold]{len(records)}[/bold]')

        destination_ids = await service.get_member_ids(destination.entity)
        eligible = [u for u in members if u.id not in destination_ids and not getattr(u, 'bot', False)]
        console.print(f'Já no destino: {len(members)-len(eligible)} | Candidatos para tentativa: {len(eligible)}')

        if not confirm('Você administra/tem autorização para adicionar participantes no grupo de destino?'):
            console.print('[yellow]Extração concluída; nenhuma tentativa de adição foi feita.[/yellow]')
            return 0

        report = ReportWriter()
        try:
            dry = settings.dry_run
            if not dry and not confirm('Iniciar as tentativas de adição no destino?'):
                return 0
            if dry:
                console.print('[yellow]DRY_RUN ativo: nenhuma adição será enviada.[/yellow]')
            engine = MigrationEngine(
                service.client,
                destination.entity,
                settings.max_invites_per_run,
                settings.min_delay_seconds,
                settings.max_delay_seconds,
            )
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
