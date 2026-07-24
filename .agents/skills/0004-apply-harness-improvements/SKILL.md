---
name: 0004-apply-harness-improvements
description: Pega o ranking acumulado de melhorias de harness (improvements-harness.md, mantido pela skill 0003), seleciona as mais mencionadas (mais de 3 menções), reescreve/aprimora a proposta de solução de cada uma, e então aplica ao harness — uma de cada vez, via subagent, com revisão do trabalho do agente — começando pelas de menor risco de quebrar o sistema. Registra o que foi implementado em implementations.md (nesta pasta) e remove do ranking as melhorias já aplicadas. Use quando pedirem para "aplicar as melhorias de harness", "implementar o ranking", "colocar em prática as dicas consolidadas" ou fechar o ciclo iniciado pela 0003.
---

# Apply Harness Improvements

Fecha o ciclo de melhoria contínua do harness. A skill **0003** consolida as dicas das rodadas de worktree em um ranking (`improvements-harness.md`). Esta skill **pega o topo desse ranking e coloca em prática**: refina a proposta, aplica no harness com o menor risco possível, revisa e registra.

Complementar à 0003 (que só ranqueia). Esta **muda o harness de verdade** — logo, é conservadora: aditiva por padrão, uma melhoria por vez, cada aplicação isolada em um subagent e revisada antes de seguir.

> ## 🎯 IMPORTANTE — o harness executor é o **Opencode**
>
> As issues são resolvidas por um worker **`opencode`** (subido pela skill `0002-linear-sequential-worktree` em modo TUI — `opencode --model … --auto`). **As melhorias precisam beneficiar o Opencode.** Ele é configurado por **`opencode.json`** (na raiz do repo).
>
> **Canais que o worker Opencode consome (todos alvos válidos):**
> 1. **`AGENTS.md`** (raiz) — lido **nativamente** pelo Opencode. **Alvo preferencial e de menor risco.**
> 2. **Skills** em `.agents/skills` e `.claude/skills` — o Opencode lê **todas** (declarado em `opencode.json` → `"skills": { "paths": [...] }`). Algumas são feitas para o fluxo do Opencode, ex.: **`commit-merge`** e **`code-review-simple`**. Editar/criar skill é alvo válido.
> 3. **RTK** (`.claude/RTK.md`) — a reescrita de comandos **também vale no Opencode**. Ajustar regras é alvo válido.
> 4. **Plugins (hooks do Opencode)** — mecanismo **próprio**, diferente do Claude Code: arquivos **JS em `.opencode/plugins/*.js`**, registrados no array `"plugin"` do **`opencode.json`** (ex.: `post-edit-checks.js`, `worktree-finish.js`). É **código que roda automaticamente** → alto risco.
> 5. **`PROMPT_TEMPLATE`** em `process_issue.py` (linha ~271) — o prompt curto injetado no worker por issue. É código → alto risco.
>
> **Atenção — Claude Code ≠ Opencode:** hooks do **Claude Code** ficam em `.claude/settings.json` e **NÃO** valem para o worker. Um hook para o Opencode é um **plugin JS em `.opencode/plugins` + entrada no `opencode.json`**. Se uma melhoria só afetaria o Claude Code, é **inelegível** (registre e pule).

## Escopo: o que é "o harness" aqui

As melhorias tocam a **infraestrutura de trabalho do worker Opencode**, nunca o código da aplicação `xtreme-system`. Alvos válidos, do menor para o maior risco (detalhes no aviso do topo):

1. **`AGENTS.md`** (raiz) — orientação lida nativamente. **Preferencial.**
2. **Skills** (`.agents/skills` / `.claude/skills`) — texto/comportamento de skill que o Opencode carrega (ex.: `commit-merge`, `code-review-simple`); ou skill nova.
3. **`.claude/RTK.md`** — regras de reescrita de comando (valem no Opencode).
4. **Plugins do Opencode** — JS em `.opencode/plugins/*.js` + registro no `opencode.json`. Alto risco (código automático).
5. **`PROMPT_TEMPLATE` / `process_issue.py`** — prompt injetado no worker. Alto risco (código).

**Inelegível:** hooks/`.claude/settings.json` e qualquer coisa que só afete o **Claude Code**, não o worker Opencode.

> ⚠️ **Nunca** editar código de produção do `xtreme-system` (bases/, components/, etc.). Se uma melhoria só puder ser realizada mexendo no app, ela **não** é elegível — registre como "requer mudança de código, fora do escopo" e pule.

## Localização dos arquivos

- **Ranking (entrada e saída):** `improvements-harness.md`. Ele vive na pasta da skill **0003** (`.agents/skills/0003-consolidate-harness-improvements/improvements-harness.md`), não na 0002. Localize com:
  `find .agents/skills -name improvements-harness.md`.
- **`.claude/skills/` é um symlink para `.agents/skills/`** — é a **mesma** pasta. Grave sempre em `.agents/skills/...`; a mudança aparece automaticamente sob `.claude/skills/...`. Não há cópia a sincronizar.
- **Registro de implementações (saída):** `implementations.md`, **nesta pasta de skill**.

## Objetivo (o que é "done")

1. Cada melhoria com **mais de 3 menções** teve sua **proposta de solução reescrita/aprimorada** (mais concreta e acionável) e regravada no `improvements-harness.md`.
2. Dessas, as elegíveis foram ordenadas por **risco crescente** e aplicadas **uma de cada vez, via subagent**, com o trabalho de cada subagent **revisado** antes de prosseguir.
3. Cada melhoria aplicada foi **registrada em `implementations.md`** (o que mudou, em quais arquivos, como revisar/reverter).
4. As melhorias aplicadas foram **removidas** do `improvements-harness.md` (entrada + linha da tabela de ranking; contagens/total ajustados).

## Fluxo

### 1. Selecionar as melhorias alvo

- Leia o `improvements-harness.md` e sua tabela "Ranking por menções".
- Selecione as melhorias com **menções > 3** (estritamente maior que 3, ou seja ≥ 4). Trate **3 exatas como fora** do alvo.
- Ordene por menções (desc); empate → ordem alfabética do título (mesma regra da tabela).
- Reporte ao usuário a lista selecionada (título + menções) antes de prosseguir.

### 2. Reescrever/aprimorar a proposta de solução

Para **cada** melhoria selecionada, reescreva o campo **Solução** para que seja acionável, não genérica. Uma boa proposta refinada tem:

- **Alvo concreto:** qual arquivo que o **Opencode consome** muda — normalmente `AGENTS.md`; excepcionalmente o `PROMPT_TEMPLATE` em `process_issue.py`.
- **Mudança exata:** o texto/regra/atalho a acrescentar, em nível de "o que escrever", não só a intenção.
- **Gatilho e limite:** quando o comportamento se aplica e quando **não** (ex.: "só para small clean change", "não para mudanças em lógica central").
- **Como verificar** que ficou correto.

Regrave o `improvements-harness.md` com as Soluções aprimoradas. **Não** mude os títulos canônicos, as contagens de menção, nem a tabela nesta etapa — só o texto da Solução (e, se útil, um subcampo `**Proposta refinada:**`).

### 3. Analisar risco e ordenar por menor risco

A faixa de risco sai quase direto do alvo (ver Escopo):

- **Baixo (aditivo/documental):** orientação em **`AGENTS.md`**; texto de uma skill sem mudar comportamento; criar skill nova **opcional**. Não altera automação.
- **Médio (comportamental):** mudar como uma skill existente age (ex.: fast path do `commit-merge`, `code-review-simple`); ajustar regras do **`.claude/RTK.md`**. Muda comportamento, mas de forma controlada e reversível.
- **Alto (automação/código):** **plugins do Opencode** (`.opencode/plugins/*.js` + `opencode.json`) e mudanças em **`process_issue.py`/`PROMPT_TEMPLATE`** — código que roda automaticamente e afeta todas as issues.

Regras de elegibilidade e ordem:
- Aplique **da menor para a maior faixa de risco**. Dentro da mesma faixa, maior nº de menções primeiro.
- **Alto risco:** por padrão **não aplicar automaticamente** — liste como "proposta pronta, aplicar sob confirmação" e **pergunte ao usuário** antes de tocar em plugins do Opencode (`.opencode/plugins` + `opencode.json`) ou `process_issue.py`.
- Melhorias que exigem mexer no código do app → **inelegíveis** (registre e pule).
- Melhorias que só afetariam o **Claude Code** (hooks em `.claude/settings.json`, comportamento do próprio Claude Code) e **não** o worker Opencode → **inelegíveis** (registre "não afeta o executor Opencode" e pule). Ver aviso no topo.

Reporte ao usuário o plano ordenado (melhoria → faixa de risco → elegível/adiada) antes de aplicar a primeira.

### 4. Aplicar uma de cada vez, via subagent + revisão

Para cada melhoria elegível, **em ordem**, faça um ciclo completo antes de passar para a próxima:

1. **Dispare um subagent** (Agent, `subagent_type: general-purpose`) para implementar **apenas aquela** melhoria. Use o template de prompt abaixo. Rode de forma **síncrona** (`run_in_background: false`) — o resultado é necessário antes de continuar.
2. **Revise o trabalho do subagent** (o agente principal faz isto, não confie cego no relatório):
   - `git status --short` / `git diff --stat`: só os arquivos esperados mudaram? Nenhum arquivo de app do `xtreme-system` foi tocado?
   - Leia o diff da mudança: ela corresponde à proposta refinada? Escopo contido?
   - **A mudança está num arquivo que o Opencode realmente consome?** (não em algo só-Claude-Code).
   - Se a melhoria mexe em skill/AGENTS.md → o Markdown está válido e coerente.
   - Nenhuma regressão óbvia introduzida.
3. **Se a revisão reprovar:** ou corrija pontualmente, ou reenvie ao subagent com o feedback específico (via SendMessage para o mesmo agente, preservando contexto). Não avance com trabalho reprovado.
4. **Se aprovar:** registre em `implementations.md` (passo 5) e só então vá para a próxima melhoria.

Nunca aplique duas melhorias em paralelo — uma por vez mantém a revisão rastreável e o blast radius pequeno.

#### Template de prompt do subagent

```
Implemente UMA melhoria de harness no repositório xtreme-system. Escopo estrito.

MELHORIA: <título canônico>
PROPOSTA REFINADA (siga à risca):
<colar a Solução aprimorada do passo 2>

CONTEXTO: O harness que executa as issues é o worker Opencode. A mudança precisa
melhorar o que o OPENCODE lê/usa (ex.: AGENTS.md, prompt injetado pela skill 0002,
config do Opencode). Não implemente nada que só afetaria o Claude Code.

ALVO: <arquivo(s) exatos que o Opencode consome: AGENTS.md, skill, RTK.md,
      plugin .opencode/plugins + opencode.json, ou process_issue.py>
FAIXA DE RISCO: <baixo|médio|alto>

REGRAS:
- Mude SOMENTE o(s) arquivo(s) do harness indicados. NÃO toque em código do app
  (bases/, components/, tests do app) nem em outras melhorias.
- Grave em .agents/skills/... (a pasta .claude/skills é symlink para essa — mesma pasta,
  nada a duplicar). AGENTS.md/config do Opencode têm arquivo único.
- Mantenha o estilo/idioma do arquivo existente.
- Se o repo tiver graphify-out/graph.json, oriente-se com `graphify query "<pergunta>"`
  antes de ler arquivos de código.
- NÃO commite nem faça merge. Só deixe as edições no working tree.

ENTREGUE: lista dos arquivos alterados e um resumo de 2-3 linhas do que mudou e como verificar.
```

### 5. Registrar e remover do ranking

Após **cada** melhoria aprovada:

- **Acrescente** um bloco em `implementations.md` (nesta pasta de skill). Se o arquivo não existir, crie com o cabeçalho abaixo. Formato por melhoria:

  ```markdown
  ### <Título canônico> — <data>
  - **Faixa de risco:** baixo | médio | alto
  - **Arquivos alterados:** <caminhos>
  - **O que mudou:** <resumo objetivo da mudança aplicada>
  - **Como verificar:** <comando/checagem>
  - **Como reverter:** <arquivo + trecho, ou "git revert do commit X">
  - **Origem:** improvements-harness.md #<posição> (<menções> menções)
  ```

- **Remova** a melhoria do `improvements-harness.md`:
  - apague a seção `### N. <título>` correspondente;
  - apague a linha da tabela "Ranking por menções";
  - **renumere** as entradas/linhas restantes e ajuste o rodapé "_Total: N menções ... → M melhorias únicas._";
  - atualize o `_Última atualização:_`.

Faça isso **incrementalmente** (por melhoria), para que uma interrupção no meio deixe o estado consistente: o que está em `implementations.md` já saiu do ranking.

### 6. Reportar

Ao terminar, informe ao usuário:
- melhorias selecionadas (>3 menções) e quantas tiveram a proposta refinada;
- plano de risco (o que foi aplicado, o que ficou adiado por ser alto risco/inelegível);
- para cada aplicada: título, arquivos, veredito da revisão;
- estado final do ranking (quantas restam) e link mental para `implementations.md`.

## Sobre os caminhos das skills

`.claude/skills` é um **symlink** para `.agents/skills` — a mesma pasta sob dois nomes. Sempre grave em `.agents/skills/...`; nada precisa ser duplicado ou sincronizado. `AGENTS.md`, `.claude/settings.json` e `.claude/RTK.md` também têm cópia única.

## Guardrails

- **Alvo é o Opencode.** O executor das issues é o worker Opencode; só melhorias que ele lê/usa contam: `AGENTS.md`, skills (`.agents/skills`/`.claude/skills`), RTK (`.claude/RTK.md`), plugins do Opencode (`.opencode/plugins`+`opencode.json`), `process_issue.py`. **Hooks do Claude Code (`.claude/settings.json`) NÃO valem** — no Opencode, hook = plugin JS.
- **Só harness, nunca app.** Uma melhoria que só se realiza mexendo em código do `xtreme-system` é inelegível.
- **Menor risco primeiro; alto risco só sob confirmação** do usuário (plugins do Opencode em `.opencode/plugins`/`opencode.json`, `process_issue.py`).
- **Uma melhoria por vez**, cada uma isolada em subagent e revisada antes da próxima.
- **Não commitar/mergear** por conta própria — deixe as edições no working tree e reporte; commit/merge é decisão do usuário (ou da skill `commit-merge`, se ele pedir).
- **Idempotência:** o que já está em `implementations.md` já saiu do ranking; reexecutar não deve reaplicar nem reprocessar melhorias já registradas.
