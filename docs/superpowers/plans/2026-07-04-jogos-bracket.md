# Página de Jogos: fase atual + chaveamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A página `/` abre na fase vigente e mostra o mata-mata (oitavas → final) como árvore vertical com mini-chave, lados A/B, bandeiras e palpite em acordeão — sem perder o histórico em lista.

**Architecture:** Server-rendered (FastAPI + Jinja2 + Tailwind CDN). Nova coluna `matches.bracket_pos` define a estrutura da chave; módulos puros novos (`app/bracket.py`, `app/flags.py`) derivam árvore e bandeiras; um partial `_bracket.html` renderiza o modo chaveamento com JS vanilla mínimo (toggle de lado, acordeão, chip de fases passadas).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Jinja2 (DictLoader), Tailwind via CDN, pytest. **Nenhuma dependência nova.**

**Spec:** `docs/superpowers/specs/2026-07-04-jogos-bracket-design.md`

## Global Constraints

- **Templates e dados são embutidos em Python.** Após editar `app/templates/*.html` ou `app/data/*.json`, SEMPRE rode `python scripts/build_assets.py` e commite os arquivos regenerados (`app/templates_data.py`, `app/seed_data.py`). Nunca edite os gerados à mão.
- Template novo exige entrada em `TEMPLATE_NAMES` em `scripts/build_assets.py:21-28`.
- A rota da página de jogos é `GET /` (`home` em `app/routers/pages.py:31`) — não existe `/jogos`.
- Bandeiras: imagens `https://flagcdn.com/w{20|40}/{code}.png` (emoji não renderiza no Windows). Time sem bandeira → placeholder, nunca quebra.
- Fases: `MATCH_STAGES = ["grupos", "16avos", "oitavas", "quartas", "semi", "final"]` (`app/phases.py:9`). Bracket cobre `oitavas → final`.
- Regra da árvore: vencedores das posições `2k-1` e `2k` de uma fase alimentam a posição `k` da seguinte. Lado A = primeira metade das posições; final não tem lado.
- Sync de resultados (`sync_results_from_api`) e de fixtures nunca sobrescrevem `bracket_pos` não-nulo.
- Sem JS a página degrada: lados empilhados, cards abertos, forms POST normais.
- Commits em português no estilo do repo (`feat:`, `fix:`, `docs:`, `test:`).
- Rode testes com `python -m pytest` a partir da raiz do repo.
- Banco local: SQLite `bolao_local.db` criado por `python scripts/seed.py` (via `Base.metadata.create_all`). Coluna nova exige recriar: apague o arquivo e rode o seed de novo.
- Migração prod (Supabase): rodar `alter table matches add column if not exists bracket_pos int;` no SQL Editor e depois clicar **Admin → Sincronizar fixtures** (o backfill da Task 1 preenche as posições).

---

### Task 1: Coluna `bracket_pos` no modelo, schema e seed/sync

**Files:**
- Modify: `app/models.py:30-46` (classe `Match`)
- Modify: `schema.sql:12-27` (tabela `matches`)
- Modify: `app/services.py` (`seed_matches`, `seed_missing_matches`, `sync_fixtures`)
- Test: `tests/test_services.py`

**Interfaces:**
- Produces: `Match.bracket_pos: int | None`; `sync_fixtures(db)` passa a fazer backfill de `bracket_pos` em jogos existentes (match por `(stage, kickoff_at)`, só quando o valor no banco é `NULL`).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_services.py` (o arquivo já tem o fixture `db` e o padrão de monkeypatch de `load_fixtures`):

```python
# --------------------------------------------------------------------------- #
# bracket_pos                                                                  #
# --------------------------------------------------------------------------- #
BRACKET_FIXTURES = [
    {
        "stage": "oitavas", "round": None, "home_team": "Brasil", "away_team": "Noruega",
        "teams_decided": True, "is_brazil": True,
        "kickoff_at": "2026-07-05T20:00:00+00:00", "bracket_pos": 3,
    },
    {
        "stage": "quartas", "round": None, "home_team": "A definir", "away_team": "A definir",
        "teams_decided": False, "is_brazil": False,
        "kickoff_at": "2026-07-10T19:00:00+00:00", "bracket_pos": 1,
    },
]


def test_seed_missing_matches_carrega_bracket_pos(db, monkeypatch):
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    seed_missing_matches(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 3


def test_sync_fixtures_backfill_bracket_pos_em_jogo_existente(db, monkeypatch):
    # Jogo já no banco SEM bracket_pos (dado antigo), mesmo (stage, kickoff) do fixture.
    db.add(_match("oitavas", "2026-07-05T20:00:00+00:00", "Brasil", "Noruega"))
    db.commit()
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    sync_fixtures(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 3


def test_sync_fixtures_nao_sobrescreve_bracket_pos(db, monkeypatch):
    existing = _match("oitavas", "2026-07-05T20:00:00+00:00", "Brasil", "Noruega")
    existing.bracket_pos = 7  # valor definido manualmente pelo admin
    db.add(existing)
    db.commit()
    monkeypatch.setattr("app.services.load_fixtures", lambda: BRACKET_FIXTURES)
    sync_fixtures(db)
    m = db.scalar(select(Match).where(Match.stage == "oitavas"))
    assert m.bracket_pos == 7
```

Também adicionar `sync_fixtures` ao import no topo do arquivo:

```python
from app.services import seed_missing_matches, sync_fixtures, sync_results_from_api
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_services.py -k bracket_pos -v`
Expected: 3 FAIL — `Match` não tem atributo `bracket_pos` (TypeError/AttributeError).

- [ ] **Step 3: Implementar**

Em `app/models.py`, classe `Match`, depois da linha `who_advanced` (linha 46):

```python
    bracket_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Em `schema.sql`, dentro do `create table if not exists matches (...)`, depois de `who_advanced text ...`:

```sql
    bracket_pos    int                               -- posição na chave (oitavas 1-8, quartas 1-4, semi 1-2, final 1)
```

(vírgula na linha anterior). E ao final do arquivo, comentário de migração:

```sql
-- Migração para bancos já criados (rodar uma vez no SQL Editor do Supabase):
-- alter table matches add column if not exists bracket_pos int;
```

Em `app/services.py`:

1. Nos três construtores `Match(...)` de `seed_matches` (linha ~32), `seed_missing_matches` (linha ~62) e `sync_fixtures` (linha ~236), adicionar:

```python
                bracket_pos=f.get("bracket_pos"),
```

2. Em `sync_fixtures`, trocar o set `existing` por um dict para permitir backfill. Substituir:

```python
    existing: set[tuple] = set()
    for m in db.scalars(select(Match)):
        kt = m.kickoff_at if m.kickoff_at.tzinfo else m.kickoff_at.replace(tzinfo=timezone.utc)
        existing.add((m.stage, kt))
```

por:

```python
    existing: dict[tuple, Match] = {}
    for m in db.scalars(select(Match)):
        kt = m.kickoff_at if m.kickoff_at.tzinfo else m.kickoff_at.replace(tzinfo=timezone.utc)
        existing[(m.stage, kt)] = m
```

(o teste `if (f["stage"], kt) not in existing:` continua funcionando com dict). E antes do `db.commit()` final da função, adicionar o backfill — sobre TODOS os fixtures, inclusive placeholders:

```python
    # Backfill de bracket_pos em jogos já existentes (nunca sobrescreve valor definido).
    for f in fixtures:
        pos = f.get("bracket_pos")
        if pos is None:
            continue
        kt = datetime.fromisoformat(f["kickoff_at"])
        if kt.tzinfo is None:
            kt = kt.replace(tzinfo=timezone.utc)
        m = existing.get((f["stage"], kt))
        if m is not None and m.bracket_pos is None:
            m.bracket_pos = pos
```

- [ ] **Step 4: Rodar e ver passar (novos + regressão)**

Run: `python -m pytest -v`
Expected: todos PASS (incluindo os 3 novos e os testes antigos de `sync_fixtures`/`seed_missing_matches`).

- [ ] **Step 5: Commit**

```bash
git add app/models.py schema.sql app/services.py tests/test_services.py
git commit -m "feat: coluna bracket_pos em matches com backfill no sync de fixtures"
```

---

### Task 2: `bracket_pos` e placeholders completos em `fixtures.json`

**Files:**
- Modify: `app/data/fixtures.json` (oitavas + placeholders de quartas/semi/final)
- Regenerate: `app/seed_data.py` (via script)
- Test: `tests/test_fixtures.py` (novo)

**Interfaces:**
- Produces: `app.seed_data.FIXTURES` com `bracket_pos` em todo jogo de oitavas → final; 4 placeholders de quartas, 2 de semi, 1 de final.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_fixtures.py`:

```python
"""Sanidade dos fixtures embutidos: estrutura da chave oitavas -> final."""

from collections import Counter

from app.seed_data import FIXTURES

BRACKET_SLOTS = {"oitavas": 8, "quartas": 4, "semi": 2, "final": 1}


def _knockout():
    return [f for f in FIXTURES if f["stage"] in BRACKET_SLOTS]


def test_todo_jogo_de_mata_mata_tem_bracket_pos():
    faltando = [f for f in _knockout() if f.get("bracket_pos") is None]
    assert faltando == []


def test_quantidade_de_jogos_por_fase():
    contagem = Counter(f["stage"] for f in _knockout())
    assert contagem == Counter(BRACKET_SLOTS)


def test_posicoes_unicas_e_dentro_da_faixa():
    for stage, slots in BRACKET_SLOTS.items():
        posicoes = sorted(f["bracket_pos"] for f in _knockout() if f["stage"] == stage)
        assert posicoes == list(range(1, slots + 1)), stage
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_fixtures.py -v`
Expected: FAIL — oitavas sem `bracket_pos`, quartas com 1 jogo em vez de 4.

- [ ] **Step 3: Editar `app/data/fixtures.json`**

Nos 8 jogos de `"stage": "oitavas"`, adicionar `"bracket_pos"` na ordem de kickoff (premissa documentada no spec; ajustável depois editando o JSON e clicando Sincronizar fixtures):

| kickoff (UTC) | jogo | bracket_pos |
|---|---|---|
| 2026-07-04T17:00 | Canadá × Marrocos | 1 |
| 2026-07-04T21:00 | Paraguai × França | 2 |
| 2026-07-05T20:00 | Brasil × Noruega | 3 |
| 2026-07-06T00:00 | México × Inglaterra | 4 |
| 2026-07-06T19:00 | Portugal × Espanha | 5 |
| 2026-07-07T00:00 | Estados Unidos × Bélgica | 6 |
| 2026-07-07T16:00 | Argentina × Egito | 7 |
| 2026-07-07T20:00 | Suíça × Colômbia | 8 |

Exemplo (aplicar o mesmo padrão nos 8):

```json
{ "stage": "oitavas", "round": null, "home_team": "Canadá", "away_team": "Marrocos", "teams_decided": true, "is_brazil": false, "kickoff_at": "2026-07-04T17:00:00+00:00", "bracket_pos": 1 },
```

Substituir os 3 placeholders atuais de quartas/semi/final por este bloco (mantém os kickoffs existentes para o dedup por `(stage, kickoff_at)` reconhecer os jogos já no banco):

```json
{ "stage": "quartas", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-10T19:00:00+00:00", "bracket_pos": 1 },
{ "stage": "quartas", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-10T23:00:00+00:00", "bracket_pos": 2 },
{ "stage": "quartas", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-11T19:00:00+00:00", "bracket_pos": 3 },
{ "stage": "quartas", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-11T23:00:00+00:00", "bracket_pos": 4 },
{ "stage": "semi", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-14T19:00:00+00:00", "bracket_pos": 1 },
{ "stage": "semi", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-15T19:00:00+00:00", "bracket_pos": 2 },
{ "stage": "final", "round": null, "home_team": "A definir", "away_team": "A definir", "teams_decided": false, "is_brazil": false, "kickoff_at": "2026-07-19T19:00:00+00:00", "bracket_pos": 1 }
```

- [ ] **Step 4: Regenerar embutidos e rodar testes**

Run: `python scripts/build_assets.py && python -m pytest -v`
Expected: `OK seed_data.py (... 55 jogos)` e todos os testes PASS.

- [ ] **Step 5: Commit**

```bash
git add app/data/fixtures.json app/seed_data.py tests/test_fixtures.py
git commit -m "feat: bracket_pos nos fixtures e placeholders completos do mata-mata"
```

---

### Task 3: Módulo de bandeiras `app/flags.py`

**Files:**
- Create: `app/flags.py`
- Modify: `app/templating.py` (registrar global)
- Test: `tests/test_flags.py` (novo)

**Interfaces:**
- Produces: `flag_url(team: str, width: int = 40) -> str | None` — URL do flagcdn ou `None` para time desconhecido/"A definir". Exposto ao Jinja como global `flag_url`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_flags.py`:

```python
"""Todo time dos fixtures precisa resolver para uma bandeira."""

from app.flags import flag_url
from app.seed_data import FIXTURES


def test_todos_os_times_dos_fixtures_tem_bandeira():
    times = {
        t
        for f in FIXTURES
        for t in (f["home_team"], f["away_team"])
        if t != "A definir"
    }
    sem_bandeira = sorted(t for t in times if flag_url(t) is None)
    assert sem_bandeira == []


def test_url_e_largura():
    assert flag_url("Brasil") == "https://flagcdn.com/w40/br.png"
    assert flag_url("Inglaterra", width=20) == "https://flagcdn.com/w20/gb-eng.png"


def test_desconhecido_e_placeholder_retornam_none():
    assert flag_url("Atlântida") is None
    assert flag_url("A definir") is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_flags.py -v`
Expected: FAIL — `ModuleNotFoundError: app.flags`.

- [ ] **Step 3: Criar `app/flags.py`**

```python
"""Bandeiras das seleções (imagens do flagcdn; emoji não renderiza no Windows)."""

# Nome em PT (como está em matches.home_team/away_team) -> código ISO do flagcdn.
FLAGS = {
    "África do Sul": "za",
    "Alemanha": "de",
    "Arábia Saudita": "sa",
    "Argélia": "dz",
    "Argentina": "ar",
    "Austrália": "au",
    "Áustria": "at",
    "Bélgica": "be",
    "Bósnia e Herzegovina": "ba",
    "Brasil": "br",
    "Cabo Verde": "cv",
    "Canadá": "ca",
    "Catar": "qa",
    "Colômbia": "co",
    "Coreia do Sul": "kr",
    "Costa do Marfim": "ci",
    "Croácia": "hr",
    "Curaçao": "cw",
    "Egito": "eg",
    "Equador": "ec",
    "Escócia": "gb-sct",
    "Espanha": "es",
    "Estados Unidos": "us",
    "França": "fr",
    "Gana": "gh",
    "Haiti": "ht",
    "Inglaterra": "gb-eng",
    "Irã": "ir",
    "Iraque": "iq",
    "Japão": "jp",
    "Jordânia": "jo",
    "Marrocos": "ma",
    "México": "mx",
    "Noruega": "no",
    "Nova Zelândia": "nz",
    "Países Baixos": "nl",
    "Panamá": "pa",
    "Paraguai": "py",
    "Portugal": "pt",
    "RD Congo": "cd",
    "Senegal": "sn",
    "Suécia": "se",
    "Suíça": "ch",
    "Tchéquia": "cz",
    "Tunísia": "tn",
    "Turquia": "tr",
    "Uruguai": "uy",
    "Uzbequistão": "uz",
}


def flag_url(team: str, width: int = 40) -> str | None:
    """URL da bandeira no flagcdn, ou None se o time não estiver no dicionário."""
    code = FLAGS.get(team)
    return f"https://flagcdn.com/w{width}/{code}.png" if code else None
```

Em `app/templating.py`, adicionar ao bloco `templates.env.globals.update(...)` (linha 26):

```python
    flag_url=flag_url,
```

com o import no topo:

```python
from app.flags import flag_url
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_flags.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/flags.py app/templating.py tests/test_flags.py
git commit -m "feat: bandeiras das seleções via flagcdn (app/flags.py)"
```

---

### Task 4: Lógica pura da chave — `app/bracket.py`

**Files:**
- Create: `app/bracket.py`
- Test: `tests/test_bracket.py` (novo)

**Interfaces:**
- Consumes: `Match` (atributos `stage`, `bracket_pos`, `finished`, `teams_decided`), `MATCH_STAGES` de `app/phases.py`.
- Produces (usado pela Task 5 e pelos templates):
  - `BRACKET_STAGES = ["oitavas", "quartas", "semi", "final"]`, `SLOTS = {"oitavas": 8, "quartas": 4, "semi": 2, "final": 1}`
  - `side_of(stage: str, pos: int) -> str | None` — `"A"`/`"B"`, `None` na final
  - `next_slot(stage: str, pos: int) -> tuple[str, int] | None` — ex.: `("quartas", 1)`; `None` na final
  - `slot_label(stage: str, pos: int) -> str` — `"QF1"`, `"SF2"`, `"FINAL"`
  - `current_stage(matches) -> str`
  - `build_bracket(matches) -> dict[str, dict[int, Match | None]] | None`
  - `jogos_view(matches, fase_param: str | None) -> dict` (chaves: `selected_stage`, `view_mode`, `bracket`, `pairs_a`, `pairs_b`, `future_rows`, `past_stages`)

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_bracket.py`:

```python
"""Derivação da árvore do mata-mata e seleção de fase da página de jogos."""

from datetime import datetime

from app.bracket import (
    build_bracket,
    current_stage,
    jogos_view,
    next_slot,
    side_of,
    slot_label,
)
from app.models import Match


def _m(stage, pos=None, finished=False, decided=True, home="X", away="Y"):
    return Match(
        stage=stage,
        round=None,
        home_team=home,
        away_team=away,
        teams_decided=decided,
        is_brazil=False,
        kickoff_at=datetime.fromisoformat("2026-07-05T20:00:00+00:00"),
        finished=finished,
        bracket_pos=pos,
    )


def _chave_completa(oitavas_finished=False):
    ms = [_m("oitavas", p, finished=oitavas_finished) for p in range(1, 9)]
    ms += [_m("quartas", p, decided=False) for p in range(1, 5)]
    ms += [_m("semi", p, decided=False) for p in range(1, 3)]
    ms += [_m("final", 1, decided=False)]
    return ms


# ---- estrutura da árvore ---------------------------------------------------
def test_side_of():
    assert side_of("oitavas", 1) == "A"
    assert side_of("oitavas", 4) == "A"
    assert side_of("oitavas", 5) == "B"
    assert side_of("semi", 2) == "B"
    assert side_of("final", 1) is None


def test_next_slot():
    assert next_slot("oitavas", 1) == ("quartas", 1)
    assert next_slot("oitavas", 2) == ("quartas", 1)
    assert next_slot("oitavas", 8) == ("quartas", 4)
    assert next_slot("semi", 2) == ("final", 1)
    assert next_slot("final", 1) is None


def test_slot_label():
    assert slot_label("quartas", 1) == "QF1"
    assert slot_label("semi", 2) == "SF2"
    assert slot_label("final", 1) == "FINAL"


# ---- current_stage ----------------------------------------------------------
def test_current_stage_oitavas_em_andamento():
    ms = [_m("grupos", finished=True), _m("16avos", finished=True), _m("oitavas", 1)]
    assert current_stage(ms) == "oitavas"


def test_current_stage_tudo_encerrado():
    ms = [_m("final", 1, finished=True)]
    assert current_stage(ms) == "final"


def test_current_stage_sem_jogos():
    assert current_stage([]) == "grupos"


# ---- build_bracket ----------------------------------------------------------
def test_build_bracket_completo():
    br = build_bracket(_chave_completa())
    assert set(br) == {"oitavas", "quartas", "semi", "final"}
    assert br["oitavas"][3].home_team == "X"
    assert br["quartas"][4] is not None


def test_build_bracket_fallback_sem_bracket_pos():
    ms = _chave_completa()
    ms[0].bracket_pos = None  # dado antigo
    assert build_bracket(ms) is None


# ---- jogos_view ---------------------------------------------------------------
def test_jogos_view_modo_bracket_nas_oitavas():
    view = jogos_view(_chave_completa(), None)
    assert view["view_mode"] == "bracket"
    assert view["selected_stage"] == "oitavas"
    assert len(view["pairs_a"]) == 2 and len(view["pairs_b"]) == 2
    assert view["pairs_a"][0]["target"] == "QF1"
    # fases além da seguinte viram linhas compactas
    assert [r["label"] for r in view["future_rows"]] == ["SF1", "SF2", "FINAL"]


def test_jogos_view_fase_invalida_cai_na_atual():
    view = jogos_view(_chave_completa(), "banana")
    assert view["selected_stage"] == "oitavas"


def test_jogos_view_fase_lista_vira_modo_lista():
    view = jogos_view(_chave_completa(), "grupos")
    assert view["view_mode"] == "list"


def test_jogos_view_fallback_para_lista_sem_bracket_pos():
    ms = _chave_completa()
    ms[0].bracket_pos = None
    view = jogos_view(ms, None)
    assert view["view_mode"] == "list"


def test_jogos_view_past_stages():
    ms = [_m("grupos", finished=True), _m("16avos", finished=True)] + _chave_completa()
    view = jogos_view(ms, None)
    assert view["past_stages"] == ["grupos", "16avos"]


def test_jogos_view_na_final_sem_lados():
    ms = _chave_completa(oitavas_finished=True)
    for m in ms:
        if m.stage != "final":
            m.finished = True
        m.teams_decided = True
    view = jogos_view(ms, None)
    assert view["selected_stage"] == "final"
    assert view["pairs_b"] == []
    assert view["pairs_a"][0]["target"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_bracket.py -v`
Expected: FAIL — `ModuleNotFoundError: app.bracket`.

- [ ] **Step 3: Criar `app/bracket.py`**

```python
"""Derivação da árvore do mata-mata (funções puras, sem banco).

A estrutura vem de matches.bracket_pos: vencedores das posições 2k-1 e 2k de
uma fase alimentam a posição k da seguinte. Lado A = primeira metade.
"""

from app.phases import MATCH_STAGES

BRACKET_STAGES = ["oitavas", "quartas", "semi", "final"]
SLOTS = {"oitavas": 8, "quartas": 4, "semi": 2, "final": 1}
_PREFIX = {"quartas": "QF", "semi": "SF", "final": "FINAL"}


def side_of(stage: str, pos: int) -> str | None:
    """Lado da chave ('A'/'B'); a final não tem lado."""
    if stage == "final":
        return None
    return "A" if pos <= SLOTS[stage] // 2 else "B"


def next_slot(stage: str, pos: int) -> tuple[str, int] | None:
    """(fase, posição) que este jogo alimenta; None na final."""
    i = BRACKET_STAGES.index(stage)
    if stage == "final":
        return None
    return BRACKET_STAGES[i + 1], (pos + 1) // 2


def slot_label(stage: str, pos: int) -> str:
    """Rótulo curto do slot: QF1, SF2, FINAL."""
    prefix = _PREFIX.get(stage, stage.upper())
    return prefix if stage == "final" else f"{prefix}{pos}"


def current_stage(matches) -> str:
    """Primeira fase com jogo não-encerrado; 'final' se tudo acabou; 'grupos' sem jogos."""
    if not matches:
        return "grupos"
    for stage in MATCH_STAGES:
        if any(m.stage == stage and not m.finished for m in matches):
            return stage
    return "final"


def build_bracket(matches):
    """{fase: {pos: Match | None}} para oitavas -> final.

    Retorna None (sinal de fallback para lista) se algum jogo de mata-mata
    não tiver bracket_pos — dado antigo, nunca quebra a página.
    """
    knockout = [m for m in matches if m.stage in SLOTS]
    if any(m.bracket_pos is None for m in knockout):
        return None
    bracket = {stage: {pos: None for pos in range(1, SLOTS[stage] + 1)} for stage in BRACKET_STAGES}
    for m in knockout:
        if 1 <= m.bracket_pos <= SLOTS[m.stage]:
            bracket[m.stage][m.bracket_pos] = m
    return bracket


def _pairs(bracket, stage, side):
    """Pares consecutivos (2k-1, 2k) de um lado, com o rótulo do slot-alvo."""
    slots = bracket[stage]
    positions = [p for p in sorted(slots) if side_of(stage, p) == side]
    pairs = []
    for i in range(0, len(positions), 2):
        chunk = positions[i : i + 2]
        target = next_slot(stage, chunk[0])
        pairs.append(
            {
                "games": [(p, slots[p]) for p in chunk],
                "target": slot_label(*target) if target else None,
            }
        )
    return pairs


def jogos_view(matches, fase_param: str | None) -> dict:
    """Contexto de exibição da página de jogos (modo lista ou bracket)."""
    atual = current_stage(matches)
    sel = fase_param if fase_param in MATCH_STAGES else atual
    view = {
        "selected_stage": sel,
        "view_mode": "list",
        "bracket": None,
        "pairs_a": [],
        "pairs_b": [],
        "future_rows": [],
        "past_stages": [],
    }
    if sel not in BRACKET_STAGES:
        return view
    bracket = build_bracket(matches)
    if bracket is None:
        return view

    view["view_mode"] = "bracket"
    view["bracket"] = bracket
    view["past_stages"] = [
        s for s in MATCH_STAGES[: MATCH_STAGES.index(sel)] if any(m.stage == s for m in matches)
    ]
    if sel == "final":
        view["pairs_a"] = [{"games": [(1, bracket["final"][1])], "target": None}]
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

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_bracket.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bracket.py tests/test_bracket.py
git commit -m "feat: derivação da árvore do mata-mata (app/bracket.py)"
```

---

### Task 5: Rota `/` com o novo contexto

**Files:**
- Modify: `app/routers/pages.py:31-68` (função `home`)

**Interfaces:**
- Consumes: `jogos_view` da Task 4.
- Produces: contexto do template com a chave nova `view` (dict de `jogos_view`); mantém `groups`, `my_preds`, `my_br`, `is_open`, `saved`.

- [ ] **Step 1: Implementar**

(A lógica testável vive em `bracket.py` — Task 4 já cobriu. Aqui é só fiação.)

Em `app/routers/pages.py`, adicionar o import:

```python
from app.bracket import jogos_view
```

e na função `home`, antes do `return`, computar a view e incluí-la no contexto:

```python
    view = jogos_view(matches, request.query_params.get("fase"))
```

No dict do `TemplateResponse`, adicionar:

```python
            "view": view,
```

- [ ] **Step 2: Verificar que nada quebrou**

Run: `python -m pytest -v`
Expected: todos PASS.

Run: `python -c "from app.routers.pages import home; print('ok')"`
Expected: `ok` (sem erro de import).

- [ ] **Step 3: Commit**

```bash
git add app/routers/pages.py
git commit -m "feat: contexto de fase atual e chave na rota de jogos"
```

---

### Task 6: Macro do card de palpite + bandeiras na lista

**Files:**
- Create: `app/templates/_match_card.html`
- Modify: `app/templates/jogos.html` (usar a macro no loop existente)
- Modify: `scripts/build_assets.py:21-28` (adicionar `_match_card.html` a `TEMPLATE_NAMES`)
- Regenerate: `app/templates_data.py`

**Interfaces:**
- Produces: macro Jinja `match_card(m, pred, br, user, open, saved)` — o card completo atual (status, times com bandeira, form de placar + qualifier, bloco Neymar/Endrick). Usada pela lista (esta task) e pelo acordeão do bracket (Task 7).

- [ ] **Step 1: Criar `app/templates/_match_card.html`**

Mover o conteúdo do `<article>` de `jogos.html` (linhas 20–157) para dentro de uma macro, trocando `my_preds.get(m.id)`/`is_open[m.id]` pelos parâmetros e adicionando bandeiras. O arquivo completo:

```jinja
{% macro team_flag(name, cls) -%}
  {%- set url = flag_url(name) -%}
  {%- if url -%}
    <img src="{{ url }}" alt="" loading="lazy" class="inline-block w-5 h-auto rounded-[2px] shadow-sm align-[-2px] {{ cls }}">
  {%- else -%}
    <span class="inline-block w-5 h-3.5 rounded-[2px] bg-slate-200 align-[-2px] {{ cls }}"></span>
  {%- endif -%}
{%- endmacro %}

{% macro match_card(m, pred, br, user, open, saved) %}
<article id="jogo-{{ m.id }}" class="bg-white rounded-xl border border-slate-200 p-4 hover:border-slate-300 transition">
  {% if saved == m.id|string or saved == 'brasil-' ~ m.id|string %}
  <div class="mb-2.5 rounded-md bg-brand-green/10 border border-brand-green/30 px-3 py-1.5 text-sm text-brand-green font-medium text-center">✓ Palpite salvo!</div>
  {% endif %}
  <div class="flex items-center justify-between text-xs mb-2.5">
    <span class="text-slate-400">{{ m.kickoff_at | dt_br }}</span>
    {% if m.finished %}<span class="font-medium text-brand-green">Encerrado</span>
    {% elif open %}<span class="inline-flex items-center gap-1 font-medium text-slate-500"><span class="h-1.5 w-1.5 rounded-full bg-brand-green"></span>Aberto</span>
    {% else %}<span class="text-slate-300">Fechado</span>{% endif %}
  </div>

  {% if not m.teams_decided %}
    <div class="text-center text-sm text-slate-400 py-2">⏳ Aguardando definição dos times</div>
  {% else %}
    <div class="flex items-center justify-center gap-3 text-base font-medium text-slate-800 mb-1">
      <span class="flex-1 text-right">{% if m.is_brazil %}<span class="text-brand-yellow">★</span> {% endif %}{{ m.home_team }} {{ team_flag(m.home_team, 'ml-1') }}</span>
      {% if m.finished %}
        <span class="px-2.5 py-1 rounded-md bg-slate-900 text-white text-sm tabular-nums">{{ m.home_score }} : {{ m.away_score }}</span>
        {% if m.who_advanced %}
        <span class="text-xs text-slate-400">→ {{ m.home_team if m.who_advanced == 'home' else m.away_team }}</span>
        {% endif %}
      {% else %}
        <span class="text-slate-300 text-sm">vs</span>
      {% endif %}
      <span class="flex-1 text-left">{{ team_flag(m.away_team, 'mr-1') }} {{ m.away_team }}{% if m.is_brazil %} <span class="text-brand-yellow">★</span>{% endif %}</span>
    </div>
```

…e o restante do card **idêntico ao atual** (`jogos.html` linhas 47–156), com apenas estas substituições mecânicas:

- `is_open[m.id]` → `open`
- (nada mais muda: `pred`, `br`, `user`, `saved` já são nomes dos parâmetros)

Fechar com `</article>` e `{% endmacro %}`.

- [ ] **Step 2: Usar a macro em `jogos.html`**

Substituir o corpo do loop (linhas 17–158) por:

```jinja
{% import "_match_card.html" as cards %}
...
    {% for m in matches %}
    {{ cards.match_card(m, my_preds.get(m.id), my_br.get(m.id), user, is_open[m.id], saved) }}
    {% endfor %}
```

(preservando a estrutura de `<section>`/`<h2>` por fase que já existe).

- [ ] **Step 3: Registrar o template novo**

Em `scripts/build_assets.py`, adicionar a `TEMPLATE_NAMES`:

```python
    "_match_card.html",
```

- [ ] **Step 4: Regenerar, testar e verificar visualmente**

Run: `python scripts/build_assets.py && python -m pytest -v`
Expected: `OK templates_data.py (... 7 templates)`; testes PASS.

Verificação manual (banco local precisa da coluna nova):

```bash
del bolao_local.db
python scripts/seed.py
uvicorn app.main:app --reload
```

Abrir http://localhost:8000/ — os cards devem estar idênticos aos de antes, **agora com bandeirinhas** ao lado dos nomes (e placeholder cinza nos "A definir").

- [ ] **Step 5: Commit**

```bash
git add app/templates/_match_card.html app/templates/jogos.html scripts/build_assets.py app/templates_data.py
git commit -m "feat: card de palpite vira macro reutilizável com bandeiras"
```

---

### Task 7: Partial `_bracket.html` — mini-chave, lados, árvore e acordeão

**Files:**
- Create: `app/templates/_bracket.html`
- Modify: `app/templates/jogos.html` (chavear entre modo lista e modo bracket)
- Modify: `scripts/build_assets.py` (adicionar `_bracket.html`)
- Regenerate: `app/templates_data.py`

**Interfaces:**
- Consumes: contexto `view` (Task 5: `selected_stage`, `pairs_a`, `pairs_b`, `future_rows`, `past_stages`, `bracket`), macro `cards.match_card` (Task 6), global `flag_url` (Task 3), globals `stage_labels`, filtro `dt_br`.

- [ ] **Step 1: Criar `app/templates/_bracket.html`**

Conteúdo completo:

```jinja
{% import "_match_card.html" as cards %}

{# ---------- mini-chave: torneio inteiro, lado A <- 🏆 -> lado B ---------- #}
{% macro mini_pair(m, live) %}
<a href="/?fase={{ m.stage if m else '' }}" class="flex flex-col gap-px p-0.5 rounded border {{ 'border-brand-green bg-brand-green/10' if live else 'border-slate-200 bg-slate-50' }}">
  {% for name in ([m.home_team, m.away_team] if m and m.teams_decided else [None, None]) %}
    {% set url = name and flag_url(name, 20) %}
    {% if url %}<img src="{{ url }}" alt="{{ name }}" loading="lazy" class="w-[13px] h-[10px] object-cover rounded-[1px]">
    {% else %}<span class="w-[13px] h-[10px] bg-slate-200 rounded-[1px]"></span>{% endif %}
  {% endfor %}
</a>
{% endmacro %}

<div class="bg-white rounded-xl border border-slate-200 p-2.5 mb-3">
  <p class="text-[8px] font-semibold uppercase tracking-wider text-slate-400 text-center mb-1.5">Chave completa · toque numa fase para navegar</p>
  <div class="flex items-center justify-between gap-1">
    {% for stage in ['oitavas', 'quartas', 'semi'] %}
    <div class="flex flex-col gap-1 items-center flex-1">
      {% for pos in range(1, (view.bracket[stage]|length) + 1) if pos <= (view.bracket[stage]|length) // 2 %}
        {{ mini_pair(view.bracket[stage][pos], stage == view.selected_stage) }}
      {% endfor %}
      <span class="text-[7px] text-slate-400">{{ stage[:3]|upper }}·A</span>
    </div>
    {% endfor %}
    <div class="flex flex-col items-center flex-1">
      <span class="text-sm">🏆</span><span class="text-[7px] text-slate-400">FINAL</span>
    </div>
    {% for stage in ['semi', 'quartas', 'oitavas'] %}
    <div class="flex flex-col gap-1 items-center flex-1">
      {% for pos in range(1, (view.bracket[stage]|length) + 1) if pos > (view.bracket[stage]|length) // 2 %}
        {{ mini_pair(view.bracket[stage][pos], stage == view.selected_stage) }}
      {% endfor %}
      <span class="text-[7px] text-slate-400">{{ stage[:3]|upper }}·B</span>
    </div>
    {% endfor %}
  </div>
</div>

{# ---------- fases anteriores recolhidas ---------- #}
{% if view.past_stages %}
<div class="mb-3">
  <button type="button" onclick="var el=document.getElementById('fases-passadas'); el.classList.toggle('hidden'); this.querySelector('span').textContent = el.classList.contains('hidden') ? 'ver ▸' : 'esconder ▾'"
          class="w-full flex items-center justify-between bg-slate-100 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-500">
    <span class="truncate">Fases anteriores: <b class="text-slate-600">{% for s in view.past_stages %}{{ stage_labels[s] }}{{ ' · ' if not loop.last }}{% endfor %}</b></span>
    <span class="text-brand-green font-semibold shrink-0 ml-2">ver ▸</span>
  </button>
  {# escondido via JS no load — sem JS o histórico fica visível (degradação) #}
  <div id="fases-passadas" class="mt-3">
    {% for stage, matches_da_fase in past_groups %}
    <section class="mb-5">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2.5">{{ stage_labels[stage] }}</h2>
      <div class="grid gap-2.5">
        {% for m in matches_da_fase %}
        {{ cards.match_card(m, my_preds.get(m.id), my_br.get(m.id), user, is_open[m.id], saved) }}
        {% endfor %}
      </div>
    </section>
    {% endfor %}
  </div>
</div>
{% endif %}

{# ---------- abas Lado A | Lado B (sublinhado) ---------- #}
{% if view.selected_stage != 'final' %}
<div class="flex justify-center gap-6 border-b border-slate-200 mb-4" id="abas-lado">
  <button type="button" data-lado="a" onclick="trocaLado('a')" class="aba-lado text-sm font-semibold text-slate-900 border-b-2 border-brand-green -mb-px pb-1.5 px-1">Lado A</button>
  <button type="button" data-lado="b" onclick="trocaLado('b')" class="aba-lado text-sm text-slate-400 border-b-2 border-transparent -mb-px pb-1.5 px-1">Lado B</button>
</div>
{% endif %}

{# ---------- árvore vertical do lado selecionado ---------- #}
{% macro linha_time(m, name) %}
  {% set url = flag_url(name) %}
  <div class="flex items-center gap-1.5 py-0.5 text-sm text-slate-800">
    {% if url %}<img src="{{ url }}" alt="" loading="lazy" class="w-[18px] h-auto rounded-[2px] shadow-sm">
    {% else %}<span class="w-[18px] h-[13px] bg-slate-200 rounded-[2px]"></span>{% endif %}
    <span class="flex-1 truncate">{% if m.is_brazil and name == 'Brasil' %}<span class="text-brand-yellow">★</span> {% endif %}{{ name }}</span>
    {% if m.finished %}<span class="font-bold tabular-nums {{ 'text-slate-900' if (name == m.home_team and m.who_advanced == 'home') or (name == m.away_team and m.who_advanced == 'away') else 'text-slate-400' }}">{{ m.home_score if name == m.home_team else m.away_score }}</span>
    {% else %}<span class="text-slate-300">–</span>{% endif %}
  </div>
{% endmacro %}

{% macro arvore(pairs, lado) %}
<div id="lado-{{ lado }}" class="lado-chave">
  <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2.5">{{ stage_labels[view.selected_stage] }}{{ ' · Lado ' ~ lado|upper if view.selected_stage != 'final' }}</h2>
  {% for pair in pairs %}
  <div class="flex items-center mb-2.5">
    <div class="flex-1 grid gap-2">
      {% for pos, m in pair.games %}
        {% if m and m.teams_decided %}
        <div>
          <button type="button" onclick="document.getElementById('card-{{ m.id }}').classList.toggle('hidden')"
                  class="w-full text-left bg-white rounded-xl border {{ 'border-brand-green' if is_open[m.id] else 'border-slate-200' }} px-3 py-1.5 hover:border-slate-400 transition">
            {{ linha_time(m, m.home_team) }}
            {{ linha_time(m, m.away_team) }}
            <p class="text-[10px] mt-0.5 {{ 'text-brand-green' if my_preds.get(m.id) else 'text-slate-400' }}">
              {% if m.finished and m.who_advanced %}→ {{ m.home_team if m.who_advanced == 'home' else m.away_team }} avançou
              {% elif my_preds.get(m.id) %}✓ seu palpite: {{ my_preds[m.id].home_pred }}:{{ my_preds[m.id].away_pred }} · toque para editar
              {% elif is_open[m.id] %}● aberto · toque para palpitar
              {% else %}{{ m.kickoff_at | dt_br }}{% endif %}
            </p>
          </button>
          <div id="card-{{ m.id }}" class="mt-2 card-palpite">
            {{ cards.match_card(m, my_preds.get(m.id), my_br.get(m.id), user, is_open[m.id], saved) }}
          </div>
        </div>
        {% else %}
        <div class="rounded-xl border border-dashed border-slate-300 bg-slate-100 px-3 py-3 text-center text-xs text-slate-400">⏳ A definir{% if m %} · {{ m.kickoff_at | dt_br }}{% endif %}</div>
        {% endif %}
      {% endfor %}
    </div>
    {% if pair.target %}
    <div class="w-2.5 self-stretch my-4 border-y-2 border-r-2 border-slate-300 rounded-r-md shrink-0"></div>
    <div class="w-16 shrink-0 ml-1 text-center text-[10px] text-slate-400">
      <div class="rounded-lg border border-dashed border-slate-300 bg-slate-100 py-2">{{ pair.target }}</div>
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endmacro %}

{{ arvore(view.pairs_a, 'a') }}
{% if view.pairs_b %}{{ arvore(view.pairs_b, 'b') }}{% endif %}

{# ---------- fases futuras compactas ---------- #}
{% if view.future_rows %}
<h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mt-5 mb-2">Mais adiante</h2>
<div class="grid gap-1.5">
  {% for row in view.future_rows %}
  <div class="bg-white rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-400 flex justify-between">
    <span>{% if row.label == 'FINAL' %}🏆 {% endif %}{{ row.label }} · A definir</span>
    <span>{{ row.match.kickoff_at | dt_br if row.match }}</span>
  </div>
  {% endfor %}
</div>
{% endif %}

<script>
// Esconde via JS o que é interativo — sem JS, cards e histórico ficam visíveis (degradação).
document.querySelectorAll('.card-palpite').forEach(function (el) { el.classList.add('hidden'); });
var fp = document.getElementById('fases-passadas');
if (fp) { fp.classList.add('hidden'); }

function trocaLado(lado) {
  document.querySelectorAll('.lado-chave').forEach(function (el) {
    el.classList.toggle('hidden', el.id !== 'lado-' + lado);
  });
  document.querySelectorAll('.aba-lado').forEach(function (btn) {
    var on = btn.dataset.lado === lado;
    btn.classList.toggle('text-slate-900', on);
    btn.classList.toggle('font-semibold', on);
    btn.classList.toggle('border-brand-green', on);
    btn.classList.toggle('text-slate-400', !on);
    btn.classList.toggle('border-transparent', !on);
  });
}
if (document.getElementById('abas-lado')) { trocaLado('a'); }
</script>
```

- [ ] **Step 2: Chavear os modos em `jogos.html`**

Envolver o conteúdo após o `<h1>`/`<p>` iniciais:

```jinja
{% if view.view_mode == 'bracket' %}
  {% include "_bracket.html" %}
{% else %}
  {# loop de seções por fase existente (Task 6), inalterado #}
{% endif %}
```

E na rota (`app/routers/pages.py`), adicionar `past_groups` ao contexto — os grupos filtrados às fases passadas:

```python
            "past_groups": [(s, ms) for s, ms in groups if s in view["past_stages"]],
```

- [ ] **Step 3: Registrar e regenerar**

Em `scripts/build_assets.py`, adicionar `"_bracket.html",` a `TEMPLATE_NAMES`.

Run: `python scripts/build_assets.py && python -m pytest -v`
Expected: `OK templates_data.py (... 8 templates)`; testes PASS.

- [ ] **Step 4: Verificação manual completa**

```bash
uvicorn app.main:app --reload
```

Checklist em http://localhost:8000/ (celular: DevTools em 390px):

1. Página abre no modo bracket, oitavas, Lado A visível.
2. Mini-chave no topo com bandeirinhas dos 16 classificados; oitavas destacadas em verde; slots vazios cinza; tocar numa fase navega (`/?fase=quartas` mostra as quartas com slots "A definir").
3. Chip "Fases anteriores: Fase de grupos · 16-avos de final — ver ▸" expande/recolhe as listas antigas com bandeiras.
4. Abas Lado A | Lado B trocam a árvore sem recarregar.
5. Tocar num jogo aberto expande o card com o form de placar (e o qualifier de empate segue funcionando ao digitar empate); tocar de novo recolhe.
6. "Mais adiante" lista SF1, SF2 e 🏆 FINAL com datas.
7. `/?fase=grupos` e `/?fase=banana` → lista clássica / bracket da fase atual.
8. Sem JS (DevTools → disable JavaScript): os dois lados aparecem, cards funcionam via POST.

- [ ] **Step 5: Commit**

```bash
git add app/templates/_bracket.html app/templates/jogos.html app/routers/pages.py scripts/build_assets.py app/templates_data.py
git commit -m "feat: chaveamento do mata-mata com mini-chave, lados A/B e palpite em acordeão"
```

---

### Task 8: Documentação e verificação final

**Files:**
- Modify: `README.md` (formato do fixture + migração)

**Interfaces:** n/a.

- [ ] **Step 1: Atualizar o README**

No exemplo de formato de jogo do `fixtures.json` (README linha ~88), adicionar o campo:

```json
  "bracket_pos": 3             // posição na chave (oitavas 1-8 ... final 1); null fora do mata-mata
```

E na seção de administração, acrescentar o parágrafo:

```markdown
> **Migração (bancos criados antes do chaveamento):** rode
> `alter table matches add column if not exists bracket_pos int;` no SQL Editor
> do Supabase e clique em **Admin → Sincronizar fixtures** para preencher as
> posições da chave nos jogos existentes.
```

- [ ] **Step 2: Verificação final**

Run: `python -m pytest -v`
Expected: todos PASS.

Run: `python scripts/build_assets.py && git status --porcelain`
Expected: nenhum arquivo gerado pendente (working tree limpo além do README).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: bracket_pos no formato de fixtures e passo de migração"
```
