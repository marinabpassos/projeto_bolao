# ⚽ Bolão da Copa 2026

Site de bolão entre amigos para a Copa do Mundo 2026. Login com Google, palpites
de placar, apostas especiais (artilheiro, Neymar/Endrick, até onde o Brasil vai) e
ranking automático. Feito em **Python (FastAPI)**, hospedado de graça na **Vercel**
com banco **Supabase**.

## Como funciona a pontuação

| Aposta | Pontos |
|---|---|
| Placar cravado | 10 |
| Acertou vencedor/empate **e** o saldo de gols | 7 |
| Acertou só o vencedor/empate | 5 |
| Neymar entra? / Endrick entra? (cada, nos jogos do Brasil) | 3 |
| Artilheiro da Copa | 60 / 50 / 40 / 30 / 20 / 10 conforme a fase do **último palpite** (grupos → final) |
| Até onde o Brasil vai | 30 no acerto exato; se ninguém cravar, o mais próximo leva |

- O bolão começa na **3ª rodada da fase de grupos**.
- Palpite de cada jogo é editável **até o apito**.
- Jogos do mata-mata abrem **quando os times são definidos** (admin preenche).

Todos os valores ficam em `app/phases.py` e `app/scoring.py`, fáceis de ajustar.

## Stack

FastAPI · Jinja2 + Tailwind (CDN) · Authlib (Google OAuth) · SQLAlchemy · Supabase
(Postgres) · Vercel (deploy serverless).

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/CMD)
pip install -r requirements.txt
copy .env.example .env            # e preencha os valores
python scripts\seed.py            # carrega data/fixtures.json no banco
uvicorn app.main:app --reload     # http://localhost:8000
```

Rodar os testes da pontuação:

```bash
pytest
```

## Configuração dos serviços gratuitos

### 1. Supabase (banco)
1. Crie um projeto em <https://supabase.com> (free).
2. Em **SQL Editor**, rode o conteúdo de [`schema.sql`](schema.sql).
3. Em **Project Settings → Database → Connection string → Transaction pooler**,
   copie a string (porta **6543**) e use em `DATABASE_URL`, trocando o prefixo
   para `postgresql+psycopg://`.

### 2. Google OAuth (login)
1. Em <https://console.cloud.google.com> crie um projeto.
2. **APIs e Serviços → Tela de consentimento OAuth** (modo "Em teste" já basta;
   adicione os e-mails dos amigos como usuários de teste).
3. **Credenciais → Criar credenciais → ID do cliente OAuth → App da Web**.
   - URIs de redirecionamento autorizados:
     - `http://localhost:8000/auth/callback`
     - `https://SEU-PROJETO.vercel.app/auth/callback`
4. Copie o **Client ID** e **Client Secret** para o `.env`.

### 3. Vercel (deploy)
1. Suba este repositório no GitHub.
2. Em <https://vercel.com> → **Add New Project** → importe o repositório.
3. Em **Settings → Environment Variables**, configure: `DATABASE_URL`,
   `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAILS`,
   `BASE_URL` (ex.: `https://SEU-PROJETO.vercel.app`) e `FOOTBALL_DATA_TOKEN`
   (token grátis da football-data.org, opcional — só para a sincronização automática).
4. Deploy. A cada `git push` a Vercel publica de novo.

> Gere um `SESSION_SECRET`:
> `python -c "import secrets; print(secrets.token_hex(32))"`

## Cadastrar os jogos

- **Manual:** edite [`data/fixtures.json`](data/fixtures.json) (já vem com um exemplo
  da 3ª rodada + esqueleto do mata-mata) e rode `python scripts/seed.py`, ou clique
  em **Importar tabela** na área de Admin.
- **Via API (opcional, modelo misto):** veja [`scripts/import_fixtures.py`](scripts/import_fixtures.py)
  para puxar a tabela da football-data.org uma vez.
- **Sincronização automática (Admin):** com `FOOTBALL_DATA_TOKEN` configurado, o botão
  **Admin → Sincronizar da API** preenche os confrontos do mata-mata assim que ficam
  definidos (quartas, semi, final) **e** puxa os placares finalizados, recalculando os
  pontos. Confrontos preenchidos à mão no Admin nunca são sobrescritos.

Formato de cada jogo em `fixtures.json`:

```json
{
  "stage": "grupos",          // grupos|16avos|oitavas|quartas|semi|final
  "round": 3,                  // 1-3 nos grupos; null no mata-mata
  "home_team": "Brasil",
  "away_team": "Camarões",
  "teams_decided": true,       // false = mata-mata ainda sem times (palpite fechado)
  "is_brazil": true,           // ativa as perguntas Neymar/Endrick
  "kickoff_at": "2026-06-23T22:00:00+00:00",  // horário UTC
  "bracket_pos": 3             // posição na chave (oitavas 1-8 ... final 1); null fora do mata-mata
}
```

## Sugestões e melhorias

Tem uma ideia ou encontrou algum problema? Abre uma issue no repositório:

👉 **[github.com/marinabpassos/projeto_bolao/issues](https://github.com/marinabpassos/projeto_bolao/issues)**

**Como abrir uma issue:**
1. Clique em **"New issue"**
2. Escolha um título descritivo (ex: "Adicionar placar ao vivo" ou "Bug: palpite não salva")
3. Descreva a sugestão ou o problema com o máximo de detalhe que puder
4. Clique em **"Submit new issue"**

Pull requests também são bem-vindos! Fork o projeto, faça suas alterações e abra um PR.

## Administração

Quem estiver em `ADMIN_EMAILS` vê o menu **Admin** para: importar jogos, definir os
times dos confrontos do mata-mata, lançar resultados (e se Neymar/Endrick entraram)
e definir os gabaritos finais (artilheiro e até onde o Brasil foi). Lançar resultado
ou gabarito **recalcula a pontuação** automaticamente.

> **Migração (bancos criados antes do chaveamento):** rode
> `alter table matches add column if not exists bracket_pos int;` no SQL Editor
> do Supabase e clique em **Admin → Sincronizar fixtures** para preencher as
> posições da chave nos jogos existentes.
