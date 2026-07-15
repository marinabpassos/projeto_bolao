# Fase final: disputa de 3º lugar + tela da final com pódio + empate no artilheiro

**Data:** 2026-07-15 · **Status:** aprovado pela usuária

## Objetivo

1. Incluir a **disputa de 3º lugar** (18/07) como jogo de palpite normal, exibida
   **junto com a final** (19/07) numa tela única e caprichada — layout "final
   dourada + pódio" escolhido nos mockups.
2. Permitir **empate no artilheiro da Copa**: mais de um jogador como gabarito,
   todos que apostaram em qualquer um deles levam a faixa congelada cheia.

Urgência: as semis terminam em 15/07; o deploy + importação em produção precisam
acontecer **antes de 18/07** para o pessoal palpitar no 3º lugar.

## Decisões tomadas

| Decisão | Escolha |
|---|---|
| Modelagem do 3º lugar | Nova fase `terceiro` (não reusar `final` com bracket_pos=2) |
| Pontuação do 3º lugar | Igual ao mata-mata: 10/7/5 + bônus +5 no empate |
| Layout da tela | C — final dourada em destaque + card 🥉 + pódio 1º–4º no rodapé |
| Empate no artilheiro | `Settlement.top_scorer` continua string; nomes separados por vírgula; pontos cheios para todos |
| "Até onde o Brasil vai" | Sem mudança — aposta já fechada; "eliminado na semi" segue válido |

## Parte 1 — dados, fases e pontuação

1. `app/phases.py`: `MATCH_STAGES = ["grupos", "16avos", "oitavas", "quartas",
   "semi", "terceiro", "final"]` (a ordem alimenta agrupamento e fase corrente).
2. `ARTILHEIRO_TIERS["terceiro"] = 10` — mesma faixa da final; evita KeyError em
   `current_artilheiro_phase` quando o próximo jogo for o 3º lugar. A tabela de
   regras ganha a linha automaticamente.
3. `app/templating.py`: `STAGE_LABELS["terceiro"] = "Disputa de 3º lugar"`.
4. `PHASES_PROGRESS` e a aposta de progresso do Brasil: **inalterados**.
5. `app/data/fixtures.json`: novo placeholder
   `{"stage": "terceiro", "round": null, "home_team": "A definir",
   "away_team": "A definir", "teams_decided": false, "is_brazil": false,
   "kickoff_at": "2026-07-18T18:00:00+00:00", "bracket_pos": null}`.
   O horário exato vem da API ao preencher os times (comportamento já existente
   de `sync_fixtures_from_api`).
6. `app/services.py`: `_STAGE_MAP_API` ganha `"THIRD_PLACE": "terceiro"` — a
   sincronização existente preenche times (perdedores das semis) e placar sem
   código novo.
7. Pontuação: nenhuma mudança de regra — `stage != "grupos"` já cai em
   `score_knockout_match`. No 3º lugar, `who_advanced` significa "quem ficou com
   o 3º" (muda só rótulo de UI).
8. **Sem migração de banco.** O jogo novo entra por **Admin → Importar faltando**.

### Empate no artilheiro

9. `app/scoring.py` — `artilheiro_points`: split do gabarito por vírgula,
   normalização (`strip` + `casefold`) e comparação do palpite contra **cada**
   nome; qualquer acerto vale `tier_points_at_edit` cheio. Gabarito com um nome
   só continua funcionando exatamente como hoje.
10. `admin.html`: placeholder/dica no campo do artilheiro — "empatou? separe os
    nomes por vírgula".
11. `regras.html`: uma linha documentando a regra do empate.

## Parte 2 — tela da final (layout C) e pódio

**Navegação (`app/bracket.py`):**

12. `jogos_view`: a fase `terceiro` faz parte da visão `final` — quando
    `current_stage` retornar "terceiro" (semis encerradas), a visão selecionada é
    "final" com os dois jogos; `/?fase=terceiro` leva à mesma visão. "Terceiro"
    não vira aba própria.
13. `past_stages` exclui `terceiro` quando a visão é a final.
14. Nova função pura `podium(matches)`: deriva `{1: time, 2: time, 3: time,
    4: time}` (ou `None` por posição) a partir de `who_advanced` da final e do
    3º lugar.

**Template (`app/templates/_bracket.html`; regenerar `templates_data.py` com
`scripts/build_assets.py`):**

15. Visão `final`: card-herói **dourado** da final (gradiente âmbar suave,
    bandeiras grandes, selo "🏆 Grande final"), abaixo o card do 3º lugar com
    selo "🥉 Disputa de 3º lugar" — ambos abrem o card-acordeão de palpite
    existente. No rodapé, **pódio 1º–4º** (ouro/prata/bronze/cinza) que começa
    com "?" e ganha bandeira + nome conforme os jogos encerram. HTML/CSS puro.
16. Mini-chave do topo: inalterada, exceto o 🏆 central virar link
    `/?fase=final`.
17. Rótulos condicionais para `m.stage == 'terceiro'`: pergunta do empate vira
    "quem fica com o 3º lugar? +5 pts"; resultado vira "→ X ficou em 3º"; no
    Admin, o rótulo "Quem avançou:" vira "Quem ficou com o 3º:".

**Erros e casos-limite:**

18. Banco sem o jogo de terceiro: a visão da final renderiza só com a final.
19. Sem JS: cards visíveis (degradação atual mantida); pódio não depende de JS.
20. `build_bracket` ignora `terceiro` (fora de `SLOTS`) — `bracket_pos: null`
    não ativa o fallback de lista.

## Testes (pytest, funções puras)

21. `artilheiro_points`: um nome (compatibilidade), lista com vírgula, espaços,
    caixa alta/baixa, palpite fora da lista → 0, gabarito vazio → 0.
22. `podium`: nada encerrado; só 3º lugar; só final; ambos.
23. `jogos_view`/`current_stage`: pós-semis a visão é "final" com os dois jogos;
    `terceiro` fora de `past_stages`; todas as `MATCH_STAGES` têm faixa em
    `ARTILHEIRO_TIERS`.

## Checklist de produção (pós-merge)

1. `vercel --prod` a partir da `main`.
2. **Admin → Importar faltando** (cria o jogo de 3º lugar).
3. **Admin → Sincronizar da API** (preenche os perdedores das semis e o horário).
4. Conferir a tela `/?fase=final` logada.
