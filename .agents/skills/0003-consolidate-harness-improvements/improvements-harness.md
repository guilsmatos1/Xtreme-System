# Melhorias de Harness — Ranking Acumulado

_Última atualização: 2026-07-26. Fontes processadas: loop-2-2026-07-24, docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-109.md, docs/0005-analyze-token-efficiency/GUI-120.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-349.md, docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-361.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-363.md, docs/0005-analyze-token-efficiency/GUI-365.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-367.md, docs/0005-analyze-token-efficiency/GUI-368.md, docs/0005-analyze-token-efficiency/GUI-369.md._

_5 melhorias (24 menções) já foram aplicadas ao harness pela skill `0004-apply-harness-improvements` e removidas deste ranking — ver `../0004-apply-harness-improvements/implementations.md`._

## Melhorias

### 1. Limitar leitura de outputs grandes ao trecho necessário
- **Problema:** Greps, logs de teste e leituras de arquivos grandes entram inteiros no contexto quando a tarefa só precisa de uma janela pequena ou dos matches mais relevantes.
- **Solução:** Após localizar um alvo, ler `line-40..line+80`, usar filtros mais estreitos ou `--stat`/`--name-only`; ampliar somente quando o trecho pequeno não bastar.
- **Economia estimada:** ~9k-31k tokens por sessão afetada.
- **Fontes:** docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-109.md, docs/0005-analyze-token-efficiency/GUI-120.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-349.md (x2), docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-361.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-363.md, docs/0005-analyze-token-efficiency/GUI-365.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-367.md, docs/0005-analyze-token-efficiency/GUI-368.md, docs/0005-analyze-token-efficiency/GUI-369.md

### 2. Preflight de comandos propensos a falha
- **Problema:** Comandos exploratórios, testes com nomes incorretos e scripts de ambiente falham antes de contribuir para a solução, despejando contexto descartável.
- **Solução:** Validar caminho, ambiente e comando mínimo antes de rodar variantes caras; quando a dúvida for estrutural, preferir inspeção estática com `rg`/metadados do modelo.
- **Economia estimada:** ~1k-15k tokens por sessão afetada.
- **Fontes:** docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-120.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-349.md, docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-361.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-363.md, docs/0005-analyze-token-efficiency/GUI-365.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-368.md, docs/0005-analyze-token-efficiency/GUI-369.md

### 3. Watchdog de re-leitura/re-grep
- **Problema:** O agente relê o mesmo arquivo, repete `rg`/`git diff`/`git status` ou reexecuta validações idênticas, reinjetando evidência já conhecida no contexto.
- **Solução:** Se uma chamada idêntica já foi executada, reutilizar a conclusão anterior ou exigir mudança explícita de escopo/argumento antes de repetir.
- **Economia estimada:** ~500-4.5k tokens por repetição evitada; até ~30% dos tokens de reanálise.
- **Fontes:** loop-2/GUI-Others.md, docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-363.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-367.md, docs/0005-analyze-token-efficiency/GUI-368.md, docs/0005-analyze-token-efficiency/GUI-369.md

### 4. Encadear descoberta com consultas mais específicas
- **Problema:** O agente faz descoberta ampla e muitas chamadas de ferramenta antes de convergir no arquivo ou helper realmente implicado.
- **Solução:** Começar por `graphify query` ou grep específico; depois abrir só os arquivos diretamente implicados, delegando mapas amplos a graphify/subagente compacto.
- **Economia estimada:** ~3.5k-6.5k tokens por sessão afetada.
- **Fontes:** docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-120.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-361.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-368.md, docs/0005-analyze-token-efficiency/GUI-369.md

### 5. Reduzir contexto persistido entre etapas do worker
- **Problema:** Logs, diffs e leituras antigas continuam no contexto cacheado e encarecem fases posteriores de teste, commit e merge.
- **Solução:** Antes de fases longas, resumir descobertas em estado compacto com arquivos alterados, decisões e comandos de verificação; evitar reintroduzir saídas antigas.
- **Economia estimada:** ~5k-14.5k tokens por sessão afetada.
- **Fontes:** docs/0005-analyze-token-efficiency/GUI-108.md, docs/0005-analyze-token-efficiency/GUI-120.md, docs/0005-analyze-token-efficiency/GUI-159.md, docs/0005-analyze-token-efficiency/GUI-168.md, docs/0005-analyze-token-efficiency/GUI-360.md, docs/0005-analyze-token-efficiency/GUI-361.md, docs/0005-analyze-token-efficiency/GUI-362.md, docs/0005-analyze-token-efficiency/GUI-365.md, docs/0005-analyze-token-efficiency/GUI-366.md, docs/0005-analyze-token-efficiency/GUI-369.md

### 6. Verificação em escada / evitar suíte duplicada
- **Problema:** Testes focados + suíte completa + re-execução pós-lint, e os hooks de commit rodam pytest de novo — validação duplicada e lenta.
- **Solução:** Após mudança final pequena, rodar só testes/lint impactados; deixar a suíte completa para hooks/CI; rodar suíte completa de novo só se a mudança tocar lógica central ou o usuário exigir.
- **Economia estimada:** ~500-3k tokens + tempo de execução.
- **Fontes:** loop-2/GUI-267.md, loop-2/GUI-302.md, loop-2/GUI-323.md

### 7. Commit-merge determinístico e seguro
- **Problema:** A skill recomenda `git add .` e `git commit -am`, redundante/incorreto para arquivos novos e perigoso em worktree sujo.
- **Solução:** Fluxo explícito: `git status --short`; stage explícito dos arquivos alterados pela task; `git commit -m`; nunca `git add .` em repo possivelmente sujo; tratar claramente o caso "sem mudanças".
- **Economia estimada:** ~500k-1k tokens (menos checagens defensivas).
- **Fontes:** loop-2/GUI-268.md, loop-2/GUI-323.md

### 8. Precheck de bloqueio de merge no worktree master
- **Problema:** A skill só descobre que o worktree master está sujo (ou que há interseção de arquivos) depois de commitar, quando o bloqueio do merge era previsível antes.
- **Solução:** Antes do merge, checar `git status --short` do worktree master e comparar `git diff --name-only master...HEAD` com o target; se houver interseção/sujeira, parar/perguntar antes de commitar.
- **Economia estimada:** ~1k-2k tokens + 4-6 chamadas.
- **Fontes:** loop-2/GUI-302.md, loop-2/GUI-323.md

### 9. Atalhos fixos de comandos do repo (test/lint)
- **Problema:** O agente lê o README inteiro para descobrir comandos de teste/lint que já são padrão do workspace.
- **Solução:** Atalho fixo no harness para este repo (`uv run rtk pytest [<path>]`, `uv run rtk ruff check <paths>`) e/ou macro `verify_changed_python` (ruff+mypy+testes relevantes em saída compacta).
- **Economia estimada:** ~800-4k tokens.
- **Fontes:** loop-2/GUI-274.md, loop-2/GUI-304.md

### 10. Subagent de análise de impacto pré-task
- **Problema:** O agente principal gasta muitos tokens lendo arquivos só para confirmar que não usam um símbolo, ou para mapear caminhos protegidos vs desprotegidos manualmente.
- **Solução:** Subagent leve que recebe um símbolo/import a remover (ou um alvo) e retorna só: callers (grep), arquivos que precisam de rollback guard, fixtures dependentes — nada mais.
- **Economia estimada:** ~13k tokens.
- **Fontes:** loop-2/GUI-Others.md (x2: impact-analysis, impact-scan)

### 11. Lint antes do commit
- **Problema:** O commit falha por regra do ruff/format/teste direcionado, gerando novo ciclo de patch/stage/commit com saída de hook grande.
- **Solução:** Em tasks Python com testes novos ou edição de código, rodar `ruff check`, `ruff format --check` e o teste direcionado antes do commit.
- **Economia estimada:** ~1k-18k tokens + 2-3 chamadas.
- **Fontes:** loop-2/GUI-302.md, docs/0005-analyze-token-efficiency/GUI-349.md

### 12. Linear auto-contexto (resumo injetado)
- **Problema:** Para ler o ticket exige carregar skill e rodar `orca status`, consumindo tokens com instruções longas e JSON grande.
- **Solução:** Para worktrees linkados, injetar automaticamente um resumo curto do issue: título, descrição, estado, branch e labels.
- **Economia estimada:** ~2k-4k tokens.
- **Fontes:** loop-2/GUI-267.md

### 13. RTK só para saídas volumosas
- **Problema:** `rtk git ...` adiciona uma camada e regras extras sem benefício em comandos de saída curta como `status --short`.
- **Solução:** Usar RTK só para comandos potencialmente volumosos (diff, log grande, grep); para `status --porcelain`, `merge-base`, `branch`, usar `git` direto.
- **Economia estimada:** ~5-10% dos tokens da task.
- **Fontes:** loop-2/GUI-268.md

### 14. Resumir git worktree list automaticamente
- **Problema:** `git worktree list` retorna dezenas de worktrees, ocupando muito contexto, quando só importa onde está o master.
- **Solução:** Instruir RTK/harness a resumir para "current worktree + master worktree + branch alvo", omitindo os demais salvo conflito.
- **Economia estimada:** ~1k-2k tokens.
- **Fontes:** loop-2/GUI-304.md

### 15. Resposta compacta para no-op
- **Problema:** Mesmo em no-op há espaço para explicação redundante.
- **Solução:** Template fixo: "Sem mudanças pendentes; master já contém HEAD. Nenhuma ação feita."
- **Economia estimada:** ~3-8% dos tokens.
- **Fontes:** loop-2/GUI-268.md

### 16. Template obrigatório de ticket
- **Problema:** Tickets ambíguos escondem o gap real; falta de campos padronizados aumenta a exploração.
- **Solução:** Template obrigatório no `send-to-linear` com "Arquivos afetados", "Teste que reproduz o bug" e "Critérios de aceitação".
- **Economia estimada:** Reduz ambiguidade e exploração inicial.
- **Fontes:** loop-2/GUI-Others.md

### 17. Skill test-impact (diff → testes afetados)
- **Problema:** Descobrir quais testes dependem de um comportamento alterado é feito manualmente (ou com subagent) e ainda deixa arquivos escaparem.
- **Solução:** Skill `test-impact` que, dado um diff, escaneia e lista todos os testes afetados pelas funções/símbolos alterados.
- **Economia estimada:** Evita subagent manual + reduz regressões perdidas.
- **Fontes:** loop-2/GUI-Others.md

### 18. Hook pytest "0 falhas = sucesso"
- **Problema:** O RTK filtra o output do pytest para mostrar só falhas; output vazio = sucesso, mas isso não é óbvio, gerando chamadas redundantes de confirmação.
- **Solução:** Hook que intercepta o retorno vazio de `rtk pytest` e emite inline "All tests passed (N passed, 0 failed)".
- **Economia estimada:** Evita ~3 chamadas redundantes por task.
- **Fontes:** loop-2/GUI-Others.md

### 19. Agente enxuto para bug fixes triviais
- **Problema:** O thinking loop gasta ~8k tokens avaliando alternativas quando o ticket já diz qual é o problema.
- **Solução:** Subagent especializado que recebe `{file}:{line}` e produz o diff sem deliberar sobre alternativas (~1k tokens).
- **Economia estimada:** ~7k tokens por bug-fix trivial.
- **Fontes:** loop-2/GUI-Others.md

### 20. Inspeção pós-merge sem diff detalhado
- **Problema:** Em convergência de merge, abrir diff detalhado só para confirmar arquivos staged reinjeta conteúdo grande no fim da sessão.
- **Solução:** Usar `merge-base`, `diff --cached --name-only` e `diff --cached --stat`; abrir diff completo só se houver arquivo inesperado ou conflito real.
- **Economia estimada:** ~2.5k tokens.
- **Fontes:** docs/0005-analyze-token-efficiency/GUI-349.md

## Ranking por menções

| # | Melhoria | Menções | Fontes |
|---|----------|---------|--------|
| 1 | Limitar leitura de outputs grandes ao trecho necessário | 16 | GUI-108, GUI-109, GUI-120, GUI-159, GUI-168, GUI-349, GUI-360, GUI-361, GUI-362, GUI-363, GUI-365, GUI-366, GUI-367, GUI-368, GUI-369 |
| 2 | Preflight de comandos propensos a falha | 13 | GUI-108, GUI-120, GUI-159, GUI-168, GUI-349, GUI-360, GUI-361, GUI-362, GUI-363, GUI-365, GUI-366, GUI-368, GUI-369 |
| 3 | Watchdog de re-leitura/re-grep | 11 | loop-2, GUI-108, GUI-159, GUI-168, GUI-360, GUI-362, GUI-363, GUI-366, GUI-367, GUI-368, GUI-369 |
| 4 | Encadear descoberta com consultas mais específicas | 10 | GUI-108, GUI-120, GUI-159, GUI-168, GUI-360, GUI-361, GUI-362, GUI-366, GUI-368, GUI-369 |
| 5 | Reduzir contexto persistido entre etapas do worker | 10 | GUI-108, GUI-120, GUI-159, GUI-168, GUI-360, GUI-361, GUI-362, GUI-365, GUI-366, GUI-369 |
| 6 | Verificação em escada / evitar suíte duplicada | 3 | loop-2 |
| 7 | Atalhos fixos de comandos do repo (test/lint) | 2 | loop-2 |
| 8 | Commit-merge determinístico e seguro | 2 | loop-2 |
| 9 | Lint antes do commit | 2 | loop-2, GUI-349 |
| 10 | Precheck de bloqueio de merge no worktree master | 2 | loop-2 |
| 11 | Subagent de análise de impacto pré-task | 2 | loop-2 |
| 12 | Agente enxuto para bug fixes triviais | 1 | loop-2 |
| 13 | Hook pytest "0 falhas = sucesso" | 1 | loop-2 |
| 14 | Inspeção pós-merge sem diff detalhado | 1 | GUI-349 |
| 15 | Linear auto-contexto (resumo injetado) | 1 | loop-2 |
| 16 | Resposta compacta para no-op | 1 | loop-2 |
| 17 | Resumir git worktree list automaticamente | 1 | loop-2 |
| 18 | RTK só para saídas volumosas | 1 | loop-2 |
| 19 | Skill test-impact (diff → testes afetados) | 1 | loop-2 |
| 20 | Template obrigatório de ticket | 1 | loop-2 |

_Total: 82 menções → 20 melhorias no ranking. 5 melhorias (24 menções) já aplicadas — ver `../0004-apply-harness-improvements/implementations.md`._
