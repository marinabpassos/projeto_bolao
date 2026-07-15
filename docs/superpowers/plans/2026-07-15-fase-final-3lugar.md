# Fase Final (3º lugar + pódio) e Empate no Artilheiro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incluir a disputa de 3º lugar como jogo de palpite normal exibido junto com a final (layout "final dourada + pódio") e permitir empate no gabarito do artilheiro.

**Architecture:** Nova fase `terceiro` nas constantes puras (`phases.py`), placeholder em `fixtures.json`, mapeamento `THIRD_PLACE` na sync da football-data.org, visão da final estendida em `bracket.py` (funções puras + nova `podium()`), e template `_bracket.html` com card dourado da final, card 🥉 e pódio. Artilheiro: gabarito aceita nomes separados por vírgula em `scoring.py`.

**Tech Stack:** Python 3.11 · FastAPI · Jinja2 (templates embutidos) · SQLAlchemy · pytest

**Spec:** `docs/superpowers/specs/2026-07-15-fase-final-design.md`

## Global Constraints

- Branch de trabalho: `feat/fase-final-3lugar` (já criada, contém o spec).
- Todo texto de UI em português brasileiro.
- Templates e dados são **embutidos**: após editar `app/templates/*.html` ou `app/data/*.json`, rodar `python scripts/build_assets.py` e commitar também `app/templates_data.py` / `app/seed_data.py`.
- Sem migração de banco: `matches.stage` é string livre.
- `PHASES_PROGRESS` (até onde o Brasil vai) **não muda**.
- Pontuação do 3º lugar = mata-mata normal (10/7/5 + bônus +5); nenhum valor novo.
- Rodar testes com `python -m pytest` a partir da raiz do repo.

---

### Task 1: Fase `terceiro` nas constantes (phases + labels)

**Files:**
- Modify: `app/phases.py:9` (MATCH_STAGES) e `app/phases.py:13-20` (ARTILHEIRO_TIERS)
- Modify: `app/templating.py:49-56` (STAGE_LABELS)
- Test: `tests/test_scoring.py` (classe `TestTierForPhase`)

**Interfaces:**
- Consumes: nada (constantes puras).
- Produces: `MATCH_STAGES` contendo `"terceiro"` entre `"semi"` e `"final"`; `ARTILHEIRO_TIERS["terceiro"] == 10`; `STAGE_LABELS["terceiro"] == "Disputa de 3º lugar"`. Tasks 3-6 dependem desses três valores.

- [ ] **Step 1: Write the failing tests**

Em `tests/test_scoring.py`, dentro da classe `TestTierForPhase`, adicionar:

```python
    def test_faixa_do_terceiro_lugar_igual_a_final(self):
        assert tier_for_phase("terceiro") == 10

    def test_toda_fase_de_jogo_tem_faixa(self):
        from app.phases import ARTILHEIRO_TIERS, MATCH_STAGES

        assert set(MATCH_STAGES) == set(ARTILHEIRO_TIERS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring.py::TestTierForPhase -v`
Expected: FAIL — `KeyError: 'terceiro'` e diferença de conjuntos.

- [ ] **Step 3: Implement**

Em `app/phases.py`, trocar:

```python
MATCH_STAGES = ["grupos", "16avos", "oitavas", "quartas", "semi", "final"]
```

por:

```python
MATCH_STAGES = ["grupos", "16avos", "oitavas", "quartas", "semi", "terceiro", "final"]
```

e trocar o dicionário de faixas por:

```python
ARTILHEIRO_TIERS = {
    "grupos": 60,
    "16avos": 50,
    "oitavas": 40,
    "quartas": 30,
    "semi": 20,
    "terceiro": 10,  # mesma faixa da final: a essa altura restam só 2 jogos
    "final": 10,
}
```

Em `app/templating.py`, trocar o `STAGE_LABELS` por:

```python
STAGE_LABELS = {
    "grupos": "Fase de grupos",
    "16avos": "16-avos de final",
    "oitavas": "Oitavas de final",
    "quartas": "Quartas de final",
    "semi": "Semifinal",
    "terceiro": "Disputa de 3º lugar",
    "final": "Final",
}
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest`
Expected: PASS (nenhum teste existente depende do tamanho de MATCH_STAGES).

- [ ] **Step 5: Commit**

```bash
git add app/phases.py app/templating.py tests/test_scoring.py
git commit -m "feat: fase 'terceiro' nas constantes de fases e faixas"
```

---

### Task 2: Empate no artilheiro (gabarito com vírgula)

**Files:**
- Modify: `app/scoring.py:69-73` (`artilheiro_points`)
- Test: `tests/test_scoring.py` (classe `TestArtilheiroPoints`)

**Interfaces:**
- Consumes: `_norm(name) -> str` já existente em `app/scoring.py:65`.
- Produces: `artilheiro_points(player_guess, tier_points_at_edit: int, top_scorer) -> int` com a MESMA assinatura de hoje — `top_scorer` passa a aceitar nomes separados por vírgula. `recompute_specials` em `services.py` não muda.

- [ ] **Step 1: Write the failing tests**

Em `tests/test_scoring.py`, dentro da classe `TestArtilheiroPoints`, adicionar:

```python
    def test_gabarito_com_empate_todos_levam_pontos_cheios(self):
        assert artilheiro_points("Mbappé", 60, "Mbappé, Haaland") == 60
        assert artilheiro_points("Haaland", 40, "Mbappé, Haaland") == 40

    def test_gabarito_com_empate_ignora_caixa_e_espacos(self):
        assert artilheiro_points(" haaland ", 30, " Mbappé ,HAALAND ") == 30

    def test_fora_da_lista_empatada_recebe_zero(self):
        assert artilheiro_points("Messi", 60, "Mbappé, Haaland") == 0

    def test_gabarito_so_com_virgulas_recebe_zero(self):
        assert artilheiro_points("Mbappé", 60, ", ,") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring.py::TestArtilheiroPoints -v`
Expected: os 4 novos FAIL (comparação de string única); os 4 antigos PASS.

- [ ] **Step 3: Implement**

Em `app/scoring.py`, substituir a função `artilheiro_points` inteira por:

```python
def artilheiro_points(player_guess, tier_points_at_edit: int, top_scorer) -> int:
    """Pontos da aposta de artilheiro: a faixa congelada se acertou, senão 0.

    O gabarito aceita mais de um nome separado por vírgula (artilharia
    empatada); acertar qualquer um deles vale a faixa cheia.
    """
    guess = _norm(player_guess)
    scorers = {_norm(n) for n in (top_scorer or "").split(",") if _norm(n)}
    if not guess or not scorers:
        return 0
    return tier_points_at_edit if guess in scorers else 0
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/scoring.py tests/test_scoring.py
git commit -m "feat: gabarito do artilheiro aceita empate (nomes por vírgula)"
```

---

### Task 3: Placeholder do 3º lugar + mapa da API + docs

**Files:**
- Modify: `app/data/fixtures.json` (novo jogo antes da final)
- Modify: `app/services.py:271-278` (`_STAGE_MAP_API`)
- Modify: `README.md:101` (lista de stages no formato do fixture)
- Generated: `app/seed_data.py` e `app/templates_data.py` (via `python scripts/build_assets.py`)
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: `MATCH_STAGES` com `"terceiro"` (Task 1).
- Produces: fixture `{"stage": "terceiro", ...}` em `FIXTURES` (seed embutido); `_STAGE_MAP_API["THIRD_PLACE"] == "terceiro"`. Com isso `seed_missing_matches`, `sync_fixtures_from_api` e `sync_results_from_api` passam a cobrir o 3º lugar **sem mudança de código**.

- [ ] **Step 1: Write the failing tests**

Adicionar ao final de `tests/test_fixtures.py`:

```python
def test_terceiro_lugar_presente_e_fora_da_chave():
    terceiros = [f for f in FIXTURES if f["stage"] == "terceiro"]
    assert len(terceiros) == 1
    assert terceiros[0]["teams_decided"] is False
    assert terceiros[0]["bracket_pos"] is None


def test_stage_map_da_api_cobre_o_terceiro_lugar():
    from app.phases import MATCH_STAGES
    from app.services import _STAGE_MAP_API

    assert _STAGE_MAP_API["THIRD_PLACE"] == "terceiro"
    assert set(_STAGE_MAP_API.values()) <= set(MATCH_STAGES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fixtures.py -v`
Expected: os 2 novos FAIL; os 3 antigos PASS (terceiro não entra em `BRACKET_SLOTS`).

- [ ] **Step 3: Implement**

Em `app/data/fixtures.json`, inserir **antes** do objeto da final (mantém ordem cronológica):

```json
{
  "stage": "terceiro",
  "round": null,
  "home_team": "A definir",
  "away_team": "A definir",
  "teams_decided": false,
  "is_brazil": false,
  "kickoff_at": "2026-07-18T18:00:00+00:00",
  "bracket_pos": null
},
```

(O horário exato vem da API quando `sync_fixtures_from_api` preencher os times — comportamento já existente.)

Em `app/services.py`, trocar o `_STAGE_MAP_API` por:

```python
_STAGE_MAP_API = {
    "GROUP_STAGE": "grupos",
    "LAST_32": "16avos",
    "LAST_16": "oitavas",
    "QUARTER_FINALS": "quartas",
    "SEMI_FINALS": "semi",
    "THIRD_PLACE": "terceiro",
    "FINAL": "final",
}
```

No `README.md`, na doc do formato do fixture, trocar o comentário:

```
"stage": "grupos",          // grupos|16avos|oitavas|quartas|semi|terceiro|final
```

- [ ] **Step 4: Regenerate embedded assets**

Run: `python scripts/build_assets.py`
Expected: `OK templates_data.py (...)` e `OK seed_data.py (... 56 jogos)` — 55 antes + 1 novo.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/data/fixtures.json app/services.py app/seed_data.py app/templates_data.py README.md tests/test_fixtures.py
git commit -m "feat: placeholder do 3º lugar e mapeamento THIRD_PLACE na sync"
```

---

### Task 4: Visão da final em `bracket.py` (+ `podium()`)

**Files:**
- Modify: `app/bracket.py:78-115` (`jogos_view`) e nova função `podium`
- Test: `tests/test_bracket.py` (novos testes + **atualizar** `test_jogos_view_na_final_sem_lados`)

**Interfaces:**
- Consumes: `MATCH_STAGES` com `"terceiro"` (Task 1); `current_stage`/`build_bracket` existentes (sem mudança — `terceiro` não está em `SLOTS`, então não afeta a árvore).
- Produces:
  - `podium(matches) -> dict[int, str | None]` — chaves 1..4, valores = nome da seleção ou `None`.
  - `jogos_view(...)` ganha as chaves `"final_match": Match | None`, `"terceiro_match": Match | None`, `"podium": dict | None` (preenchidas só na visão final); `selected_stage` nunca é `"terceiro"` (normaliza para `"final"`); na visão final `pairs_a`/`pairs_b` ficam vazios (o template da Task 5 usa as chaves novas).

- [ ] **Step 1: Write the failing tests**

Em `tests/test_bracket.py`: importar `podium` no bloco de imports do topo:

```python
from app.bracket import (
    build_bracket,
    current_stage,
    jogos_view,
    next_slot,
    podium,
    side_of,
    slot_label,
)
```

Adicionar helper após `_chave_completa`:

```python
def _finished(stage, home, away, hs, as_, adv=None, pos=None):
    m = _m(stage, pos, finished=True, home=home, away=away)
    m.home_score, m.away_score, m.who_advanced = hs, as_, adv
    return m
```

**Substituir** o teste `test_jogos_view_na_final_sem_lados` por:

```python
def test_jogos_view_na_final_mostra_final_e_terceiro():
    ms = _chave_completa(oitavas_finished=True)
    for m in ms:
        if m.stage != "final":
            m.finished = True
        m.teams_decided = True
    ms.append(_m("terceiro"))
    view = jogos_view(ms, None)
    assert view["selected_stage"] == "final"
    assert view["view_mode"] == "bracket"
    assert view["pairs_a"] == [] and view["pairs_b"] == []
    assert view["final_match"] is not None
    assert view["terceiro_match"].stage == "terceiro"
    assert view["podium"] == {1: None, 2: None, 3: None, 4: None}
    assert "terceiro" not in view["past_stages"]
```

Adicionar ao final do arquivo:

```python
def test_jogos_view_fase_terceiro_cai_na_visao_final():
    ms = _chave_completa() + [_m("terceiro")]
    view = jogos_view(ms, "terceiro")
    assert view["selected_stage"] == "final"


def test_jogos_view_sem_jogo_de_terceiro_nao_quebra():
    view = jogos_view(_chave_completa(), "final")
    assert view["terceiro_match"] is None
    assert view["final_match"] is not None


# ---- podium ------------------------------------------------------------------
def test_podium_vazio_sem_jogos_encerrados():
    ms = [_m("final", 1, decided=False), _m("terceiro", decided=False)]
    assert podium(ms) == {1: None, 2: None, 3: None, 4: None}


def test_podium_so_terceiro_encerrado():
    ms = [_m("final", 1), _finished("terceiro", "Brasil", "Inglaterra", 1, 1, adv="home")]
    assert podium(ms) == {1: None, 2: None, 3: "Brasil", 4: "Inglaterra"}


def test_podium_completo_sem_who_advanced_usa_placar():
    ms = [
        _finished("final", "França", "Argentina", 0, 2, pos=1),
        _finished("terceiro", "Brasil", "Inglaterra", 3, 1),
    ]
    assert podium(ms) == {1: "Argentina", 2: "França", 3: "Brasil", 4: "Inglaterra"}


def test_podium_empate_sem_who_advanced_fica_indefinido():
    ms = [_finished("final", "França", "Argentina", 1, 1, pos=1)]
    assert podium(ms) == {1: None, 2: None, 3: None, 4: None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bracket.py -v`
Expected: FAIL — `ImportError: cannot import name 'podium'`.

- [ ] **Step 3: Implement**

Em `app/bracket.py`, adicionar após `current_stage`:

```python
def podium(matches) -> dict[int, str | None]:
    """{1..4: seleção} a partir da final e do 3º lugar (None = ainda indefinido).

    Usa who_advanced; sem ele (resultado manual), deriva do placar se não houve
    empate nos 90 minutos.
    """

    def winner_loser(m):
        if m is None or not m.finished:
            return None, None
        adv = m.who_advanced
        if (
            adv not in ("home", "away")
            and m.home_score is not None
            and m.away_score is not None
            and m.home_score != m.away_score
        ):
            adv = "home" if m.home_score > m.away_score else "away"
        if adv == "home":
            return m.home_team, m.away_team
        if adv == "away":
            return m.away_team, m.home_team
        return None, None

    final = next((m for m in matches if m.stage == "final"), None)
    terceiro = next((m for m in matches if m.stage == "terceiro"), None)
    p1, p2 = winner_loser(final)
    p3, p4 = winner_loser(terceiro)
    return {1: p1, 2: p2, 3: p3, 4: p4}
```

Substituir `jogos_view` inteira por:

```python
def jogos_view(matches, fase_param: str | None) -> dict:
    """Contexto de exibição da página de jogos (modo lista ou bracket)."""
    atual = current_stage(matches)
    sel = fase_param if fase_param in MATCH_STAGES else atual
    if sel == "terceiro":
        sel = "final"  # o 3º lugar é exibido dentro da visão da final
    view = {
        "selected_stage": sel,
        "view_mode": "list",
        "bracket": None,
        "pairs_a": [],
        "pairs_b": [],
        "future_rows": [],
        "past_stages": [],
        "final_match": None,
        "terceiro_match": None,
        "podium": None,
    }
    if sel not in BRACKET_STAGES:
        return view
    bracket = build_bracket(matches)
    if bracket is None:
        return view

    view["view_mode"] = "bracket"
    view["bracket"] = bracket
    view["past_stages"] = [
        s
        for s in MATCH_STAGES[: MATCH_STAGES.index(sel)]
        if s != "terceiro" and any(m.stage == s for m in matches)
    ]
    if sel == "final":
        view["final_match"] = bracket["final"][1]
        view["terceiro_match"] = next((m for m in matches if m.stage == "terceiro"), None)
        view["podium"] = podium(matches)
    else:
        view["pairs_a"] = _pairs(bracket, sel, "A")
        view["pairs_b"] = _pairs(bracket, sel, "B")

    # Fases além da seguinte, como linhas compactas (SF1 · A definir — 14/07).
    i = BRACKET_STAGES.index(sel)
    for stage in BRACKET_STAGES[i + 2 :]:
        for pos in range(1, SLOTS[stage] + 1):
            view["future_rows"].append(
                {"label": slot_label(stage, pos), "match": bracket[stage][pos]}
            )
    return view
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest`
Expected: PASS (inclusive os testes antigos de `jogos_view` das oitavas).

- [ ] **Step 5: Commit**

```bash
git add app/bracket.py tests/test_bracket.py
git commit -m "feat: visão da final com jogo de 3º lugar e derivação do pódio"
```

---

### Task 5: Template da tela da final (hero dourada + 🥉 + pódio)

**Files:**
- Modify: `app/templates/_bracket.html`
- Generated: `app/templates_data.py` (via `python scripts/build_assets.py`)

**Interfaces:**
- Consumes: `view.final_match`, `view.terceiro_match`, `view.podium` (Task 4); macros `cards.match_card`, `flag_url`, `dt_br`, `stage_labels`, `my_preds`, `my_br`, `is_open`, `saved` — todos já no contexto da página.
- Produces: visão `selected_stage == 'final'` renderizada com os dois jogos + pódio. Sem contrato para tasks seguintes.

- [ ] **Step 1: Substituir a renderização da visão final**

Em `app/templates/_bracket.html`, trocar as duas linhas:

```jinja
{{ arvore(view.pairs_a, 'a') }}
{% if view.pairs_b %}{{ arvore(view.pairs_b, 'b') }}{% endif %}
```

por:

```jinja
{% macro jogo_final(m, titulo, dourado) %}
{% set box = 'bg-gradient-to-br from-amber-50 via-white to-amber-50/60 border-amber-300 hover:border-amber-400' if dourado else 'bg-white border-slate-200 hover:border-slate-400' %}
{% if m and m.teams_decided %}
<div class="mb-3">
  <button type="button" onclick="document.getElementById('card-{{ m.id }}').classList.toggle('hidden')"
          class="w-full text-left rounded-2xl border-2 {{ box }} px-4 {{ 'py-4' if dourado else 'py-3' }} shadow-sm transition">
    <p class="text-[10px] font-semibold uppercase tracking-wider {{ 'text-amber-600' if dourado else 'text-amber-800' }} mb-2 text-center">{{ titulo }} · {{ m.kickoff_at | dt_br }}</p>
    <div class="flex items-center justify-center gap-3 {{ 'text-lg' if dourado else 'text-base' }} font-semibold text-slate-900">
      <span class="flex-1 text-right truncate">{% if m.is_brazil and m.home_team == 'Brasil' %}<span class="text-brand-yellow">★</span> {% endif %}{{ m.home_team }}</span>
      {% set url = flag_url(m.home_team) %}
      {% if url %}<img src="{{ url }}" alt="" loading="lazy" class="{{ 'w-9' if dourado else 'w-7' }} h-auto rounded shadow">{% else %}<span class="{{ 'w-9 h-6' if dourado else 'w-7 h-5' }} bg-slate-200 rounded inline-block"></span>{% endif %}
      {% if m.finished %}
        <span class="px-2.5 py-1 rounded-md bg-slate-900 text-white text-sm tabular-nums">{{ m.home_score }} : {{ m.away_score }}</span>
      {% else %}
        <span class="text-slate-300 text-sm">vs</span>
      {% endif %}
      {% set url = flag_url(m.away_team) %}
      {% if url %}<img src="{{ url }}" alt="" loading="lazy" class="{{ 'w-9' if dourado else 'w-7' }} h-auto rounded shadow">{% else %}<span class="{{ 'w-9 h-6' if dourado else 'w-7 h-5' }} bg-slate-200 rounded inline-block"></span>{% endif %}
      <span class="flex-1 text-left truncate">{{ m.away_team }}{% if m.is_brazil and m.away_team == 'Brasil' %} <span class="text-brand-yellow">★</span>{% endif %}</span>
    </div>
    <p class="text-[11px] mt-2 text-center {{ 'text-brand-green' if my_preds.get(m.id) else 'text-slate-400' }}">
      {% if m.finished and m.who_advanced %}→ {{ m.home_team if m.who_advanced == 'home' else m.away_team }} {{ 'ficou em 3º 🥉' if m.stage == 'terceiro' else 'é campeão! 🏆' }}
      {% elif my_preds.get(m.id) %}✓ seu palpite: {{ my_preds[m.id].home_pred }}:{{ my_preds[m.id].away_pred }} · toque para editar
      {% elif is_open[m.id] %}● aberto · toque para palpitar
      {% else %}fechado{% endif %}
    </p>
  </button>
  <div id="card-{{ m.id }}" class="mt-2 card-palpite{{ ' card-salvo' if saved == m.id|string or saved == 'brasil-' ~ m.id|string }}">
    {{ cards.match_card(m, my_preds.get(m.id), my_br.get(m.id), user, is_open[m.id], saved) }}
  </div>
</div>
{% elif m %}
<div class="mb-3 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-100 px-4 py-4 text-center text-xs text-slate-400">
  {{ titulo }} · ⏳ A definir · {{ m.kickoff_at | dt_br }}
</div>
{% endif %}
{% endmacro %}

{% macro degrau(pos, nome, cor, altura, texto='text-white') %}
<div class="flex flex-col items-center justify-end gap-1 w-16">
  {% if nome %}
    {% set url = flag_url(nome) %}
    {% if url %}<img src="{{ url }}" alt="" loading="lazy" class="w-6 h-auto rounded-[2px] shadow-sm">{% endif %}
    <span class="text-[10px] text-slate-600 font-medium truncate max-w-full">{{ nome }}</span>
  {% else %}
    <span class="text-slate-300 text-sm">?</span>
  {% endif %}
  <div class="w-full {{ altura }} {{ cor }} rounded-t-md text-center text-[10px] font-bold {{ texto }} pt-0.5">{{ pos }}º</div>
</div>
{% endmacro %}

{% if view.selected_stage == 'final' %}
  {{ jogo_final(view.final_match, '🏆 Grande final', true) }}
  {{ jogo_final(view.terceiro_match, '🥉 Disputa de 3º lugar', false) }}
  {% if view.podium %}
  <div class="bg-white rounded-xl border border-slate-200 p-4 mt-4">
    <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 text-center mb-3">Pódio da Copa 2026</p>
    <div class="flex items-end justify-center gap-2">
      {{ degrau(2, view.podium[2], 'bg-slate-400', 'h-14') }}
      {{ degrau(1, view.podium[1], 'bg-amber-400', 'h-20') }}
      {{ degrau(3, view.podium[3], 'bg-amber-700', 'h-10') }}
      {{ degrau(4, view.podium[4], 'bg-slate-200', 'h-6', 'text-slate-500') }}
    </div>
  </div>
  {% endif %}
{% else %}
  {{ arvore(view.pairs_a, 'a') }}
  {% if view.pairs_b %}{{ arvore(view.pairs_b, 'b') }}{% endif %}
{% endif %}
```

- [ ] **Step 2: Linkar o 🏆 da mini-chave**

Ainda em `_bracket.html`, na mini-chave, trocar:

```jinja
    <div class="flex flex-col items-center flex-1">
      <span class="text-sm">🏆</span><span class="text-[7px] text-slate-400">FINAL</span>
    </div>
```

por:

```jinja
    <a href="/?fase=final" class="flex flex-col items-center flex-1">
      <span class="text-sm">🏆</span><span class="text-[7px] text-slate-400">FINAL</span>
    </a>
```

- [ ] **Step 3: Regenerate embedded templates**

Run: `python scripts/build_assets.py`
Expected: `OK templates_data.py (...)`.

- [ ] **Step 4: Run the full suite + render smoke**

Run: `python -m pytest`
Expected: PASS.

Smoke de sintaxe Jinja (pega erro de template sem subir servidor):

Run: `python -c "from app.templating import templates; templates.env.get_template('_bracket.html'); print('jinja OK')"`
Expected: `jinja OK`.

- [ ] **Step 5: Commit**

```bash
git add app/templates/_bracket.html app/templates_data.py
git commit -m "feat: tela da final com card dourado, 3º lugar e pódio"
```

---

### Task 6: Rótulos do 3º lugar, regras e dica de vírgula no admin

**Files:**
- Modify: `app/templates/_match_card.html` (pergunta/resumo do qualificador)
- Modify: `app/templates/admin.html` (rótulo "Quem avançou" + placeholder do artilheiro)
- Modify: `app/templates/regras.html` (linha do 3º lugar + regra do empate)
- Generated: `app/templates_data.py` (via `python scripts/build_assets.py`)

**Interfaces:**
- Consumes: fase `"terceiro"` (Task 1) e comportamento de vírgula no gabarito (Task 2).
- Produces: só texto de UI; sem contrato para outras tasks.

- [ ] **Step 1: `_match_card.html` — textos do qualificador**

Trocar a linha da pergunta:

```jinja
          <p class="text-xs text-slate-400 mb-1.5 text-center">Em caso de empate, quem avança? <span class="font-medium text-brand-green">+5 pts</span></p>
```

por:

```jinja
          <p class="text-xs text-slate-400 mb-1.5 text-center">Em caso de empate, {{ 'quem fica com o 3º lugar?' if m.stage == 'terceiro' else 'quem avança?' }} <span class="font-medium text-brand-green">+5 pts</span></p>
```

Trocar, no resumo do palpite salvo (formulário aberto):

```jinja
      <p class="text-center text-xs text-brand-green mt-2 mb-0.5">✓ Palpite salvo: <b>{{ pred.home_pred }} : {{ pred.away_pred }}</b>{% if m.stage != 'grupos' and pred and pred.qualifier_pred %} · avança: <b>{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>{% endif %} — editável até o apito</p>
```

por:

```jinja
      <p class="text-center text-xs text-brand-green mt-2 mb-0.5">✓ Palpite salvo: <b>{{ pred.home_pred }} : {{ pred.away_pred }}</b>{% if m.stage != 'grupos' and pred and pred.qualifier_pred %} · {{ 'leva o 3º' if m.stage == 'terceiro' else 'avança' }}: <b>{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>{% endif %} — editável até o apito</p>
```

E no resumo do palpite fechado:

```jinja
        Seu palpite: <b class="text-slate-700">{{ pred.home_pred }} : {{ pred.away_pred }}</b>{% if m.stage != 'grupos' and pred.qualifier_pred %} · avança: <b class="text-slate-700">{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>{% endif %}
```

por:

```jinja
        Seu palpite: <b class="text-slate-700">{{ pred.home_pred }} : {{ pred.away_pred }}</b>{% if m.stage != 'grupos' and pred.qualifier_pred %} · {{ 'leva o 3º' if m.stage == 'terceiro' else 'avança' }}: <b class="text-slate-700">{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>{% endif %}
```

- [ ] **Step 2: `admin.html` — rótulo e placeholder**

Trocar:

```jinja
        <span class="text-xs text-slate-400">Quem avançou:</span>
```

por:

```jinja
        <span class="text-xs text-slate-400">{{ 'Quem ficou com o 3º:' if m.stage == 'terceiro' else 'Quem avançou:' }}</span>
```

Trocar o placeholder do artilheiro:

```jinja
               class="border border-slate-300 rounded-md py-1.5 px-2 w-full mt-1 outline-none focus:border-brand-green" placeholder="Nome do artilheiro">
```

por:

```jinja
               class="border border-slate-300 rounded-md py-1.5 px-2 w-full mt-1 outline-none focus:border-brand-green" placeholder="Nome do artilheiro (empate? separe por vírgula)">
```

- [ ] **Step 3: `regras.html` — documentar as duas regras**

Na seção "Palpites dos jogos", após a linha `<li>Jogos do <b>mata-mata</b> abrem...`, adicionar:

```jinja
      <li>A <b>disputa de 3º lugar</b> conta como jogo normal do mata-mata.</li>
```

Na seção "Artilheiro da Copa", trocar o parágrafo:

```jinja
    <p class="text-sm text-slate-600 mb-2">
      Escolha o artilheiro e troque quando quiser — a pontuação fica
      <b>congelada conforme a fase do seu último palpite</b>. Quanto mais cedo, mais vale:
    </p>
```

por:

```jinja
    <p class="text-sm text-slate-600 mb-2">
      Escolha o artilheiro e troque quando quiser — a pontuação fica
      <b>congelada conforme a fase do seu último palpite</b>. Se dois ou mais
      jogadores empatarem na artilharia, acertar qualquer um deles vale a
      pontuação cheia. Quanto mais cedo, mais vale:
    </p>
```

- [ ] **Step 4: Regenerate + full suite + smoke Jinja**

Run: `python scripts/build_assets.py && python -m pytest`
Expected: `OK templates_data.py` e PASS.

Run: `python -c "from app.templating import templates; [templates.env.get_template(t) for t in ('_match_card.html','admin.html','regras.html')]; print('jinja OK')"`
Expected: `jinja OK`.

- [ ] **Step 5: Commit**

```bash
git add app/templates/_match_card.html app/templates/admin.html app/templates/regras.html app/templates_data.py
git commit -m "feat: rótulos do 3º lugar, regra do empate no artilheiro e dica no admin"
```

---

### Task 7: Verificação end-to-end local

**Files:** nenhum novo (verificação).

**Interfaces:**
- Consumes: tudo das tasks 1-6.
- Produces: confirmação visual/funcional antes do merge.

- [ ] **Step 1: Suite completa**

Run: `python -m pytest -v`
Expected: PASS em todos.

- [ ] **Step 2: Conferir que os assets embutidos não têm drift**

Run: `python scripts/build_assets.py && git status --short`
Expected: nenhuma mudança pendente em `app/templates_data.py` / `app/seed_data.py`.

- [ ] **Step 3: Subir local e verificar a tela**

Com o `.env` local apontando para um banco de teste (NUNCA o de produção/Neon):

```bash
uvicorn app.main:app --reload
```

Roteiro de verificação em `http://localhost:8000`:
1. Admin → Importar tabela (banco vazio) — deve criar 56 jogos, incluindo "Disputa de 3º lugar · 18/07".
2. No Admin, definir times das duas semis, lançar resultados (com "quem avançou"); definir times do 3º lugar e da final manualmente.
3. Abrir `/?fase=final`: card dourado da final no topo, card 🥉 abaixo, ambos abrindo o acordeão de palpite; pódio com "?" nas 4 posições.
4. Palpitar no 3º lugar com empate: a pergunta deve ser "quem fica com o 3º lugar? +5 pts".
5. Lançar resultado do 3º lugar no Admin (rótulo "Quem ficou com o 3º:") → pódio mostra 3º/4º.
6. Lançar resultado da final → pódio completo, status "→ X é campeão! 🏆".
7. Gabarito do artilheiro com `"Nome A, Nome B"` → quem apostou em qualquer um pontua (ver ranking).
8. `/?fase=terceiro` na URL → mesma tela da final.
9. `/regras`: linha do 3º lugar, regra do empate e faixa "Disputa de 3º lugar — 10 pts" na tabela.

- [ ] **Step 4: Commit final (se a verificação gerou ajustes)**

```bash
git status --short   # commitar qualquer ajuste com mensagem descritiva
```

---

## Pós-merge (produção) — do spec, não automatizável daqui

1. Merge do PR na `main` e `vercel --prod`.
2. **Admin → Importar faltando** (cria o jogo de 3º lugar no banco Neon).
3. **Admin → Sincronizar da API** (preenche perdedores das semis + horário real).
4. Conferir `/?fase=final` em produção **antes de 18/07**.
