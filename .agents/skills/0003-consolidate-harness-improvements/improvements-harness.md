# Melhorias de Harness — Ranking Acumulado

_Última atualização: 2026-07-24. Rodadas processadas: loop-2-2026-07-24._

_5 melhorias (24 menções) já foram aplicadas ao harness pela skill `0004-apply-harness-improvements` e removidas deste ranking — ver `../0004-apply-harness-improvements/implementations.md`._

## Melhorias

### 1. Verificação em escada / evitar suíte duplicada
- **Problema:** Testes focados + suíte completa + re-execução pós-lint, e os hooks de commit rodam pytest de novo — validação duplicada e lenta.
- **Solução:** Após mudança final pequena, rodar só testes/lint impactados; deixar a suíte completa para hooks/CI; rodar suíte completa de novo só se a mudança tocar lógica central ou o usuário exigir.
- **Economia estimada:** ~500–3k tokens + tempo de execução.
- **Fontes:** loop-2/GUI-267.md, loop-2/GUI-302.md, loop-2/GUI-323.md

### 2. Commit-merge determinístico e seguro
- **Problema:** A skill recomenda `git add .` e `git commit -am`, redundante/incorreto para arquivos novos e perigoso em worktree sujo.
- **Solução:** Fluxo explícito: `git status --short`; stage explícito dos arquivos alterados pela task; `git commit -m`; nunca `git add .` em repo possivelmente sujo; tratar claramente o caso "sem mudanças".
- **Economia estimada:** ~500k–1k tokens (menos checagens defensivas).
- **Fontes:** loop-2/GUI-268.md, loop-2/GUI-323.md

### 3. Precheck de bloqueio de merge no worktree master
- **Problema:** A skill só descobre que o worktree master está sujo (ou que há interseção de arquivos) depois de commitar, quando o bloqueio do merge era previsível antes.
- **Solução:** Antes do merge, checar `git status --short` do worktree master e comparar `git diff --name-only master...HEAD` com o target; se houver interseção/sujeira, parar/perguntar antes de commitar.
- **Economia estimada:** ~1k–2k tokens + 4–6 chamadas.
- **Fontes:** loop-2/GUI-302.md, loop-2/GUI-323.md

### 4. Atalhos fixos de comandos do repo (test/lint)
- **Problema:** O agente lê o README inteiro para descobrir comandos de teste/lint que já são padrão do workspace.
- **Solução:** Atalho fixo no harness para este repo (`uv run rtk pytest [<path>]`, `uv run rtk ruff check <paths>`) e/ou macro `verify_changed_python` (ruff+mypy+testes relevantes em saída compacta).
- **Economia estimada:** ~800–4k tokens.
- **Fontes:** loop-2/GUI-274.md, loop-2/GUI-304.md

### 5. Subagent de análise de impacto pré-task
- **Problema:** O agente principal gasta muitos tokens lendo arquivos só para confirmar que não usam um símbolo, ou para mapear caminhos protegidos vs desprotegidos manualmente.
- **Solução:** Subagent leve que recebe um símbolo/import a remover (ou um alvo) e retorna só: callers (grep), arquivos que precisam de rollback guard, fixtures dependentes — nada mais. Ex.: `rg` de handlers `except IntegrityError` para reportar "Protegidos: X,Y / Desprotegidos: A,B".
- **Economia estimada:** ~13k tokens (de ~15k manual para <2k).
- **Fontes:** loop-2/GUI-Others.md (×2: impact-analysis, impact-scan)

### 6. Linear auto-contexto (resumo injetado)
- **Problema:** Para ler o ticket exige carregar skill e rodar `orca status`, consumindo tokens com instruções longas e JSON grande.
- **Solução:** Para worktrees linkados, injetar automaticamente um resumo curto do issue: título, descrição, estado, branch e labels.
- **Economia estimada:** ~2k–4k tokens.
- **Fontes:** loop-2/GUI-267.md

### 7. Lint antes do commit
- **Problema:** O commit falha por regra do ruff (ex.: SLF001), gerando novo ciclo de patch/stage/commit.
- **Solução:** Em tasks com testes novos que acessam helpers privados, rodar `uv run ruff check <arquivos alterados>` antes do commit.
- **Economia estimada:** ~1k tokens + 2–3 chamadas.
- **Fontes:** loop-2/GUI-302.md

### 8. RTK só para saídas volumosas
- **Problema:** `rtk git ...` adiciona uma camada e regras extras sem benefício em comandos de saída curta como `status --short`.
- **Solução:** Usar RTK só para comandos potencialmente volumosos (diff, log grande, grep); para `status --porcelain`, `merge-base`, `branch`, usar `git` direto.
- **Economia estimada:** ~5–10% dos tokens da task.
- **Fontes:** loop-2/GUI-268.md

### 9. Resumir git worktree list automaticamente
- **Problema:** `git worktree list` retorna dezenas de worktrees, ocupando muito contexto, quando só importa onde está o master.
- **Solução:** Instruir RTK/harness a resumir para "current worktree + master worktree + branch alvo", omitindo os demais salvo conflito.
- **Economia estimada:** ~1k–2k tokens.
- **Fontes:** loop-2/GUI-304.md

### 10. Resposta compacta para no-op
- **Problema:** Mesmo em no-op há espaço para explicação redundante.
- **Solução:** Template fixo: "Sem mudanças pendentes; master já contém HEAD. Nenhuma ação feita."
- **Economia estimada:** ~3–8% dos tokens.
- **Fontes:** loop-2/GUI-268.md

### 11. Template obrigatório de ticket (arquivos afetados / done)
- **Problema:** Tickets ambíguos ("generic HTMX CRUD routes") escondem o gap real; falta de campos padronizados aumenta a exploração.
- **Solução:** Template obrigatório no `send-to-linear` com "Arquivos afetados", "Teste que reproduz o bug" e "Critérios de aceitação".
- **Economia estimada:** reduz ambiguidade e exploração inicial.
- **Fontes:** loop-2/GUI-Others.md

### 12. Watchdog de re-leitura/re-grep
- **Problema:** O agente relê o mesmo arquivo 2+ vezes e repete greds idênticos, gastando ~30% em re-análise.
- **Solução:** Se o agente lê o mesmo arquivo (mesmo offset/limit) ou roda o mesmo `rg` 2+ vezes, pausar e perguntar "já analisei isto; continuar ou refinar?".
- **Economia estimada:** ~30% dos tokens de re-análise.
- **Fontes:** loop-2/GUI-Others.md

### 13. Skill test-impact (diff → testes afetados)
- **Problema:** Descobrir quais testes dependem de um comportamento alterado é feito manualmente (ou com subagent) e ainda deixa arquivos escaparem.
- **Solução:** Skill `test-impact` que, dado um diff, escaneia e lista todos os testes afetados pelas funções/símbolos alterados.
- **Economia estimada:** evita subagent manual + reduz regressões perdidas.
- **Fontes:** loop-2/GUI-Others.md

### 14. Hook pytest "0 falhas = sucesso"
- **Problema:** O RTK filtra o output do pytest para mostrar só falhas; output vazio = sucesso, mas isso não é óbvio, gerando chamadas redundantes de confirmação.
- **Solução:** Hook que intercepta o retorno vazio de `rtk pytest` e emite inline "All tests passed (N passed, 0 failed)".
- **Economia estimada:** evita ~3 chamadas redundantes por task.
- **Fontes:** loop-2/GUI-Others.md

### 15. Agente enxuto para bug fixes triviais
- **Problema:** O thinking loop gasta ~8k tokens avaliando alternativas ("remover X ou Y?") quando o ticket já diz qual é o problema (ex.: dead code / unreachable branch).
- **Solução:** Subagent especializado que recebe `{file}:{line}` e produz o diff sem deliberar sobre alternativas (~1k tokens).
- **Economia estimada:** ~7k tokens por bug-fix trivial.
- **Fontes:** loop-2/GUI-Others.md

## Ranking por menções

| #  | Melhoria                                             | Menções | Rodadas |
|----|------------------------------------------------------|---------|---------|
| 1  | Verificação em escada / evitar suíte duplicada       | 3       | loop-2  |
| 2  | Commit-merge determinístico e seguro                 | 2       | loop-2  |
| 3  | Precheck de bloqueio de merge no worktree master     | 2       | loop-2  |
| 4  | Atalhos fixos de comandos do repo (test/lint)        | 2       | loop-2  |
| 5  | Subagent de análise de impacto pré-task              | 2       | loop-2  |
| 6  | Linear auto-contexto (resumo injetado)               | 1       | loop-2  |
| 7  | Lint antes do commit                                | 1       | loop-2  |
| 8  | RTK só para saídas volumosas                        | 1       | loop-2  |
| 9  | Resumir git worktree list automaticamente            | 1       | loop-2  |
| 10 | Resposta compacta para no-op                        | 1       | loop-2  |
| 11 | Template obrigatório de ticket                       | 1       | loop-2  |
| 12 | Watchdog de re-leitura/re-grep                       | 1       | loop-2  |
| 13 | Skill test-impact (diff → testes afetados)           | 1       | loop-2  |
| 14 | Hook pytest "0 falhas = sucesso"                     | 1       | loop-2  |
| 15 | Agente enxuto para bug fixes triviais                | 1       | loop-2  |

_Total: 21 menções → 15 melhorias no ranking. 5 melhorias (24 menções) já aplicadas — ver `../0004-apply-harness-improvements/implementations.md`._
