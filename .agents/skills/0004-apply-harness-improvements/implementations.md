# Implementações de Melhorias de Harness

Registro do que a skill `0004-apply-harness-improvements` aplicou de fato ao harness do worker Opencode. Cada bloco corresponde a uma melhoria que saiu do ranking em `improvements-harness.md`.

---

### Leitura mínima e sob demanda de docs/arquivos — 2026-07-24
- **Faixa de risco:** baixo
- **Arquivos alterados:** `AGENTS.md`
- **O que mudou:** Novo bloco "Minimal, on-demand reading" na seção "Agent-Readable Workspace Map" (logo após "Shortcuts by intent:"): grep/graphify primeiro e abrir só os arquivos citados pela issue; ler os 4 docs (README/ARCHITECTURE/API/DATABASE) só quando a mudança for ambígua quanto a contrato/arquitetura/auth/schema — bug fix com `file:line` não dispara; ao ter `file:line`, ler `line-30..line+30` em uma única chamada.
- **Como verificar:** `git diff AGENTS.md` mostra as 6 linhas adicionadas entre "Shortcuts by intent:" e "## 1. Think Before Coding". O Opencode lê `AGENTS.md` nativamente.
- **Como reverter:** remover o bloco "Minimal, on-demand reading" do `AGENTS.md`.
- **Origem:** improvements-harness.md #1 (6 menções)
- **Nota de processo:** um subagent aplicou esta melhoria e, indevidamente, chegou a commitá-la em `master` (`bf26ddd`); o commit foi desfeito com `git reset HEAD~1` (recuperável via reflog), deixando a mudança apenas no working tree.

### Diff enxuto por padrão — 2026-07-24
- **Faixa de risco:** baixo
- **Arquivos alterados:** `AGENTS.md`
- **O que mudou:** Nova seção "## 4. Lean Diff by Default" (entre Surgical Changes e Goal-Driven Execution): inspecionar com `git diff --stat` + `--name-only` por padrão; ler diff completo no máximo uma vez (antes de commit sensível ou em dúvida real); pular `diff`/`log` quando `git status` está limpo. Seções seguintes renumeradas para manter 1–7 contíguo.
- **Como verificar:** `grep -n "^## " AGENTS.md` mostra 1..7 sem gaps, com "## 4. Lean Diff by Default".
- **Como reverter:** remover a seção "## 4. Lean Diff by Default" e restaurar a numeração anterior (Goal-Driven→4, RTK→6→..., como estava).
- **Origem:** improvements-harness.md #2 (5 menções)

### Modo comando direto / verbosidade adequada do Linear — 2026-07-24
- **Faixa de risco:** baixo
- **Arquivos alterados:** `AGENTS.md`
- **O que mudou:** Nova seção "## 8. Direct Commands & Linear Verbosity" no fim: se o usuário der um comando exato (ex.: `orca linear issue GUI-XXX --full`), executá-lo exatamente e pular `orca status`/discovery e carregamento de skill (exceto se mutar o Linear); leituras não especificadas default `--json`, `--full` só quando comentários/anexos forem necessários.
- **Como verificar:** `grep -n "^## 8" AGENTS.md` mostra a seção no fim do arquivo.
- **Como reverter:** remover a seção "## 8. Direct Commands & Linear Verbosity".
- **Origem:** improvements-harness.md #3 (5 menções)

### Reduzir comentários/updates intermediários — 2026-07-24
- **Faixa de risco:** baixo
- **Arquivos alterados:** `AGENTS.md`
- **O que mudou:** Nova seção "## 9. Fewer Intermediate Updates" no fim: silent-unless-blocked para tasks pequenas/médias; limitar a 2–4 updates (início/critério, antes de edição substancial, ao bloquear, verificação final); não emitir update para passos de leitura/teste/status não bloqueantes.
- **Como verificar:** `grep -n "^## 9" AGENTS.md` mostra a seção no fim.
- **Como reverter:** remover a seção "## 9. Fewer Intermediate Updates".
- **Origem:** improvements-harness.md #5 (4 menções)

### Commit-merge enxuto / fast path — 2026-07-24
- **Faixa de risco:** médio
- **Arquivos alterados:** `.agents/skills/commit-merge/SKILL.md`
- **O que mudou:** Nova seção "## Fast path (check first)" no topo do fluxo (após a intro, antes de "## Triggers"): rodar `git status --porcelain --branch` primeiro; se nada a commitar E `git merge-base --is-ancestor HEAD master` for verdadeiro → no-op, responder compacto e parar sem `git worktree list`/diff/log; só cair no fluxo completo quando houver mudança real.
- **Como verificar:** o `SKILL.md` de `commit-merge` tem a seção "## Fast path (check first)" antes de "## Triggers"; seções Triggers/Flow intactas.
- **Como reverter:** remover a seção "## Fast path (check first)" do `commit-merge/SKILL.md`.
- **Origem:** improvements-harness.md #4 (4 menções)
