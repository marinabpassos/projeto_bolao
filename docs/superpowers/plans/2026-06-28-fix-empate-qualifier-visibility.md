# Fix: Visibilidade do Qualifier "Em caso de empate" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exibir a seção "Em caso de empate, quem avança?" somente quando o usuário digitar um placar empatado nos jogos de mata-mata.

**Architecture:** Fix puramente no frontend (Jinja2 template + JavaScript vanilla). Adiciona lógica de show/hide em cada formulário de mata-mata baseada nos valores dos inputs de placar. O backend já trata `qualifier_pred` ausente graciosamente (salva `None`), então não precisa de mudança no servidor.

**Tech Stack:** Jinja2 template, JavaScript vanilla (sem dependências), FastAPI/Python backend (inalterado).

## Global Constraints

- Não adicionar dependências externas (JS ou Python)
- Não modificar backend — o scoring já ignora `qualifier_pred` quando o palpite não é empate
- Manter comportamento existente: se já há um palpite salvo em empate, mostrar a seção pré-preenchida ao carregar a página
- Manter o atributo `required` nos radios apenas quando a seção está visível (para forçar o usuário a escolher quando digitar empate)

---

### Task 1: Criar branch e implementar o fix no template

**Files:**
- Modify: `app/templates/jogos.html:60-76`

**Interfaces:**
- Produces: Formulários de mata-mata que mostram/escondem o bloco de qualifier dinamicamente

- [ ] **Step 1: Criar a branch de fix**

```bash
git checkout -b fix/qualifier-visibility
```

Expected: Branch criada e ativa.

- [ ] **Step 2: Entender o estado atual do bloco a ser modificado**

Linhas 60-76 de `app/templates/jogos.html`:

```html
{% if m.stage != 'grupos' %}
<div class="w-full mt-2">
  <p class="text-xs text-slate-400 mb-1.5 text-center">Em caso de empate, quem avança? <span class="font-medium text-brand-green">+5 pts</span></p>
  <div class="flex justify-center gap-6 text-sm">
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="home" required
             {{ 'checked' if pred and pred.qualifier_pred == 'home' }}>
      <span class="text-slate-700">{{ m.home_team }}</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="away" required
             {{ 'checked' if pred and pred.qualifier_pred == 'away' }}>
      <span class="text-slate-700">{{ m.away_team }}</span>
    </label>
  </div>
</div>
{% endif %}
```

- [ ] **Step 3: Aplicar o fix — adicionar data attributes e JavaScript**

Substituir o bloco acima (linhas 60-76) por:

```html
{% if m.stage != 'grupos' %}
<div id="qualifier-{{ m.id }}"
     class="w-full mt-2"
     {% set already_tied = pred and pred.home_pred == pred.away_pred and pred.qualifier_pred %}
     style="{{ '' if already_tied else 'display:none' }}">
  <p class="text-xs text-slate-400 mb-1.5 text-center">Em caso de empate, quem avança? <span class="font-medium text-brand-green">+5 pts</span></p>
  <div class="flex justify-center gap-6 text-sm">
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="home"
             {{ 'checked' if pred and pred.qualifier_pred == 'home' }}
             {{ 'required' if already_tied }}>
      <span class="text-slate-700">{{ m.home_team }}</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input type="radio" name="qualifier_pred" value="away"
             {{ 'checked' if pred and pred.qualifier_pred == 'away' }}
             {{ 'required' if already_tied }}>
      <span class="text-slate-700">{{ m.away_team }}</span>
    </label>
  </div>
</div>
<script>
(function() {
  var form   = document.currentScript.closest('form');
  var div    = document.getElementById('qualifier-{{ m.id }}');
  var homeIn = form.querySelector('[name="home_pred"]');
  var awayIn = form.querySelector('[name="away_pred"]');
  var radios = div.querySelectorAll('input[type="radio"]');

  function update() {
    var h = homeIn.value.trim();
    var a = awayIn.value.trim();
    var isTie = h !== '' && a !== '' && h === a;
    div.style.display = isTie ? '' : 'none';
    radios.forEach(function(r) {
      r.disabled = !isTie;
      r.required = isTie;
      if (!isTie) r.checked = false;
    });
  }

  homeIn.addEventListener('input', update);
  awayIn.addEventListener('input', update);
  update();
})();
</script>
{% endif %}
```

**Por que `disabled` e não apenas `display:none`:** Inputs `disabled` não são incluídos no submit do formulário, garantindo que `qualifier_pred` não seja enviado quando não é empate. O backend já trata a ausência do campo graciosamente, mas isso é mais correto semanticamente.

**Por que `document.currentScript.closest('form')`:** Cada jogo renderiza seu próprio `<form>` e `<script>`. Usar `currentScript` garante que cada script encontra os inputs do seu próprio formulário, sem IDs globais que colidiriam na página (há múltiplos formulários).

- [ ] **Step 4: Commit do fix**

```bash
git add app/templates/jogos.html
git commit -m "fix: exibir qualifier de empate apenas quando placar for empate"
```

---

### Task 2: Testar o fix manualmente

**Files:**
- Sem alterações — apenas verificação

- [ ] **Step 1: Subir o servidor local**

```bash
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000` e faça login.

- [ ] **Step 2: Verificar cenário 1 — placar não-empate**

1. Vá para um jogo de mata-mata aberto
2. Digite `2` no campo do time da casa e `1` no do visitante
3. **Esperado:** A seção "Em caso de empate, quem avança?" NÃO aparece

- [ ] **Step 3: Verificar cenário 2 — placar empatado**

1. No mesmo jogo, mude para `1` : `1`
2. **Esperado:** A seção "Em caso de empate, quem avança?" aparece com os dois times para escolher

- [ ] **Step 4: Verificar cenário 3 — voltar para não-empate**

1. Mude de `1:1` para `2:1`
2. **Esperado:** A seção some e os radios são desmarcados

- [ ] **Step 5: Verificar cenário 4 — palpite já salvo em empate**

1. Se houver um palpite salvo com `home_pred == away_pred` e `qualifier_pred` preenchido
2. Ao carregar a página, a seção deve aparecer já marcada com a escolha salva

- [ ] **Step 6: Verificar cenário 5 — submit sem escolher qualifier em empate**

1. Digite `1:1`, deixe o qualifier sem marcar, tente salvar
2. **Esperado:** O browser bloqueia o submit (validação HTML5 `required`)

- [ ] **Step 7: Verificar que jogos de grupos não foram afetados**

1. Vá para um jogo de fase de grupos
2. **Esperado:** Nenhuma seção de qualifier aparece (comportamento já existente)

---

### Task 3: Deploy

**Files:**
- Sem alterações adicionais

- [ ] **Step 1: Confirmar que está na branch certa e limpa**

```bash
git status
git log --oneline -3
```

Expected: Apenas o commit do fix, sem arquivos modificados não commitados.

- [ ] **Step 2: Push da branch**

```bash
git push -u origin fix/qualifier-visibility
```

- [ ] **Step 3: Fazer o deploy**

Use o skill `vercel:deploy` ou o comando:

```bash
vercel --prod
```

Ou se for via PR merge, abrir a PR e fazer merge na main antes do deploy.

- [ ] **Step 4: Verificar o deploy em produção**

Acesse a URL de produção e repita os cenários de teste do Task 2.
