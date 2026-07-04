# 16 avos de final + Sync automático de resultados

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar os 16 jogos dos 16 avos de final, criar um mecanismo de sincronização de resultados via API da football-data.org, e suportar palpites de quem avança no mata-mata (incluindo prorrogação e pênaltis).

**Architecture:** Três eixos: (1) popular `fixtures.json` com os 16 jogos corretos via `import_fixtures.py`, depois criar função `seed_missing_matches` que insere somente os jogos ausentes no banco; (2) criar função `sync_results_from_api` em `services.py` e expor um botão no admin para disparar a sincronização sob demanda; (3) adicionar campo `qualifier_pred` em `predictions` e `who_advanced` em `matches` para suportar palpites de quem avança no mata-mata, com bônus de +5 pts quando o palpite prevê empate e acerta quem vence na prorrogação/pênaltis.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (SQLite local / PostgreSQL em prod), Jinja2, httpx, pytest, football-data.org API v4.

## Global Constraints

- Nunca apagar matches existentes; só inserir novos.
- Token `FOOTBALL_DATA_TOKEN` já é usado por `scripts/import_fixtures.py`; o mesmo token será lido em runtime via `os.environ` para o sync.
- A chave natural para deduplicação de matches é `(stage, kickoff_at)` — jogos do mata-mata nunca têm o mesmo horário dentro da mesma fase.
- Para jogos do grupo, não tentar re-inserir (a fase de grupos já está completa no banco).
- Nomes de time oriundos da API estão em inglês; para a fase 16avos em diante isso é aceitável (os grupos já têm nomes em português e permanecem intactos).
- Todos os datetimes são tratados como UTC.

---

## Arquivo: mapa de mudanças

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `app/data/fixtures.json` | Atualizar | Fonte de verdade dos jogos (todos os 16 avos) |
| `app/seed_data.py` | Regenerar (via script) | Cópia embutida para bundle serverless |
| `app/services.py` | Modificar | Adicionar `seed_missing_matches` e `sync_results_from_api` |
| `app/routers/admin.py` | Modificar | Novos endpoints `POST /admin/seed-missing` e `POST /admin/sync-resultados` |
| `app/templates/admin.html` | Modificar | Dois novos botões na seção de ferramentas |
| `app/templates_data.py` | Regenerar (via script) | Cópia embutida do admin.html atualizado |
| `tests/test_services.py` | Criar | Testes das duas novas funções |

**Task 4 — campos adicionais:**

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `schema.sql` | Modificar | Novas colunas `matches.who_advanced` e `predictions.qualifier_pred` |
| `app/models.py` | Modificar | Campos ORM correspondentes |
| `app/scoring.py` | Modificar | Nova função `score_knockout_match` com bônus de qualificador |
| `app/routers/predictions.py` | Modificar | Aceitar `qualifier_pred` no form para jogos de mata-mata |
| `app/routers/admin.py` | Modificar | Aceitar `who_advanced` no form de resultado |
| `app/templates/jogos.html` | Modificar | Radio "quem avança?" para jogos de mata-mata |
| `app/templates/admin.html` | Modificar | Radio "quem avançou?" no lançamento de resultado |
| `tests/test_scoring.py` | Modificar | Testes de `score_knockout_match` |

---

## Task 1: Atualizar fixtures.json com todos os 16 jogos dos 16 avos

**Files:**
- Modify: `app/data/fixtures.json`
- Modify: `app/seed_data.py` (auto-gerado por `scripts/build_assets.py`)

**Interfaces:**
- Produces: `fixtures.json` com exatamente 16 entradas `stage == "16avos"`, cada uma com `kickoff_at` único e correto.

> Esta task é uma execução de script — não tem TDD. Os passos são verificação manual.

- [ ] **Step 1: Verificar estado atual**

```bash
python -c "
import json
from pathlib import Path
data = json.loads(Path('app/data/fixtures.json').read_text())
avos = [x for x in data if x['stage'] == '16avos']
print(f'16avos: {len(avos)} jogos')
for x in avos:
    print(' ', x['kickoff_at'], x['home_team'], 'x', x['away_team'])
"
```
Esperado: 2 jogos (placeholders).

- [ ] **Step 2: Buscar schedule completo da API**

```bash
FOOTBALL_DATA_TOKEN=seu_token python scripts/import_fixtures.py
```

Caso não tenha token, criar conta gratuita em https://www.football-data.org/ (resposta em segundos).

Se o script retornar erro "Cobertura não disponível no plano free", adicionar os jogos manualmente conforme Step 2b.

- [ ] **Step 2b (alternativa manual): Adicionar 14 jogos de 16avos ao fixtures.json**

Abrir `app/data/fixtures.json` e, após os 2 jogos já existentes de `16avos`, inserir as 14 entradas restantes com as datas/horários corretos do calendário oficial (https://www.fifa.com/en/tournaments/mens/worldcup/articles/match-schedule). O formato de cada entrada:

```json
{
  "stage": "16avos",
  "round": null,
  "home_team": "A definir",
  "away_team": "A definir",
  "teams_decided": false,
  "is_brazil": false,
  "kickoff_at": "2026-07-01T18:00:00+00:00"
}
```

Repetir para cada jogo (total: 16 entradas `16avos`).

- [ ] **Step 3: Verificar que fixtures.json tem 16 jogos de 16avos**

```bash
python -c "
import json
from pathlib import Path
data = json.loads(Path('app/data/fixtures.json').read_text())
avos = [x for x in data if x['stage'] == '16avos']
print(f'16avos: {len(avos)} jogos')
assert len(avos) == 16, 'Esperado 16!'
print('OK')
"
```
Esperado: `16avos: 16 jogos` e `OK`.

- [ ] **Step 4: Regenerar seed_data.py**

```bash
python scripts/build_assets.py
```
Esperado: `OK seed_data.py (... bytes, 55 jogos)` (ou número próximo).

- [ ] **Step 5: Commit**

```bash
git add app/data/fixtures.json app/seed_data.py
git commit -m "data: adiciona os 16 jogos dos 16 avos de final"
```

---

## Task 2: Seed incremental — inserir jogos ausentes sem apagar existentes

**Files:**
- Modify: `app/services.py` — nova função `seed_missing_matches`
- Modify: `app/routers/admin.py` — novo endpoint `POST /admin/seed-missing`
- Modify: `app/templates/admin.html` — novo botão
- Modify: `app/templates_data.py` — regenerado após mudar admin.html
- Create: `tests/test_services.py`

**Interfaces:**
- Consumes: `load_fixtures()` de `app/data_loader.py` (já existente)
- Produces: `seed_missing_matches(db: Session) -> int` — retorna nº de jogos inseridos

- [ ] **Step 1: Criar o arquivo de testes e escrever o teste para `seed_missing_matches`**

Criar `tests/test_services.py`:

```python
"""Testes das funções de negócio em services.py."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.models import Base, Match
from app.services import seed_missing_matches, sync_results_from_api


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _match(stage: str, kickoff: str, home: str = "A definir", away: str = "A definir") -> Match:
    return Match(
        stage=stage,
        round=None,
        home_team=home,
        away_team=away,
        teams_decided=False,
        is_brazil=False,
        kickoff_at=datetime.fromisoformat(kickoff),
        finished=False,
    )


FAKE_FIXTURES = [
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-06-29T19:00:00+00:00",
    },
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-06-30T19:00:00+00:00",
    },
    {
        "stage": "16avos",
        "round": None,
        "home_team": "A definir",
        "away_team": "A definir",
        "teams_decided": False,
        "is_brazil": False,
        "kickoff_at": "2026-07-01T18:00:00+00:00",
    },
]


class TestSeedMissingMatches:
    def test_insere_todos_quando_banco_vazio(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        count = seed_missing_matches(db)
        assert count == 3
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 3

    def test_nao_duplica_jogos_ja_existentes(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        # Jogo de June 29 já está no banco
        db.add(_match("16avos", "2026-06-29T19:00:00+00:00"))
        db.commit()

        count = seed_missing_matches(db)
        assert count == 2  # só os dois novos
        total = db.scalar(select(func.count()).select_from(Match))
        assert total == 3

    def test_idempotente_segunda_chamada_retorna_zero(self, db, monkeypatch):
        monkeypatch.setattr("app.services.load_fixtures", lambda: FAKE_FIXTURES)
        seed_missing_matches(db)
        count2 = seed_missing_matches(db)
        assert count2 == 0
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
pytest tests/test_services.py::TestSeedMissingMatches -v
```
Esperado: `ImportError` ou `AttributeError` (função ainda não existe).

- [ ] **Step 3: Implementar `seed_missing_matches` em `app/services.py`**

Adicionar logo após `seed_matches`, ainda na seção de seed:

```python
def seed_missing_matches(db: Session) -> int:
    """Insere jogos de fixtures.json ainda ausentes no banco (dedup por stage + kickoff_at)."""
    existing: set[tuple[str, datetime]] = set()
    for m in db.scalars(select(Match)):
        kt = m.kickoff_at if m.kickoff_at.tzinfo else m.kickoff_at.replace(tzinfo=timezone.utc)
        existing.add((m.stage, kt))

    count = 0
    for f in load_fixtures():
        kt = datetime.fromisoformat(f["kickoff_at"])
        if kt.tzinfo is None:
            kt = kt.replace(tzinfo=timezone.utc)
        if (f["stage"], kt) in existing:
            continue
        db.add(
            Match(
                stage=f["stage"],
                round=f.get("round"),
                home_team=f["home_team"],
                away_team=f["away_team"],
                teams_decided=f.get("teams_decided", True),
                is_brazil=f.get("is_brazil", False),
                kickoff_at=kt,
            )
        )
        count += 1
    db.commit()
    return count
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
pytest tests/test_services.py::TestSeedMissingMatches -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Adicionar endpoint `POST /admin/seed-missing` em `app/routers/admin.py`**

Adicionar import no topo (junto aos imports existentes):
```python
from app.services import recompute_match, recompute_specials, seed_matches, seed_missing_matches
```

Adicionar rota após `run_seed`:
```python
@router.post("/seed-missing")
def run_seed_missing(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    seed_missing_matches(db)
    return RedirectResponse(url="/admin", status_code=303)
```

- [ ] **Step 6: Adicionar botão no `app/templates/admin.html`**

Localizar a section "Importar jogos" (linha 7–13) e adicionar uma nova `<section>` logo abaixo, dentro do mesmo `<div class="grid md:grid-cols-2 gap-4 mb-8">`:

```html
  <section class="bg-white rounded-xl border border-slate-200 p-5">
    <h2 class="font-semibold text-slate-900 mb-2">Importar jogos faltando</h2>
    <p class="text-sm text-slate-500 mb-3">Adiciona ao banco os jogos de <code class="text-slate-600">fixtures.json</code> que ainda não existem (seguro de rodar várias vezes).</p>
    <form method="post" action="/admin/seed-missing">
      <button class="px-4 py-2 rounded-lg bg-slate-700 text-white font-medium hover:brightness-110 transition">Importar faltando</button>
    </form>
  </section>
```

- [ ] **Step 7: Regenerar templates_data.py**

```bash
python scripts/build_assets.py
```

- [ ] **Step 8: Testar localmente**

```bash
uvicorn app.main:app --reload
```
Acessar `/admin`, verificar que o botão "Importar faltando" aparece. Clicar nele e confirmar que os 14 novos jogos de 16avos aparecem na lista.

- [ ] **Step 9: Commit**

```bash
git add app/services.py app/routers/admin.py app/templates/admin.html app/templates_data.py tests/test_services.py
git commit -m "feat: seed incremental — importar jogos faltando sem apagar existentes"
```

---

## Task 3: Sincronizar resultados via football-data.org

**Files:**
- Modify: `app/services.py` — nova função `sync_results_from_api`
- Modify: `app/routers/admin.py` — novo endpoint `POST /admin/sync-resultados`
- Modify: `app/templates/admin.html` — novo botão
- Modify: `app/templates_data.py` — regenerado

**Interfaces:**
- Consumes: `FOOTBALL_DATA_TOKEN` env var; `recompute_match(db, match)` (já existente)
- Produces: `sync_results_from_api(db: Session, token: str) -> int` — retorna nº de jogos atualizados

**Nota:** `httpx` já é dependência do projeto (usado em `import_fixtures.py`).

- [ ] **Step 1: Escrever os testes para `sync_results_from_api`**

Adicionar ao final de `tests/test_services.py`:

```python
import httpx
import respx  # pip install respx


FAKE_API_RESPONSE = {
    "matches": [
        {
            "stage": "LAST_32",
            "utcDate": "2026-06-29T19:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"name": "Germany"},
            "awayTeam": {"name": "Morocco"},
            "score": {
                "fullTime": {"home": 2, "away": 1}
            },
        },
        {
            "stage": "LAST_32",
            "utcDate": "2026-06-30T19:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"name": "France"},
            "awayTeam": {"name": "Japan"},
            "score": {
                "fullTime": {"home": None, "away": None}  # ainda sem placar (não deve atualizar)
            },
        },
    ]
}


class TestSyncResultsFromApi:
    def test_atualiza_jogo_finalizado(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        # Jogo existe no banco, ainda não finalizado
        m = _match("16avos", "2026-06-29T19:00:00+00:00", "Germany", "Morocco")
        m.teams_decided = True
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")

        assert count == 1
        db.refresh(m)
        assert m.finished is True
        assert m.home_score == 2
        assert m.away_score == 1

    def test_ignora_placar_nulo(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        m = _match("16avos", "2026-06-30T19:00:00+00:00", "France", "Japan")
        m.teams_decided = True
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")

        assert count == 0
        db.refresh(m)
        assert m.finished is False

    def test_nao_re_processa_jogo_ja_finalizado(self, db, respx_mock):
        respx_mock.get("https://api.football-data.org/v4/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=FAKE_API_RESPONSE)
        )
        m = _match("16avos", "2026-06-29T19:00:00+00:00", "Germany", "Morocco")
        m.teams_decided = True
        m.finished = True
        m.home_score = 2
        m.away_score = 1
        db.add(m)
        db.commit()

        count = sync_results_from_api(db, token="fake-token")
        assert count == 0
```

> Requer `respx` para mock de chamadas HTTP: `pip install respx`
> Adicionar `respx` ao `requirements.txt` (ou `requirements-dev.txt` se houver).

- [ ] **Step 2: Verificar que os testes falham**

```bash
pytest tests/test_services.py::TestSyncResultsFromApi -v
```
Esperado: `ImportError` (função ainda não existe).

- [ ] **Step 3: Instalar respx**

```bash
pip install respx
```

Adicionar ao arquivo de dependências de desenvolvimento (se houver `requirements-dev.txt`) ou ao `requirements.txt`:
```
respx
```

- [ ] **Step 4: Implementar `sync_results_from_api` em `app/services.py`**

Adicionar o import `import httpx` no topo de `app/services.py` (junto aos imports já existentes).
Adicionar também `from datetime import timedelta` no import de datetime.

Adicionar a função ao final de `app/services.py`:

```python
_STAGE_MAP_API = {
    "GROUP_STAGE": "grupos",
    "LAST_32": "16avos",
    "LAST_16": "oitavas",
    "QUARTER_FINALS": "quartas",
    "SEMI_FINALS": "semi",
    "FINAL": "final",
}


def sync_results_from_api(db: Session, token: str) -> int:
    """Busca resultados finalizados na football-data.org e atualiza o banco.

    Retorna o número de jogos atualizados.
    Não re-processa jogos já marcados como finished.
    Correspondência por (stage, kickoff_at) com tolerância de ±5 minutos.
    """
    import httpx  # import local para não pesar no bundle serverless

    resp = httpx.get(
        "https://api.football-data.org/v4/competitions/WC/matches",
        params={"status": "FINISHED"},
        headers={"X-Auth-Token": token},
        timeout=30,
    )
    resp.raise_for_status()

    count = 0
    for m in resp.json().get("matches", []):
        stage = _STAGE_MAP_API.get(m.get("stage", ""))
        if not stage:
            continue

        score = (m.get("score") or {}).get("fullTime") or {}
        home_score = score.get("home")
        away_score = score.get("away")
        if home_score is None or away_score is None:
            continue

        api_kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        window_start = api_kickoff - timedelta(minutes=5)
        window_end = api_kickoff + timedelta(minutes=5)

        local = db.scalar(
            select(Match).where(
                Match.stage == stage,
                Match.kickoff_at >= window_start.replace(tzinfo=None),
                Match.kickoff_at <= window_end.replace(tzinfo=None),
            )
        )
        if local is None or local.finished:
            continue

        local.home_score = home_score
        local.away_score = away_score
        local.finished = True
        db.commit()
        recompute_match(db, local)
        count += 1

    return count
```

> Nota: `window_start.replace(tzinfo=None)` converte para naive UTC para comparar com o banco (SQLite armazena sem timezone). Em PostgreSQL (produção), o SQLAlchemy trata automaticamente.

- [ ] **Step 5: Rodar os testes**

```bash
pytest tests/test_services.py::TestSyncResultsFromApi -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 6: Rodar todos os testes**

```bash
pytest -v
```
Esperado: todos os testes passam.

- [ ] **Step 7: Adicionar endpoint `POST /admin/sync-resultados` em `app/routers/admin.py`**

Adicionar import no topo:
```python
import os
from app.services import recompute_match, recompute_specials, seed_matches, seed_missing_matches, sync_results_from_api
```

Adicionar rota:
```python
@router.post("/sync-resultados")
def run_sync_resultados(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="FOOTBALL_DATA_TOKEN não configurado.")
    sync_results_from_api(db, token)
    return RedirectResponse(url="/admin", status_code=303)
```

- [ ] **Step 8: Adicionar botão no `app/templates/admin.html`**

Adicionar uma terceira `<section>` no mesmo grid das outras duas, após o botão "Importar faltando" da Task 2:

```html
  <section class="bg-white rounded-xl border border-slate-200 p-5">
    <h2 class="font-semibold text-slate-900 mb-2">Sincronizar resultados</h2>
    <p class="text-sm text-slate-500 mb-3">Busca placares de jogos finalizados na football-data.org e recalcula pontos automaticamente. Requer <code class="text-slate-600">FOOTBALL_DATA_TOKEN</code>.</p>
    <form method="post" action="/admin/sync-resultados">
      <button class="px-4 py-2 rounded-lg bg-brand-blue text-white font-medium hover:brightness-110 transition">Sincronizar da API</button>
    </form>
  </section>
```

- [ ] **Step 9: Regenerar templates_data.py**

```bash
python scripts/build_assets.py
```

- [ ] **Step 10: Configurar FOOTBALL_DATA_TOKEN no ambiente**

**Local (`.env` ou export):**
```bash
export FOOTBALL_DATA_TOKEN=seu_token
uvicorn app.main:app --reload
```

**Produção (Vercel):** Adicionar `FOOTBALL_DATA_TOKEN` como variável de ambiente no dashboard do projeto em Settings → Environment Variables.

- [ ] **Step 11: Testar o fluxo completo localmente**

```bash
uvicorn app.main:app --reload
```
1. Acessar `/admin`
2. Clicar "Sincronizar da API"
3. Verificar no console que a chamada HTTP foi feita (ou inspecionar o banco)
4. Confirmar que jogos já finalizados aparecem com placar e status "encerrado"

- [ ] **Step 12: Commit**

```bash
git add app/services.py app/routers/admin.py app/templates/admin.html app/templates_data.py tests/test_services.py requirements.txt
git commit -m "feat: sincronizar resultados automaticamente via football-data.org"
```

---

---

## Task 4: Palpite de quem avança no mata-mata

**Files:**
- Modify: `schema.sql` — novas colunas nas duas tabelas
- Modify: `app/models.py` — campos ORM
- Modify: `app/scoring.py` — `score_knockout_match` + constante
- Modify: `app/routers/predictions.py` — aceitar `qualifier_pred`
- Modify: `app/routers/admin.py` — aceitar `who_advanced`
- Modify: `app/templates/jogos.html` — radio "quem avança?" para mata-mata
- Modify: `app/templates/admin.html` — radio "quem avançou?" no lançamento de resultado
- Modify: `app/services.py` — `recompute_match` usa scorer correto por fase
- Modify: `app/templates_data.py` — regenerar
- Modify: `tests/test_scoring.py` — testes de `score_knockout_match`

**Interfaces:**
- Consumes: `Match.stage` para decidir se aplica scoring de mata-mata
- Produces: `score_knockout_match(pred_home, pred_away, qualifier_pred, real_home, real_away, who_advanced) -> int`
- Produces: `Match.who_advanced: str | None` — `'home'` / `'away'` / `None`
- Produces: `Prediction.qualifier_pred: str | None` — `'home'` / `'away'` / `None`

**Regra de pontuação do bônus:**
O bônus de +5 pts é concedido **somente se** o palpite de placar foi empate (`pred_home == pred_away`) **E** o resultado real dos 90 min também foi empate (`real_home == real_away`) **E** o qualificador previsto bate com o time que efetivamente avançou. Em qualquer outro caso, o bônus é zero.

---

- [ ] **Step 1: Adicionar colunas ao schema.sql**

Abrir `schema.sql` e adicionar as colunas faltantes nas duas tabelas existentes.

Na tabela `matches`, após `finished boolean`:
```sql
who_advanced   text,        -- 'home' | 'away' | null (mata-mata: quem avançou)
```

Na tabela `predictions`, após `points integer`:
```sql
qualifier_pred text         -- 'home' | 'away' | null (mata-mata: quem o usuário acha que avança)
```

Para **migrar bancos existentes** (local e produção), rodar no SQL:
```sql
ALTER TABLE matches     ADD COLUMN IF NOT EXISTS who_advanced   text;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS qualifier_pred text;
```

No SQLite local (sem suporte a `IF NOT EXISTS` em ALTER):
```sql
ALTER TABLE matches     ADD COLUMN who_advanced   text;
ALTER TABLE predictions ADD COLUMN qualifier_pred text;
```

- [ ] **Step 2: Atualizar os modelos ORM em `app/models.py`**

Na classe `Match`, adicionar após `finished`:
```python
who_advanced: Mapped[str | None] = mapped_column(String, nullable=True)
```

Na classe `Prediction`, adicionar após `points`:
```python
qualifier_pred: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 3: Escrever os testes para `score_knockout_match` em `tests/test_scoring.py`**

Adicionar no final do arquivo:

```python
from app.scoring import score_knockout_match


class TestScoreKnockoutMatch:
    # --- placar decidido em 90 min: bônus nunca se aplica ---
    def test_placar_cravado_sem_empate(self):
        assert score_knockout_match(2, 1, "home", 2, 1, "home") == 10

    def test_placar_winner_goaldiff(self):
        assert score_knockout_match(1, 0, "home", 2, 1, "home") == 7

    def test_placar_so_winner(self):
        assert score_knockout_match(2, 0, "home", 3, 1, "home") == 5

    def test_errou_resultado_nao_ganha_bonus(self):
        # Previu empate, saiu vitória — 0 pts (nem tenta bônus)
        assert score_knockout_match(1, 1, "home", 2, 1, "home") == 0

    # --- prorrogação/pênaltis: ambos empate nos 90 min ---
    def test_cravou_placar_e_qualificador(self):
        # 1x1 + home avança
        assert score_knockout_match(1, 1, "home", 1, 1, "home") == 15  # 10 + 5

    def test_acertou_empate_e_qualificador_saldo(self):
        # 1x1 previu, saiu 0x0 — mesmo saldo (0), qualificador correto
        assert score_knockout_match(1, 1, "home", 0, 0, "home") == 12  # 7 + 5

    def test_acertou_empate_mas_errou_qualificador(self):
        # Placar cravado mas errou quem avança
        assert score_knockout_match(1, 1, "home", 1, 1, "away") == 10  # 10 + 0

    def test_acertou_empate_qualificador_saldo_errou_quem_avanca(self):
        assert score_knockout_match(1, 1, "home", 0, 0, "away") == 7   # 7 + 0

    def test_qualificador_none_nao_da_bonus(self):
        # Usuário não preencheu o qualifier (palpite antigo)
        assert score_knockout_match(1, 1, None, 1, 1, "home") == 10    # 10 + 0

    def test_who_advanced_none_nao_da_bonus(self):
        # Admin ainda não informou quem avançou
        assert score_knockout_match(1, 1, "home", 1, 1, None) == 10    # 10 + 0
```

- [ ] **Step 4: Rodar os testes para confirmar que falham**

```bash
pytest tests/test_scoring.py::TestScoreKnockoutMatch -v
```
Esperado: `ImportError` (função ainda não existe).

- [ ] **Step 5: Implementar `score_knockout_match` em `app/scoring.py`**

Adicionar após as constantes de pontos existentes:
```python
POINTS_QUALIFIER = 5  # bônus por acertar quem avançou em prorrogação/pênaltis
```

Adicionar após `score_match`:
```python
def score_knockout_match(
    pred_home: int,
    pred_away: int,
    qualifier_pred: str | None,
    real_home: int,
    real_away: int,
    who_advanced: str | None,
) -> int:
    """Pontos de um palpite de mata-mata: placar dos 90 min + bônus de qualificador.

    Bônus de +5 pts: somente quando TANTO o palpite QUANTO o resultado real
    foram empate nos 90 min E o qualificador previsto bate com quem avançou.
    """
    base = score_match(pred_home, pred_away, real_home, real_away)
    pred_draw = pred_home == pred_away
    real_draw = real_home == real_away
    if pred_draw and real_draw and qualifier_pred and who_advanced:
        if qualifier_pred == who_advanced:
            base += POINTS_QUALIFIER
    return base
```

- [ ] **Step 6: Rodar os testes de scoring**

```bash
pytest tests/test_scoring.py -v
```
Esperado: todos os testes PASSED (incluindo os existentes).

- [ ] **Step 7: Atualizar `recompute_match` em `app/services.py`**

Localizar a função `recompute_match`. Substituir o bloco de cálculo de pontos por:

```python
def recompute_match(db: Session, match: Match) -> None:
    """Recalcula os pontos de um jogo (placar + perguntas do Brasil)."""
    if not match.finished or match.home_score is None or match.away_score is None:
        return
    is_knockout = match.stage != "grupos"
    for pred in db.scalars(select(Prediction).where(Prediction.match_id == match.id)):
        if is_knockout:
            pred.points = scoring.score_knockout_match(
                pred.home_pred, pred.away_pred, pred.qualifier_pred,
                match.home_score, match.away_score, match.who_advanced,
            )
        else:
            pred.points = scoring.score_match(
                pred.home_pred, pred.away_pred, match.home_score, match.away_score
            )
    if match.is_brazil:
        for bp in db.scalars(
            select(BrazilMatchPrediction).where(BrazilMatchPrediction.match_id == match.id)
        ):
            bp.points = scoring.brazil_yesno_points(
                bp.neymar_in, match.neymar_played
            ) + scoring.brazil_yesno_points(bp.endrick_in, match.endrick_played)
    db.commit()
```

- [ ] **Step 8: Atualizar `app/routers/predictions.py` para aceitar `qualifier_pred`**

Substituir a função `save_prediction` inteira por:

```python
@router.post("/{match_id}")
def save_prediction(
    match_id: int,
    home_pred: int = Form(...),
    away_pred: int = Form(...),
    qualifier_pred: str = Form(default=""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if not match_is_open(match):
        raise HTTPException(status_code=400, detail="Palpites deste jogo estão fechados.")
    if home_pred < 0 or away_pred < 0:
        raise HTTPException(status_code=400, detail="Placar não pode ser negativo.")

    pred = db.scalar(
        select(Prediction).where(
            Prediction.user_id == user.id, Prediction.match_id == match_id
        )
    )
    if pred is None:
        pred = Prediction(user_id=user.id, match_id=match_id)
        db.add(pred)
    pred.home_pred = home_pred
    pred.away_pred = away_pred
    if match.stage != "grupos":
        pred.qualifier_pred = qualifier_pred if qualifier_pred in ("home", "away") else None
    db.commit()
    return RedirectResponse(url=f"/?saved={match_id}#jogo-{match_id}", status_code=303)
```

- [ ] **Step 9: Atualizar `app/routers/admin.py` para aceitar `who_advanced`**

Localizar a função `set_result` e adicionar o parâmetro e o campo:

```python
@router.post("/match/{match_id}/resultado")
def set_result(
    match_id: int,
    home_score: int = Form(...),
    away_score: int = Form(...),
    neymar_played: str = Form(default="off"),
    endrick_played: str = Form(default="off"),
    who_advanced: str = Form(default=""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    match.home_score = home_score
    match.away_score = away_score
    match.finished = True
    if match.is_brazil:
        match.neymar_played = neymar_played == "on"
        match.endrick_played = endrick_played == "on"
    if match.stage != "grupos":
        match.who_advanced = who_advanced if who_advanced in ("home", "away") else None
    db.commit()
    recompute_match(db, match)
    return RedirectResponse(url="/admin", status_code=303)
```

- [ ] **Step 10: Atualizar `app/templates/admin.html` — adicionar "quem avançou?" no formulário de resultado**

Localizar o bloco do formulário de resultado (começa em `<form method="post" action="/admin/match/{{ m.id }}/resultado"`). Adicionar o campo de qualificador **antes** do botão "Lançar resultado":

```html
{% if m.stage != 'grupos' %}
<div class="flex items-center gap-3 text-sm">
  <span class="text-xs text-slate-400">Quem avançou:</span>
  <label class="flex items-center gap-1 text-xs text-slate-500">
    <input type="radio" name="who_advanced" value="home" {{ 'checked' if m.who_advanced == 'home' }}> {{ m.home_team }}
  </label>
  <label class="flex items-center gap-1 text-xs text-slate-500">
    <input type="radio" name="who_advanced" value="away" {{ 'checked' if m.who_advanced == 'away' }}> {{ m.away_team }}
  </label>
</div>
{% endif %}
```

- [ ] **Step 11: Atualizar `app/templates/jogos.html` — mostrar "quem avança?" para jogos de mata-mata**

**11a.** No bloco do formulário ativo (dentro de `{% if user and is_open[m.id] %}`), adicionar o seletor de qualificador logo após os inputs de placar e antes do botão, **dentro da `<form>`**:

```html
{% if m.stage != 'grupos' %}
<div class="w-full mt-2">
  <p class="text-xs text-slate-400 mb-1.5 text-center">Em caso de empate, quem avança? <span class="font-medium text-brand-green">+5 pts</span></p>
  <div class="flex justify-center gap-6 text-sm">
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="home"
             {{ 'checked' if pred and pred.qualifier_pred == 'home' }} required>
      <span class="text-slate-700">{{ m.home_team }}</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="away"
             {{ 'checked' if pred and pred.qualifier_pred == 'away' }} required>
      <span class="text-slate-700">{{ m.away_team }}</span>
    </label>
  </div>
</div>
{% endif %}
```

**11b.** No bloco de exibição do palpite salvo (`✓ Palpite salvo: ...`), adicionar o qualificador na linha:

```html
{% if m.stage != 'grupos' and pred and pred.qualifier_pred %}
· avança: <b>{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>
{% endif %}
```

**11c.** No bloco de palpite fechado (exibe "Seu palpite: X : Y"), adicionar:

```html
{% if m.stage != 'grupos' and pred.qualifier_pred %}
· avança: <b class="text-slate-700">{{ m.home_team if pred.qualifier_pred == 'home' else m.away_team }}</b>
{% endif %}
```

**11d.** Exibir quem efetivamente avançou quando o jogo estiver encerrado. Adicionar logo após o placar real (`<span class="px-2.5 py-1 ...">{{ m.home_score }} : {{ m.away_score }}</span>`):

```html
{% if m.who_advanced %}
<span class="text-xs text-slate-400">→ {{ m.home_team if m.who_advanced == 'home' else m.away_team }}</span>
{% endif %}
```

- [ ] **Step 12: Rodar todos os testes**

```bash
pytest -v
```
Esperado: todos os testes PASSED.

- [ ] **Step 13: Regenerar templates_data.py**

```bash
python scripts/build_assets.py
```

- [ ] **Step 14: Migrar banco local e testar o fluxo completo**

```bash
# Migrar banco SQLite local
python -c "
from app.db import engine
with engine.connect() as conn:
    conn.execute('ALTER TABLE matches ADD COLUMN who_advanced text')
    conn.execute('ALTER TABLE predictions ADD COLUMN qualifier_pred text')
    conn.commit()
print('Migração OK')
"
```

```bash
uvicorn app.main:app --reload
```

Fluxo de teste:
1. Ir em `/` e abrir um jogo de mata-mata → verificar que aparece "Em caso de empate, quem avança?"
2. Salvar palpite com empate + qualificador → confirmar que fica salvo e exibido
3. No `/admin`, lançar resultado de um jogo de mata-mata com "quem avançou"
4. Confirmar que o card do jogo exibe o qualificador real
5. Verificar que pontos são calculados corretamente (empate + qualificador certo = 10+5)

- [ ] **Step 15: Atualizar `sync_results_from_api` para popular `who_advanced`**

Na função `sync_results_from_api` em `app/services.py`, adicionar o preenchimento de `who_advanced` junto ao placar. Localizar onde `local.home_score` e `local.away_score` são atribuídos e adicionar:

```python
# Determinar quem avançou a partir do campo "winner" da API
winner = (m.get("score") or {}).get("winner")  # "HOME_TEAM" | "AWAY_TEAM" | null
if local.stage != "grupos" and winner:
    local.who_advanced = "home" if winner == "HOME_TEAM" else "away"
```

- [ ] **Step 16: Commit**

```bash
git add schema.sql app/models.py app/scoring.py app/routers/predictions.py app/routers/admin.py app/templates/jogos.html app/templates/admin.html app/services.py app/templates_data.py tests/test_scoring.py
git commit -m "feat: palpite de quem avança no mata-mata (+5 pts em caso de empate acertado)"
```

---

## Self-Review

**Spec coverage:**
- ✅ 16 jogos dos 16 avos → Task 1 (fixtures.json) + Task 2 (seed incremental)
- ✅ Menos atualização manual → Task 3 (sync via API + botão admin)
- ✅ Jogos existentes preservados → `seed_missing_matches` só insere novos
- ✅ Pontos recalculados após sync → `recompute_match` chamado em cada jogo atualizado
- ✅ Palpite de quem avança → Task 4 (qualifier_pred + who_advanced + score_knockout_match)
- ✅ Bônus só quando ambos empate (pred + real) → regra em `score_knockout_match`
- ✅ Retrocompatível → colunas nullable; palpites antigos sem qualifier recebem 0 de bônus
- ✅ Admin + sync populam `who_advanced` → Task 4 steps 9 e 15

**Riscos e notas:**
- A football-data.org gratuita pode não cobrir a Copa 2026 em tempo real; teste antes de confiar no sync.
- O campo `score.fullTime` da API pode incluir gols de prorrogação; o campo correto para placar em 90 min seria `score.regularTime` quando disponível. Verificar com a API real antes de ir a produção.
- O grid no admin ficará com 3+ seções. Se quiser manter 2 colunas, ajuste `grid-cols-2` para `grid-cols-3` ou reorganize em duas linhas.
- A tolerância de ±5 min no matching por `kickoff_at` cobre eventuais diferenças de representação UTC. Se dois jogos de mata-mata tiverem kickoffs a menos de 10 minutos um do outro (improvável), pode haver falso match.
- Palpites de grupos já salvos não são afetados: `recompute_match` usa `score_match` para `stage == "grupos"`.
