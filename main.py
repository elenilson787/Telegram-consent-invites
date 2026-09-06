import asyncio
import sys

from config import Settings
from extractor import save_members
from migrator import MigrationEngine, classify_candidates, select_explicit_targets
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
            console.print('[red]São necessários pelo menos dois grupos/canais acessíveis.[/red]')
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

        console.print('[cyan]Lendo membros da origem...[/cyan]')
        try:
            members = await service.get_members(source.entity)
        except Exception as exc:
            console.print(
                '[red]Não foi possível listar os participantes da origem: '
                f'{type(exc).__name__}: {exc}[/red]'
            )
            return 1

        if not members:
            console.print('[yellow]Nenhum participante acessível foi encontrado.[/yellow]')
            return 0

        json_path, csv_path, records = save_members(members, source.entity)
        console.print(f'[green]✓ Extração salva em:[/green] {json_path}')
        console.print(f'[green]✓ Cópia CSV salva em:[/green] {csv_path}')
        console.print(f'Participantes extraídos: [bold]{len(records)}[/bold]')

        console.print('[cyan]Identificando administradores/owner da origem...[/cyan]')
        try:
            source_admin_ids = await service.get_admin_ids(source.entity)
        except Exception as exc:
            console.print(
                '[red]Não foi possível identificar os administradores da origem com segurança: '
                f'{type(exc).__name__}: {exc}[/red]'
            )
            console.print(
                '[yellow]A extração foi preservada; nenhuma tentativa será feita para evitar incluir admins por engano.[/yellow]'
            )
            return 1

        console.print('[cyan]Verificando membros já presentes no destino...[/cyan]')
        try:
            destination_ids = await service.get_member_ids(destination.entity)
        except Exception as exc:
            console.print(
                '[red]Não foi possível enumerar o destino com segurança: '
                f'{type(exc).__name__}: {exc}[/red]'
            )
            console.print('[yellow]A extração foi preservada; nenhuma tentativa será feita.[/yellow]')
            return 1

        admins, bots, excluded, already_members, eligible = classify_candidates(
            members,
            destination_ids,
            source_admin_ids,
            settings.excluded_user_ids,
        )

        console.print(
            f'Admins/owner ignorados: {len(admins)} | '
            f'Bots ignorados: {len(bots)} | '
            f'Exclusões manuais: {len(excluded)} | '
            f'Já no destino: {len(already_members)} | '
            f'Candidatos para tentativa: {len(eligible)}'
        )

        eligible, missing_targets = select_explicit_targets(
            eligible,
            settings.target_user_ids,
        )
        if missing_targets:
            ids = ', '.join(str(x) for x in sorted(missing_targets))
            console.print(
                '[red]Alvo(s) explícito(s) não estão elegíveis nesta execução: '
                f'{ids}.[/red]'
            )
            console.print(
                '[yellow]Nenhuma tentativa será feita. Confira se o usuário ainda está na origem, '
                'não é admin, não está bloqueado e ainda não está no destino.[/yellow]'
            )
            return 1

        if settings.target_user_ids:
            console.print('[bold cyan]Alvos explícitos desta execução:[/bold cyan]')
            for user in eligible:
                console.print(f'  • {full_name(user)} (ID {user.id})')

        report = ReportWriter()
        try:
            if settings.dry_run:
                console.print(
                    '[bold yellow]DRY_RUN ativo: nenhuma adição será enviada. '
                    f'Serão analisados no máximo {settings.max_invites_per_run} candidatos.[/bold yellow]'
                )
            else:
                if not confirm(
                    'Você administra/tem autorização para adicionar participantes no grupo de destino?'
                ):
                    console.print('[yellow]Extração concluída; nenhuma tentativa de adição foi feita.[/yellow]')
                    return 0

                target_text = ', '.join(
                    f'{full_name(user)} (ID {user.id})' for user in eligible
                )
                if not confirm(f'Confirmar tentativa SOMENTE para: {target_text}?'):
                    console.print('[yellow]Operação cancelada; nenhuma tentativa de adição foi feita.[/yellow]')
                    return 0

            engine = MigrationEngine(
                service.client,
                destination.entity,
                settings.max_invites_per_run,
                settings.min_delay_seconds,
                settings.max_delay_seconds,
            )
            stats = await engine.run(eligible, report, dry_run=settings.dry_run)
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
