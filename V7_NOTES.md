# V7 — sincronização pós-rodada

A V7 mantém toda a lógica de convite da V6 e corrige apenas o estado visual após uma rodada real.

Após concluir uma rodada real, a interface consulta novamente os administradores da origem e os membros do destino, combina isso com o histórico local e reconstrói os cards e a fila sem disparar novas tentativas.

Isso garante que usuários adicionados passem a aparecer em `Já no destino`, enquanto tentativas que permanecerem fora do destino mas já tiverem sido processadas apareçam em `Já processados`.
