# Página de Jogos: fase atual + chaveamento do mata-mata

**Data:** 2026-07-04
**Status:** aprovado (brainstorming com mockups visuais)

## Problema

Com o torneio nas oitavas, a página `/jogos` é uma lista corrida de todas as
fases: o usuário rola muito até achar os jogos atuais. Além disso, o mata-mata
pede uma experiência mais rica — um chaveamento com bandeiras — sem perder o
acesso ao histórico das fases passadas. Uso é quase 100% no celular.

## Decisões de produto (validadas em mockup)

1. **A página abre na fase vigente** — sem rolagem até a fase atual.
2. **Mata-mata como árvore vertical** (opção escolhida entre scroll horizontal,
   abas por fase e árvore vertical): pares de jogos com linhas convergindo para
   o slot da fase seguinte, um lado da chave por vez.
3. **Mini-chave resumida no topo, sempre visível**: o torneio inteiro
   (oitavas → final) em bandeirinhas minúsculas, lado A à esquerda, 🏆 no
   centro, lado B à direita. Fase atual destacada em verde. Tocar numa fase
   navega até ela.
4. **Abas "Lado A | Lado B" com sublinhado** (estilo escolhido entre pill iOS e
   setas no título): texto simples, traço verde de 2px sob o lado ativo.
5. **Fases anteriores recolhidas**: chip discreto
   "Fases anteriores: Grupos · 16avos — ver ▸" que expande a lista clássica de
   cards. Conforme o torneio avança, cada fase de mata-mata concluída sai do
   detalhe e fica só na mini-chave + chip, até que semi + final caibam em uma
   tela sem rolagem.
6. **Tocar num jogo expande o card de palpite no lugar (acordeão)** — o
   formulário atual (placar + "em caso de empate, quem avança") permanece
   intacto, apenas muda onde aparece. Tocar de novo recolhe.
7. **Bandeiras como imagens** (flagcdn.com), não emoji — emoji de bandeira não
   renderiza no Windows. Time indefinido ("A definir") usa placeholder cinza.
8. **Escopo do bracket: oitavas → final** (15 jogos). Os 16avos e grupos
   permanecem como histórico em lista de cards (com bandeiras adicionadas).

## Arquitetura

Segue o padrão do projeto: FastAPI + Jinja2 server-rendered, Tailwind via CDN,
JS vanilla mínimo embutido no template. Nenhuma dependência nova.

### Dados

- **Nova coluna `matches.bracket_pos`** (`Integer`, nullable): posição na chave
  dentro da fase — oitavas 1–8, quartas 1–4, semi 1–2, final 1.
  - Regra da árvore: vencedores das oitavas `2k-1` e `2k` alimentam a
    quartas `k`; idem nas fases seguintes.
  - Lado A = primeira metade das posições da fase; Lado B = segunda metade.
    (Final não tem lado.)
  - Migração: `ALTER TABLE matches ADD COLUMN bracket_pos INTEGER` no
    `schema.sql` (Supabase roda manualmente; SQLite local recriado pelo seed).
  - Origem do valor: novo campo `bracket_pos` em `app/data/fixtures.json` nos
    jogos de oitavas em diante, aplicado pelo seed/importação. A ordem segue o
    chaveamento oficial da FIFA 2026.
  - O sync de resultados (football-data.org) **não escreve** `bracket_pos`:
    nunca sobrescreve/apaga valor existente.

- **Novo módulo `app/flags.py`**: dicionário `nome do time em PT → código ISO`
  (as 48 seleções da Copa, ex.: `"Brasil" → "br"`, `"Inglaterra" → "gb-eng"`) e
  helper `flag_url(team, width=40)` → `https://flagcdn.com/w40/br.png`.
  Nome fora do dicionário retorna `None` e o template mostra placeholder.
  Exposto ao Jinja como filtro/global em `templating.py`.

### Backend (rota `/jogos` em `app/routers/pages.py`)

Novos valores de contexto:

- `current_stage`: primeira fase (na ordem de `MATCH_STAGES`) com algum jogo
  não-encerrado; se todos encerrados, `final`. Query param `?fase=<stage>`
  sobrepõe (validado contra `MATCH_STAGES`; valor inválido → `current_stage`).
- `bracket`: estrutura derivada dos jogos de oitavas → final ordenados por
  `bracket_pos` — por fase, jogos divididos em lado A/B, cada posição com o
  jogo (ou slot "A definir" quando `teams_decided=False` ou sem jogo cadastrado).
- `past_stages`: fases anteriores a `current_stage` que têm jogos (para o chip).

Rotas de palpite (`/palpite/{id}` etc.) não mudam.

### Template e interação

- `jogos.html` passa a ter dois modos por fase:
  - **Fases de lista** (grupos, 16avos, e qualquer fase aberta pelo chip):
    cards atuais + bandeiras ao lado dos nomes.
  - **Fase vigente de mata-mata** (oitavas em diante): novo partial
    `_bracket.html` com mini-chave, chip de fases anteriores, abas de lado e
    árvore vertical.
- O que a árvore detalha: os pares da **fase vigente** do lado selecionado,
  cada par com linha convergindo ao slot da fase seguinte. Fases futuras além
  da seguinte aparecem como linhas compactas ("SF1 · A definir — 14/jul",
  "🏆 FINAL · A definir — 19/jul"). Fases de mata-mata já concluídas não
  aparecem no detalhe — ficam na mini-chave e no chip de fases anteriores.
- JS vanilla (bloco único no template, sem fetch):
  - alternar Lado A/B — os dois lados já vêm renderizados; JS só troca
    `hidden`;
  - acordeão do card de palpite;
  - expandir/recolher fases anteriores (conteúdo já renderizado, `hidden`).
- Sem JS a página degrada: os dois lados aparecem empilhados e os cards
  abertos; formulários continuam POST normais.
- A mini-chave usa `flagcdn.com/w20`; a árvore usa `w40`. Ambos com
  `loading="lazy"`.

## Casos de borda

| Situação | Comportamento |
|---|---|
| Jogos de mata-mata sem `bracket_pos` (dado antigo) | Fase cai na lista clássica de cards; nunca quebra. |
| Time sem entrada no dicionário de bandeiras | Placeholder cinza + nome do time. |
| Jogo com `teams_decided=False` | Slot tracejado "A definir", sem acordeão de palpite. |
| `?fase=` inválido | Ignora e usa `current_stage`. |
| Sync de fixtures | Preserva `bracket_pos` existente. |
| flagcdn fora do ar | `<img>` com `alt` = nome do time; layout não depende da imagem carregar. |

## Testes

- `tests/test_bracket.py` (novo):
  - derivação da árvore: quem alimenta quem, divisão lado A/B por fase;
  - `current_stage`: oitavas em andamento, tudo encerrado (→ `final`),
    sem jogos, `?fase=` válido e inválido;
  - fallback para lista quando falta `bracket_pos`.
- `tests/test_flags.py` (novo): todas as 48 seleções resolvem para URL; nome
  desconhecido → `None`.
- Pontuação (`scoring.py`) não é tocada; testes existentes permanecem como
  regressão.

## Fora de escopo (próximos ciclos)

- Ranking lúdico estilo "corrida" com histórico de ultrapassagens (exige
  armazenar evolução de pontos no tempo — projeto separado).
- Palpitar direto dentro da árvore (decidido: palpite fica no card expandido).
- Bracket dos 16avos (fica no histórico em lista).
