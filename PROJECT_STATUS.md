# Telegram Extractor — Status do projeto

## Status atual

**Desenvolvimento comercial congelado na V19.**

A V19 permanece como versão experimental/legada para testes controlados e referência técnica. O projeto não será comercializado com a proposta principal de extrair participantes e adicioná-los automaticamente a outro grupo, porque a etapa de inclusão direta depende de limites dinâmicos do Telegram (`PEER_FLOOD`/`FLOOD_WAIT`) que não são previsíveis nem adequados para uma promessa comercial estável.

## O que permanece preservado

- autenticação e login do SaaS;
- confirmação de e-mail;
- planos, assinatura e entitlements via Supabase;
- limite de contas por plano;
- sessão Telegram isolada por conta;
- onboarding de contas Telegram;
- análise e extração de participantes acessíveis;
- filtros de admins, bots, duplicados e exclusões;
- histórico e relatórios;
- DRY RUN;
- links de convite;
- mensagens opt-in;
- painel de saúde da conta;
- detecção e tratamento de `PEER_FLOOD`/`FLOOD_WAIT`;
- política de pausa adaptativa por conta.

## Direção recomendada

A infraestrutura comercial reutilizável deve ser reaproveitada em outros produtos, em especial:

1. autenticação e cadastro;
2. confirmação de e-mail;
3. assinatura/planos;
4. entitlements e limites por plano;
5. licenciamento do agente desktop;
6. componentes de UI comercial;
7. integração Supabase;
8. isolamento multi-conta.

## Regra de manutenção

Não investir em novas tentativas de encontrar um "intervalo ideal" ou um "limite diário garantido" para convites diretos do Telegram. Qualquer manutenção futura nesta base deve priorizar correções de segurança, preservação de dados ou reutilização de componentes.

## Última versão experimental

- **V19** — proteção adaptativa contra `PEER_FLOOD`/`FLOOD_WAIT`.

O código deve ser preservado como referência e não apagado.