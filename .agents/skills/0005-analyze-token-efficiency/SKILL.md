---
name: 0005-analyze-token-efficiency
description: Analisa o histórico de execução da última sessão do worker Opencode (tabela opencode.db) e cita 5 melhorias de harness que teriam obtido o MESMO resultado consumindo menos tokens, sem perder qualidade. Para cada melhoria: evidência do desperdício na sessão (tool calls, re-leituras, outputs grandes, cache_read inflado — com custo real em tokens), o alvo de harness a mudar, a economia estimada e o teste de "mesmo resultado". Use quando pedirem retrospectiva de eficiência de tokens do worker, "onde gastei token à toa", ou para alimentar o pipeline de melhoria contínua (skill 0003).
---

# Analyze Token Efficiency

Retrospectiva de **eficiência de tokens** da sessão que o **worker Opencode** acabou de rodar. A pergunta central é:

> **Quais melhorias no harness, se estivessem em vigor, teriam produzido exatamente o mesmo resultado consumindo menos tokens?**

O entregável são **exatamente 5 melhorias de harness**, cada uma ancorada em **evidência concreta da sessão** (o que foi lido/rodado, quantas vezes, o custo em tokens) e com um **teste de "mesmo resultado"** que justifica por que a qualidade **não** cairia. Sem esse teste, uma "melhoria" vira só corte de trabalho — proibido aqui.

Esta skill é o **gerador** do pipeline de melhoria contínua: os blocos que ela produz têm o formato que a skill **`0003-consolidate-harness-improvements`** consome (`Melhoria #N` / Problema / Solução / Economia estimada). Ela é o passo que **deixa as dicas em `.loop/loop-*/GUI-*.md`** ao fim de uma rodada de worktree, para depois entrarem no ranking acumulado.

> ## 🎯 O executor é o **Opencode**, não o Claude Code
> Esta skill roda **dentro do worker Opencode**, que resolve issues em worktrees (`.../workspaces/xtreme-system/GUI-NNN`). Portanto:
> - **A fonte do histórico é o banco do Opencode** (`~/.local/share/opencode/opencode.db`), **não** os `.jsonl` do Claude Code.
> - **As melhorias precisam beneficiar o Opencode.** Alvos válidos (ver skill `0004`): `AGENTS.md` (raiz, lido nativamente — preferencial), **skills** (`.agents/skills`/`.claude/skills`), **RTK** (`.claude/RTK.md`, vale no Opencode), **plugins do Opencode** (`.opencode/plugins/*.js` + `opencode.json`, alto risco), **`PROMPT_TEMPLATE`** em `process_issue.py` (alto risco), e o uso de **graphify**.
> - **`CLAUDE.md` e hooks `.claude/settings.json` são só do Claude Code → inelegíveis.** Se uma melhoria só afetaria o Claude Code, não conte.

## Objetivo (o que é "done")

1. A **sessão-alvo** foi identificada no `opencode.db` — a sessão do worker que acabou de rodar (por `directory` = worktree atual).
2. Um **perfil de execução compacto** foi extraído via **SQL** (contagens, tamanhos, tokens reais) **sem despejar os outputs inteiros** no contexto.
3. Foram produzidas **exatamente 5 melhorias**, ordenadas por **economia estimada (desc)**, cada uma com: evidência + custo, alvo de harness do Opencode, economia estimada e **teste de mesmo-resultado**.
4. As 5 foram gravadas na pasta `.loop/loop-*/GUI-*.md` da rodada corrente no **formato compatível com a 0003** (e/ou em `docs/0005-analyze-token-efficiency/` se pedido).

## Como o custo de token funciona no Opencode (leia antes de estimar)

A tabela `session` tem colunas de token **reais** — use-as, não estime 4:1:
`tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`, `cost`.

**Insight-chave — o efeito multiplicador do cache_read.** O Opencode reenvia o contexto acumulado a cada passo; o que entrou cedo é **re-lido como cache em TODOS os passos seguintes**. Por isso `tokens_cache_read` costuma ser 10–100× o `tokens_input` (ex.: uma sessão real com ~9,8M de cache_read). Consequência para priorizar melhorias:

- Um **output grande lido cedo** (doc inteiro, `git diff` gigante, dump de comando) custa **muito mais** que o mesmo output no fim, porque é pago uma vez na escrita e depois re-lido N vezes.
- **Cortar contexto de entrada cedo tem economia multiplicativa.** Ranqueie melhorias que enxugam **o que entra no contexto nos primeiros passos** acima de microeconomias no fim.

## Fluxo

### 1. Localizar a sessão-alvo no `opencode.db`

Quem invoca esta skill é o plugin **`worktree-finish.js`** no evento `session.idle`, injetando um prompt na **própria sessão** do worker. Portanto a sessão-alvo é a **sessão corrente** — e o plugin já tem o `sessionID`.

- **Se o prompt de invocação trouxer um session id** (ex.: `SID=ses_...` injetado pelo plugin), **use-o direto** — é a fonte mais confiável.
- **Senão**, ache a sessão mais recente do **diretório worktree atual** (o cwd do worker):

```bash
DB=~/.local/share/opencode/opencode.db
CWD="$(pwd)"
sqlite3 -header "$DB" "SELECT id, title, agent, model,
  tokens_input, tokens_output, tokens_cache_read, tokens_cache_write, round(cost,4) cost
  FROM session WHERE directory = '$CWD' ORDER BY time_created DESC LIMIT 1;"
```

- Guarde `SID` = id da sessão para os passos seguintes.
- **Auto-alvo.** Esta skill roda **na mesma sessão que analisa**, e o commit-merge roda antes dela. **Só** exclua da análise os turnos **desta própria retrospectiva** (as queries/leituras que a `0005` faz agora) — analisá-los é circular e sem valor. **Tudo o mais entra**, inclusive os turnos da skill `commit-merge`: eles fazem parte do custo real de toda issue e são um **alvo de otimização válido** (ex.: mensagem/diff mais enxutos). Não os trate como intocáveis.

### 2. Extrair o perfil de execução (via SQL, sem despejar outputs)

A skill trata de economia — ela mesma **não pode** puxar `.state.output` inteiro para o contexto. Use `length()`, `COUNT`, `GROUP BY`. Receitas **validadas** contra o schema real (`part.data` é JSON; `.tool`, `.state.input`, `.state.output`, `.state.metadata`):

```bash
SID='ses_...'   # id do passo 1

# (a) Tokens da sessão já vêm da tabela session (passo 1). Complemento por mensagem:
sqlite3 "$DB" "SELECT COUNT(*) AS passos FROM message WHERE session_id='$SID' AND json_extract(data,'\$.role')='assistant';"

# (b) Contagem por ferramenta
sqlite3 "$DB" "SELECT json_extract(data,'\$.tool') tool, COUNT(*) n
  FROM part WHERE session_id='$SID' AND json_extract(data,'\$.type')='tool'
  GROUP BY tool ORDER BY n DESC;"

# (c) Arquivos lidos e REPETIÇÕES (re-leitura = desperdício)
sqlite3 "$DB" "SELECT json_extract(data,'\$.state.input.filePath') f, COUNT(*) n
  FROM part WHERE session_id='$SID' AND json_extract(data,'\$.tool')='read'
  GROUP BY f ORDER BY n DESC;"

# (d) Comandos bash (procure git diff cheio, ls -R, cat de arquivo grande, repetição)
sqlite3 "$DB" "SELECT json_extract(data,'\$.state.input.command') cmd
  FROM part WHERE session_id='$SID' AND json_extract(data,'\$.tool')='bash';"

# (e) MAIORES outputs de tool (chars) — onde o contexto encheu cedo. Ordene e veja só o tamanho.
sqlite3 "$DB" "SELECT json_extract(data,'\$.tool') tool,
  length(json_extract(data,'\$.state.output')) len,
  substr(json_extract(data,'\$.state.input'),1,60) inp
  FROM part WHERE session_id='$SID' AND json_extract(data,'\$.type')='tool'
  ORDER BY len DESC LIMIT 12;"

# (f) Outputs TRUNCADOS (pediu mais do que precisava)
sqlite3 "$DB" "SELECT json_extract(data,'\$.tool') tool, COUNT(*) n
  FROM part WHERE session_id='$SID'
    AND json_extract(data,'\$.state.metadata.truncated')=1 GROUP BY tool;"

# (g) grep/glob largos (varredura que poderia ser graphify/subagente)
sqlite3 "$DB" "SELECT json_extract(data,'\$.tool') tool, json_extract(data,'\$.state.input') inp
  FROM part WHERE session_id='$SID' AND json_extract(data,'\$.tool') IN ('grep','glob');"
```

Para converter chars→tokens em outputs (quando a coluna de sessão não isola aquele item), use **~4 chars ≈ 1 token** e **rotule como estimativa**. Os totais da sessão (passo 1) são exatos.

### 3. Diagnosticar os padrões de desperdício

Cruze o perfil com o **objetivo da issue** (o que a tarefa realmente exigia). Procure trabalho cujo **resultado não dependia** do custo pago. Catálogo:

- **Docs lidos sem gatilho** — `read` de `ARCHITECTURE.md`/`API.md`/`README` inteiros (recipe c/e) quando a issue não mudava contrato. Alvo clássico: regra em `AGENTS.md` "ler doc só se mudar contrato".
- **Re-leitura** — mesmo arquivo lido N vezes (recipe c), ou reler após editar só para "conferir".
- **Comando tagarela** — `git diff` completo onde `--stat`/`--name-only` bastava; `ls -R`, `cat` de arquivo enorme, log verboso (recipe d/e). Alvo típico: **RTK**.
- **Output grande cedo** — recipe (e) no topo + ocorrendo nos primeiros passos → custo multiplicado por cache_read (ver seção acima).
- **Varredura no worker principal** — `grep`/`glob` largos (recipe g) que poderiam ter ido para um **subagente** (`task`) que devolve só a conclusão, ou para **graphify query**.
- **Truncamento** — outputs truncados (recipe f): pediu volume, pagou pela leitura, e ainda perdeu informação.
- **Ida-e-volta evitável** — comando que falha por flag conhecida, refeito depois; uma regra/skill teria evitado.
- **Contexto refeito** — reconstruir do zero o que `graphify` ou o resumo da issue já dariam pronto.

Para cada candidato anote: **evidência** (recipe + número), **custo estimado em tokens** (lembrando o multiplicador de cache_read se foi cedo), e **qual canal do Opencode** o teria evitado.

### 4. Escrever exatamente 5 melhorias, com o teste de mesmo-resultado

Selecione as **5** de maior economia estimada. Cada uma **precisa** passar no teste:

> **Teste de mesmo-resultado:** se esta melhoria estivesse ativa na sessão-alvo, a entrega final (o código/PR da issue) teria sido **igualmente correta e completa**? Aponte por que o token cortado era **redundante** — informação duplicada, output não usado na solução, varredura jogada fora — e **não** informação de que a solução dependia.

Se uma ideia não passa nesse teste, ela **corta qualidade** — descarte e pegue a próxima. Cada melhoria deve mirar um **canal que o Opencode consome** (AGENTS.md/skill/RTK/graphify/subagente/plugin/PROMPT_TEMPLATE); se só afetaria o Claude Code, é inelegível. Ordene por economia estimada (desc).

### 5. Gravar (formato do pipeline `.loop`, consumido pela 0003)

⚠️ **`.loop` vive SÓ no checkout principal e é gitignored** (`~/orca/projects/xtreme-system/.loop`), **nunca dentro da worktree**. Como o worker roda numa worktree (`~/orca/workspaces/.../GUI-NNN`), gravar em `./.loop` criaria uma pasta isolada que **ninguém consome**. Grave por **caminho absoluto no checkout principal**:

```bash
# Raiz do checkout principal (a partir da worktree): pai do git-common-dir
MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
# Rodada .loop corrente = a mais recente (mesma regra da 0003)
LOOP="$(ls -d "$MAIN"/.loop/loop-* 2>/dev/null | sort | tail -1)"
# Issue a partir do nome da branch/worktree (ex.: GUI-156)
ISSUE="$(git rev-parse --abbrev-ref HEAD)"
# Alvo final:  $LOOP/GUI-$ISSUE.md   (não sobrescreva GUI-Others.md nem improvements.json)
```

- Grave os 5 blocos em `"$LOOP/GUI-$ISSUE.md"`, no formato que a **0003** lê (um arquivo por issue, como os `GUI-267.md` já existentes).
- Se não houver `.loop/loop-*` no checkout principal, caia para `"$MAIN"/docs/0005-analyze-token-efficiency/GUI-$ISSUE.md` e avise no resumo.

```markdown
# Retrospectiva de Eficiência de Tokens — <issue / prompt-alvo em uma linha>

_Sessão Opencode: <ses_id> · worktree: <dir> · modelo: <model> · Data: <data>_

## Perfil de execução (tokens reais da tabela session)
- input: <N> · output: <N> · cache_read: <N> · cache_write: <N> · custo: $<N>
- Passos (assistant): <N> · Ferramentas: <read xN, bash xN, grep xN, ...>
- Maiores outputs / re-leituras / truncamentos: <resumo das recipes c/e/f>

## As 5 melhorias (ordenadas por economia estimada)

### 1. <título curto e estável>
- **Padrão:** <doc sem gatilho | comando tagarela | output grande cedo | varredura no principal | ...>
- **Evidência:** <recipe + número — ex.: recipe (c): API.md lido inteiro (limit 2000) no passo 2>
- **Custo observado:** ~<N> tokens (<exato | estimado>; se foi cedo, some o efeito cache_read)
- **Alvo de harness (Opencode):** <AGENTS.md | skill X | .claude/RTK.md | graphify | subagente/task | plugin | PROMPT_TEMPLATE>
- **Solução:** <a regra/atalho/mudança concreta — nível "o que escrever/fazer">
- **Economia estimada:** ~<N> tokens
- **Teste de mesmo-resultado:** <por que a entrega continuaria correta e completa>

### 2. ... até ### 5.

## Total estimado economizado
~<N> tokens (~<%> do custo da sessão), sem mudança no resultado entregue.

---

## Blocos para o pipeline (formato 0003)

Melhoria #1: <título>
- Problema: <...>
- Solução: <alvo Opencode + mudança concreta>
- Economia estimada: ~<N> tokens

Melhoria #2: ...  (até #5)
```

### 6. Reportar (headless)

Esta skill roda **sem humano assistindo** (disparada no `session.idle`). O entregável é o **arquivo** do passo 5 — não um relatório de chat. Ao terminar, imprima **uma linha** de confirmação: sessão-alvo, custo real (input/output/cache_read), caminho gravado e os 5 títulos com a economia estimada. Nada de narração longa (ela mesma custaria tokens). A **0003** consolida esses blocos no ranking; a **0004** os aplica.

## Guardrails

- **Alvo é o Opencode.** Só contam melhorias em canais que o worker Opencode lê/usa (AGENTS.md, skills, RTK, graphify, subagentes, plugins do Opencode, PROMPT_TEMPLATE). `CLAUDE.md` e `.claude/settings.json` são **inelegíveis** (só Claude Code).
- **Sempre 5, sempre com teste de mesmo-resultado.** Uma "melhoria" que reduz o escopo da entrega **não** vale. Se não houver 5 que passem no teste, diga isso e liste quantas passaram — não invente para completar 5.
- **A skill não pode ser gastadora.** Nunca puxe `.state.output` inteiro para o contexto; use `length()`/`COUNT`/`GROUP BY`. Em sessão enorme, rode a extração e traga só o perfil agregado.
- **Tokens reais primeiro.** Use as colunas da tabela `session`/`message`; só estime (4:1) quando precisar isolar o custo de um item, e rotule como estimativa.
- **Evidência real, não hipótese.** Toda melhoria cita recipe + número da sessão. Sem evidência no histórico → fora.
- **Analysis-only para o app.** A skill grava **relatório/blocos de harness**; **nunca** edita código de `xtreme-system` (bases/, components/, etc.).
- **Auto-alvo.** Ao escolher a sessão, garanta que é a da issue resolvida, não a da própria análise.
