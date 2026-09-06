import customtkinter as ctk

from local_app import PreparedQueue
from local_app_v6 import LocalAppV6
from migrator import classify_candidates


def rebuild_prepared_queue(prepared, source_admin_ids, destination_ids, excluded_ids, processed_ids):
    """Reconstrói apenas o estado visual da fila após uma rodada.

    Usa os membros já extraídos da origem e o estado atual do destino/histórico,
    sem disparar qualquer convite adicional e sem gerar nova extração em disco.
    """
    admins, bots, excluded, already_members, eligible = classify_candidates(
        prepared.members,
        destination_ids,
        source_admin_ids,
        excluded_ids,
    )
    processed_ids = set(processed_ids)
    queue = [user for user in eligible if user.id not in processed_ids]

    return PreparedQueue(
        source=prepared.source,
        destination=prepared.destination,
        members=prepared.members,
        queue=queue,
        extracted=prepared.extracted,
        admins=len(admins),
        bots=len(bots),
        excluded=len(excluded),
        already_destination=len(already_members),
        previously_processed=len([user for user in eligible if user.id in processed_ids]),
        json_path=prepared.json_path,
        csv_path=prepared.csv_path,
    )


class LocalAppV7(LocalAppV6):
    """V7: sincroniza métricas e fila automaticamente após uma rodada real."""

    def _after_run_v2(self, future):
        try:
            _stats, _report_path, prepared, was_dry_run = future.result()
        except Exception:
            # A V6 mantém o tratamento completo de falha da rodada.
            super()._after_run_v2(future)
            return

        super()._after_run_v2(future)

        if was_dry_run or self.service is None:
            return

        self._set_status('Rodada concluída. Atualizando estado da fila...')
        self._append_log('Sincronizando fila com o estado atual do Telegram após a rodada real.')
        self._submit(
            self._refresh_prepared_after_real_run(prepared),
            self._after_post_run_refresh,
        )

    async def _refresh_prepared_after_real_run(self, prepared):
        source_admin_ids = await self.service.get_admin_ids(prepared.source.entity)
        destination_ids = await self.service.get_member_ids(prepared.destination.entity)
        excluded_ids = set(self.settings.excluded_user_ids) | self.store.excluded_ids()
        processed_ids = self.store.processed_ids(prepared.source.id, prepared.destination.id)

        return rebuild_prepared_queue(
            prepared,
            source_admin_ids,
            destination_ids,
            excluded_ids,
            processed_ids,
        )

    def _after_post_run_refresh(self, future):
        try:
            refreshed = future.result()
        except Exception as exc:
            self._set_status('Rodada concluída. Clique em Analisar fila para atualizar os números.')
            self._append_log(
                f'AVISO: não foi possível atualizar automaticamente a fila: '
                f'{type(exc).__name__}: {exc}'
            )
            return

        self.prepared = refreshed
        self._show_prepared(refreshed)
        self._refresh_primary_button()
        self._set_status(f'Fila atualizada: {len(refreshed.queue)} candidatos disponíveis.')
        self._append_log(
            'Fila sincronizada após rodada real. '
            f'Já no destino={refreshed.already_destination}; '
            f'já processados={refreshed.previously_processed}; '
            f'pendentes={len(refreshed.queue)}.'
        )


if __name__ == '__main__':
    app = LocalAppV7()
    app.mainloop()
