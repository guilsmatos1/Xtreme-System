5. Subagent impact-analysis com template fixo

O agente principal gastou tokens lendo arquivos que não precisavam de mudança ([vendas.py](http://vendas.py), [investidores.py](http://investidores.py), [perfis.py](http://perfis.py), veiculo/[core.py](http://core.py), compra/[core.py](http://core.py), e2e/[conftest.py](http://conftest.py)) só para confirmar que eles não usavam atomic_write. Um subagent especializado que recebe um "símbolo a remover" (atomic_write) e retorna apenas a lista de arquivos que o referenciam + os que precisam de adaptação (ex: os que fazem except IntegrityError sem rollback) eliminaria 6 reads de confirmação negativa.

## Subagent: impact-analysis

Input: function name or import path to remove

Output:

- Callers (grep)
- Files needing new rollback() guards
- Test fixtures that depend on the removed behavior
- Nothing else



1. [AGENTS.md](http://AGENTS.md): "bug fix" shortcut que suprime leitura dos 4 docs

A leitura cega de [DATABASE.md](http://DATABASE.md) (306 linhas), [API.md](http://API.md) (416), [ARCHITECTURE.md](http://ARCHITECTURE.md) (214) e [README.md](http://README.md) (133) custou ~1000+ linhas de contexto quando o linear issue já especificava components/xtreme_system/venda/core.py:101-152, bases/xtreme_system/api/routes/json.py:177-192 e bases/xtreme_system/api/routes/ui_routes/vendas.py:46-100.

- Fixing a bug from a Linear issue with explicit file:line references →

  read only the referenced files first. Read [ARCHITECTURE.md](http://ARCHITECTURE.md) only if

  the flow crosses layer boundaries in ways you don't understand.

Economia estimada: ~3000 tokens por bug-fix com issue auto-documentado.



&nbsp;

2. Skill: targeted-explore — lê os arquivos referenciados pela issue, expande só sob demanda

A exploração progressiva leu ~3500 linhas de código-fonte. Desse total, route_[factories.py](http://factories.py) (219), crud_ui/[routes.py](http://routes.py) (540), crud_[writes.py](http://writes.py) (68) e o template HTML (219) foram lidos para confirmar assinaturas de hooks e comportamento do formulário — informação que poderia ser sumarizada por um agente especializado em 1/3 do custo.

O skill extrairia file:line do description da issue, leria só esses trechos, e só faria grep por imports/funções referenciadas se o contexto inicial fosse ambíguo.

Economia estimada: ~1500 linhas de leitura evitadas.



&nbsp;

&nbsp;

2. Template/validação de ticket com checklist de "done" e arquivos afetados

O ticket GUI-101 dizia "generic HTMX CRUD routes" mas o gap real estava nos handlers manuais ([veiculos.py](http://veiculos.py), [vendas.py](http://vendas.py)) que usam register_create=False. Um template obrigatório com campos como "Arquivos afetados", "Teste que reproduz o bug", e "Critérios de aceitação" teria reduzido ambiguidade. Idealmente integrado ao send-to-linear skill, que já existe mas não impõe esses campos.



&nbsp;

3. Subagent de "impact scan" pré-implementação

Um subagent leve acionado no início de toda task que:

- Faz rg "module(create|update|delete)session" nos route handlers
- Cruza com rg "except IntegrityError" para identificar caminhos protegidos vs desprotegidos
- Retorna um relatório de 10 linhas: "Protegidos: X, Y, Z. Desprotegidos: A, B, C"

Isso teria me dado em &lt;2k tokens o que levei ~15k tokens para descobrir manualmente. O analyze-codebase skill existente poderia ser adaptado para este modo "cirúrgico pré-task".



&nbsp;

&nbsp;

5. Watchdog de loop / re-leitura no agente

O agente gastou tokens relendo crud_ui/[routes.py](http://routes.py) ao menos 3 vezes e repetindo buscas rg similares. Um mecanismo simples: se o agente lê o mesmo arquivo 2+ vezes com o mesmo offset/limit ou faz a mesma query rg com mesmo padrão 2+ vezes, pausa e pergunta: "Já analisei este arquivo/pattern. Devo continuar ou refinar a abordagem?" Isso teria cortado ~30% dos tokens gastos em re-análise.



&nbsp;

2. O mapeamento de impacto foi feito manualmente com subagent.

Gastei um subagent (explore) para descobrir quais testes chamavam funções auditáveis sem usuario_id. Ainda assim, 2 arquivos escaparam.

→ Um skill test-impact que, dado um diff, escaneia todas as



3. Hook pós-rtk pytest que sinaliza "0 falhas = sucesso"

O RTK filtra output de pytest para mostrar só falhas. Quando o output é vazio, significa sucesso — mas isso não é óbvio. Um hook que intercepte o retorno vazio de rtk pytest e emita All tests passed (N passed, 0 failed) como comentário inline evitaria as 3 chamadas redundantes que fiz tentando confirmar que os testes passaram.



&nbsp;

4. Rule no [AGENTS.md](http://AGENTS.md): "read target file once with ±30 lines around the cited line"

O ticket citava venda/core.py:161. Li primeiro um chunk (140-199), depois outro (136-140) para a helper function. Uma regra simples: quando o ticket cita arquivo:linha, ler linha-30 até linha+30 em uma única chamada. Economizaria 1 read + 1 glob neste caso.



&nbsp;

&nbsp;

2. Agente general com prompt enxuto para bug fixes triviais

Criar um subagent especializado em dead code / unreachable branch que receba só {file}:{line} e produza o diff sem deliberar sobre alternativas. O thinking loop neste caso gastou ~8k tokens avaliando "e se removermos X em vez de Y?" — o ticket já dizia qual era o problema. O agente reduziria isso a ~1k.



&nbsp;

&nbsp;

&nbsp;