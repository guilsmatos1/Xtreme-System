# Análise de Codebase — Xtreme System

10 oportunidades de melhoria, ordenadas por impacto. Foco em correção,
confiabilidade e risco operacional acima de estilo.

---

## Opportunity 1: Migrations nunca são exercitadas pela suíte de testes padrão

Location: tests/database.py:23-33
Impact: High
Category: Testing
Estimated effort: Medium

Description:
No caminho padrão (sem `TEST_DATABASE_URL`), o engine de teste é SQLite e o
schema é criado com `Base.metadata.create_all(engine)` — os ~35 arquivos em
`alembic/versions/` são completamente ignorados. As migrations só rodam quando
alguém aponta `TEST_DATABASE_URL` para um Postgres, o que não é o caminho de CI
descrito no `ARCHITECTURE.md` ("Testes usam SQLite in-memory").

Why it matters:
Uma migration quebrada, uma coluna adicionada ao model mas esquecida na
migration, ou divergência entre `server_default`/tipos e o que o Alembic gera
passa 100% dos testes. O schema real de produção (Postgres) e o schema testado
(SQLite via metadata) são objetos diferentes — a suíte dá falsa confiança
exatamente na camada mais difícil de reverter em produção.

Concrete fix suggestion:
Rodar as migrations em CI contra um Postgres efêmero (o código para isso já
existe em `_run_migrations`), e adicionar um teste que compara o schema gerado
pelos models com o schema após `upgrade head` (autogenerate deve produzir diff
vazio).

Example:
```python
def test_migrations_match_models(alembic_config, pg_engine):
    command.upgrade(alembic_config, "head")
    diff = compare_metadata(
        MigrationContext.configure(pg_engine.connect()), Base.metadata
    )
    assert diff == [], f"models divergem das migrations: {diff}"
```

---

## Opportunity 2: Fronteiras de transação inconsistentes e mecanismo `DEFER_COMMIT_KEY` morto

Location: components/xtreme_system/usuario/core.py:75,99,114 · components/xtreme_system/crud/core.py:9-13 · bases/xtreme_system/api/crud_writes.py:30-46
Impact: High
Category: Maintainability
Estimated effort: Medium

Description:
Três padrões de commit convivem:
- `crud.commit()` na verdade só faz `session.flush()` (nome enganoso — não faz
  commit).
- `usuario.create/change_password/set_perfil` chamam `session.commit()`
  diretamente, no meio da requisição.
- `atomic_write` escreve `session.info[DEFER_COMMIT_KEY] = True`, mas **nada lê
  essa chave** — `crud.commit` a ignora. O mecanismo inteiro é código morto.

Why it matters:
`usuario.*` faz commit imediato, quebrando a atomicidade se essas funções forem
compostas em um fluxo maior (ex.: criar usuário + outra escrita na mesma
requisição): a primeira parte já foi persistida e não pode ser revertida se a
segunda falhar. O `DEFER_COMMIT_KEY` morto sugere que existiu (ou pretendia-se)
um controle de commit diferido que nunca funcionou — qualquer manutenção futura
vai raciocinar sobre um contrato que não existe.

Concrete fix suggestion:
Padronizar: componentes só fazem `flush()`; o commit pertence à borda
(`atomic_write` ou `get_session`). Trocar os `session.commit()` de `usuario`
por `session.flush()` e garantir que as rotas manuais de usuário usem
`atomic_write`. Remover `DEFER_COMMIT_KEY` ou fazer `crud.commit` respeitá-lo.

---

## Opportunity 3: Rate limiter em memória — ineficaz com múltiplos workers e com vazamento de memória

Location: bases/xtreme_system/api/setup.py:90-114
Impact: High
Category: Error handling / operational
Estimated effort: Medium

Description:
`_RateLimiter` guarda os hits em um `defaultdict(deque)` de processo. Dois
problemas:
1. O estado é por processo. Sob Gunicorn/Uvicorn com N workers, o limite
   efetivo vira N×5 no login e N×100 no geral, e cai a cada restart/deploy — a
   proteção contra brute-force de senha (`/login`) fica frágil.
2. `self._hits[key]` cria uma entrada por IP e **nunca remove** as chaves cujos
   deques esvaziaram. Um atacante rotacionando IPs (ou tráfego legítimo diverso)
   faz o dicionário crescer sem limite → vazamento de memória.

Why it matters:
É o único controle contra força-bruta de credenciais e contra abuso. Hoje ele
não segura o que promete em produção multi-worker e é um vetor de exaustão de
memória.

Concrete fix suggestion:
Mover o estado para um store compartilhado (Redis) se houver mais de um worker.
No mínimo, evictar chaves ociosas: após `popleft`, se `not hits: del
self._hits[key]`. Considerar `slowapi`/`limits` em vez de implementação própria.

Example:
```python
while hits and hits[0] < cutoff:
    hits.popleft()
if not hits:
    del self._hits[key]      # evita crescimento ilimitado
    hits = self._hits[key]
```

---

## Opportunity 4: Notificação de WhatsApp dispara antes do commit da transação

Location: components/xtreme_system/whatsapp/core.py:128-151 · bases/xtreme_system/api/route_factories.py:83-93
Impact: Medium
Category: Error handling
Estimated effort: Low

Description:
`whatsapp.notificar_venda` é registrado como `after_create` da venda e roda
**dentro** do `atomic_write`, antes de `session.commit()`. Ele já dispara a
thread que envia o HTTP. Se o commit falhar em seguida (ex.: `IntegrityError`,
constraint), a transação é revertida — mas a mensagem "Nova venda registrada"
já foi (ou está sendo) enviada para o grupo.

Why it matters:
Gera notificação de uma venda que não existe no banco. Em um fluxo financeiro,
mensagens falsas para o grupo de vendas corroem a confiança no sistema e podem
disparar ações humanas equivocadas.

Concrete fix suggestion:
Disparar o efeito colateral externo somente após o commit — capturar os dados
da mensagem no hook e enfileirar o envio para depois do `session.commit()`
bem-sucedido (ex.: usar o retorno de `atomic_write` para então notificar, ou um
callback pós-commit via evento SQLAlchemy `after_commit`).

---

## Opportunity 5: Verificação de "admin" duplicada em três lugares, com estilos divergentes

Location: bases/xtreme_system/api/deps.py:55-58,102-105 · components/xtreme_system/perfil/core.py:82-85
Impact: Medium
Category: Architecture and design
Estimated effort: Low

Description:
A regra "é admin?" aparece três vezes:
- `require_admin`: `user.papel != usuario.Papel.admin`
- `require_ui_admin`: `user.papel != usuario.Papel.admin`
- `pode_acessar`: `user.papel.value == "admin"` (comparação por string literal)

Duas comparam contra o enum; a terceira compara a string `"admin"` crua.

Why it matters:
É lógica de autorização — o lugar onde divergência silenciosa vira falha de
segurança. Renomear o valor do enum, adicionar um papel ou introduzir
"superadmin" exige lembrar de três pontos com convenções diferentes; a string
literal `"admin"` não é pega por refactors guiados por tipo.

Concrete fix suggestion:
Centralizar em um único predicado no componente `usuario` (ou `perfil`) e
reusar nos três pontos: `def is_admin(user) -> bool: return user.papel ==
Papel.admin`. Remover a comparação por string.

---

## Opportunity 6: Endpoints de listagem carregam a tabela inteira e ordenam/filtram em Python, sem paginação

Location: bases/xtreme_system/api/crud_ui/query.py:33-63 · components/xtreme_system/venda/core.py:53-58,124-125
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
`query_list` chama `module.list_all(session)` (SELECT sem `LIMIT`) e
`sorted_list` ordena a lista **em memória Python**. Não há paginação em nenhuma
rota de listagem UI/JSON. No caso de `Venda`, cada relação
(`cliente`, `veiculo`, `veiculo_troca`, `vendedor`) é `lazy="joined"`, então
listar vendas emite um JOIN largo trazendo todas as linhas a cada request, e
depois ordena em Python.

Why it matters:
Cresce linearmente com o número de registros. Numa concessionária com histórico
de anos de vendas/veículos, cada abertura da tela de listagem materializa a
tabela inteira + joins e ordena no processo web — latência e memória crescem sem
teto, e a ordenação em Python impede o banco de usar índices.

Concrete fix suggestion:
Empurrar `ORDER BY`/`LIMIT`/`OFFSET` (ou keyset pagination) para o SQL. Como
`sort_fields` já mapeia campos ordenáveis, dá para traduzi-los em
`order_by(getattr(Model, campo))` e paginar no query em vez de na lista.

---

## Opportunity 7: `agregados_investidores` faz varredura completa em Python e duplica a lógica de `saldos`

Location: components/xtreme_system/caixa/core.py:204-223 · bases/xtreme_system/api/routes/ui_routes/investidores.py:60-84
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
A tela de investidores chama, na mesma request, `caixa.saldos()` (um `GROUP BY`
em SQL) **e** `caixa.agregados_investidores()`, que carrega `list_all(Veiculo)`
e `list_all(LancamentoInvestimento)` inteiros e reagrega em laços Python —
inclusive recomputando o total aportado, que se sobrepõe ao que `saldos` já
calcula. O próprio código admite: *"In-memory aggregations for caixa table.
Query-level if row counts grow."*

Why it matters:
Duas passagens sobre as mesmas tabelas (uma em SQL, outra em Python) por
carregamento de página, com lógica de agregação duplicada e divergente sobre
quais `tipo`s somam positivo. Duplicação em cálculo financeiro é risco de
números que não batem entre colunas da mesma tela.

Concrete fix suggestion:
Substituir os laços por `GROUP BY` em SQL (`func.count`, `func.sum`) por
`investidor_id`, no mesmo estilo de `saldos()`, e reusar uma única definição da
regra de sinal por `tipo`.

---

## Opportunity 8: Ramo morto em `_sincronizar_status_veiculo` esconde a intenção real

Location: components/xtreme_system/venda/core.py:142-166
Impact: Medium
Category: Code quality
Estimated effort: Low

Description:
A função monta a flag `sincronizado` condicionalmente para o veículo anterior,
mas na linha 161 faz `sincronizado = True` incondicional logo depois. Com isso,
o `if not sincronizado: return obj` (linha 162) é inalcançável e o early-return
é código morto. O leitor é levado a crer que existe um caminho "sem sincronizar"
que nunca ocorre.

Why it matters:
Mistura sincronização de estado com controle de commit e mente sobre seus
caminhos possíveis. Em código que dispara mudança de status de veículo (com
efeito no fechamento financeiro), lógica enganosa é terreno fértil para bugs na
próxima edição.

Concrete fix suggestion:
Remover a flag e o early-return e deixar explícito que a venda sempre
sincroniza o status do seu veículo atual, e opcionalmente reseta o anterior:
```python
if (veiculo_anterior_id and veiculo_anterior_id != obj.veiculo_id
        and status_anterior == StatusVenda.concluido):
    if (anterior := session.get(Veiculo, veiculo_anterior_id)):
        anterior.status = StatusVeiculo.disponivel
obj.veiculo.status = _status_veiculo_para_venda(obj.status)
crud.commit(session)
session.refresh(obj)
return obj
```

---

## Opportunity 9: Trilha de auditoria perde o autor silenciosamente quando `session.info` não está setado

Location: components/xtreme_system/auditoria/core.py:56-77 · components/xtreme_system/crud/core.py:24-70
Impact: Medium
Category: Error handling / observability
Estimated effort: Low

Description:
`auditar` obtém o autor via `session.info.get("usuario_id")` — se a chave não
foi setada, grava `usuario_id=None` sem reclamar. A atribuição do autor depende
de cada rota lembrar de `session.info["usuario_id"] = user.id`. Qualquer escrita
que passe por `crud.create/update/delete` fora desse contrato produz um registro
de auditoria órfão, indistinguível de uma ação legítima de sistema.

Why it matters:
Auditoria é justamente a feature onde "silenciosamente errado" é o pior modo de
falha. Um `usuario_id` nulo por esquecimento de wiring é indetectável depois do
fato e enfraquece o valor probatório da trilha.

Concrete fix suggestion:
Tornar a intenção explícita: exigir o autor por parâmetro em `auditar` (ou um
sentinela `SYSTEM`), e logar em nível warning quando um write auditável não
tiver autor. Alternativamente, um teste que garanta que toda rota de mutação
seta `usuario_id`.

---

## Opportunity 10: Erros não tratados são logados duas vezes

Location: bases/xtreme_system/api/setup.py:57-77,186-191
Impact: Low
Category: Error handling / logging
Estimated effort: Low

Description:
O middleware `_request_context` captura qualquer exceção, chama
`logger.exception("unhandled_error", ...)` e re-levanta. O
`@app.exception_handler(Exception)` então captura a mesma exceção e chama
`logger.exception("unhandled_error", ...)` de novo. Todo erro interno gera dois
registros idênticos. Além disso, `clear_contextvars()` (linha 75) só é chamado
no caminho de sucesso — em caso de exceção ele é pulado.

Why it matters:
Duplicação infla o volume de logs e distorce contadores/alertas por taxa de erro
(cada incidente conta como dois). Não é crítico, mas polui a observabilidade
justamente nos eventos que mais importam.

Concrete fix suggestion:
Logar em um único lugar. Manter o log no `exception_handler` (que tem o contexto
da resposta) e remover o `try/except` de logging do middleware, ou vice-versa.
Mover `clear_contextvars()` para um `finally`.
