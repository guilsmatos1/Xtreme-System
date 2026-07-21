# Análise de Codebase — 10 Oportunidades de Melhoria

Gerado em 2026-07-20. Ordenado da maior para a menor prioridade.

---

## A API JSON ignora o modelo de permissões por perfil que a UI aplica

Location: bases/xtreme_system/api/route_factories.py:62-68 (`register_crud_routes._list` / `_get`)
Impact: High
Category: Architecture and design
Estimated effort: Medium

Description:
As rotas HTMX aplicam três camadas de autorização: `pagina_da_rota` + `pode_acessar`
em `get_ui_user` (bases/xtreme_system/api/deps.py:107), `require_operacao` por
operação, e `pode_ver_campo` para mascarar campos sensíveis (colunas do CSV em
crud_ui/routes.py:297-304 e campos de formulário em crud_ui/routes.py:508-511).

As rotas JSON criadas por `register_crud_routes` só exigem `CurrentUser`:

```python
@app.get(prefix, response_model=list[read_schema])
def _list(session: SessionDep, _: CurrentUser) -> list[EntityT]:
    return module.list_all(session)
```

Isso vale para `/veiculos`, `/vendas`, `/clientes`, `/investidores` e
`/lancamentos-caixa` (bases/xtreme_system/api/routes/json.py:122-274). Qualquer
usuário autenticado e ativo — inclusive um funcionário cujo perfil oculta
`preco`, `valor_venda`, `valor_entrada` ou nem sequer dá acesso à página — recebe
o `VeiculoRead`/`VendaRead` completo, com `preco` (veiculo/core.py:122) e todos os
valores financeiros.

O padrão correto já existe no mesmo arquivo: `/compras` faz `_compra_json` com
`pode_ver_campo` e `_require_compra_operacao` com `pode_operacao`
(json.py:280-346). Ou seja, a regra foi implementada uma vez, à mão, para uma
entidade, e as outras cinco ficaram de fora.

Why it matters:
É um bypass real de controle de acesso, não uma inconsistência estética. As
restrições de perfil são a funcionalidade que separa admin de funcionário no
produto, e elas valem apenas para quem usa o navegador. Além disso, cada nova
entidade registrada via `register_crud_routes` herda o problema silenciosamente.

Concrete fix suggestion:
Mover a checagem para a factory, com `pagina` e mapa de campos protegidos como
parâmetros — mesmo contrato já usado em `register_crud_ui_routes`
(`pagina=`, `campos_form_map=`). Menor correção útil:

```python
def register_crud_routes(app, module, prefix, label, *, pagina: str | None = None,
                         campos_protegidos: list[str] | None = None, ...):
    def _mask(obj, user):
        data = jsonable_encoder(read_schema.model_validate(obj))
        for campo in campos_protegidos or []:
            if not perfil.pode_ver_campo(user, pagina, campo):
                data.pop(campo, None)
        return data

    @app.get(prefix)
    def _list(session: SessionDep, user: CurrentUser) -> list[dict[str, Any]]:
        if pagina and not perfil.pode_acessar(user, pagina):
            raise HTTPException(status_code=403, detail="Acesso negado")
        return [_mask(obj, user) for obj in module.list_all(session)]
```

Tradeoff: mudar `response_model` para `dict` perde a documentação automática do
OpenAPI. Alternativa mais conservadora, se aceitável para o produto: exigir
`AdminUser` também em `_list`/`_get`, restringindo a API JSON a admins.

---

## Toda listagem carrega a tabela inteira e ordena/filtra em Python

Location: bases/xtreme_system/api/crud_ui/query.py:70-94 e crud_ui/routes.py:237-268, 453-460, 553-560, 607-614
Impact: High
Category: Performance
Estimated effort: High

Description:
`query_list` termina sempre em `module.list_all(session)`, que é
`session.query(model_cls).all()` (components/xtreme_system/crud/core.py:14-15).
Não há `LIMIT`, `OFFSET` nem `WHERE` na maioria dos caminhos. Ordenação
(`sorted_list`) e filtro (`filter_list`) rodam em Python sobre a lista completa.

O custo se multiplica porque a lista é recarregada após cada escrita: `_criar`
(routes.py:453), `_atualizar` (routes.py:553) e `_excluir` (routes.py:607) todos
chamam `query_list` de novo para renderizar o parcial HTMX.

Em vendas o efeito é pior. `Venda` tem quatro relacionamentos `lazy="joined"`
(cliente, veiculo, veiculo_troca, vendedor — venda/core.py:64-69), então cada
listagem faz um join de cinco tabelas sobre o conjunto inteiro. Em cima disso,
`_ctx_lista_vendas` (ui_routes/vendas.py:134-136) chama
`fechamento_venda.list_all`, que por sua vez carrega `FechamentoVenda` com
`venda`, `usuario` e `participacoes` todos `lazy="joined"`
(fechamento_venda/core.py:55-61) — e o resultado é usado apenas para montar um
dicionário `{venda_id: fechamento}`.

Há ainda um N+1 clássico em `_atividades_recentes`
(ui_routes/dashboard.py:121-136): um `usuario.get` por linha de auditoria.

Why it matters:
O comportamento é aceitável com dezenas de registros e degrada de forma
não linear. Vendas e veículos são exatamente as tabelas que crescem com o uso do
produto; a página de vendas é a mais cara e a mais acessada. O `/exportar`
(routes.py:285-305) tem o mesmo perfil sem nem o alívio de um `LIMIT`.

Concrete fix suggestion:
Empurrar ordenação, filtro e paginação para o banco. `sort_fields` já é um mapa
declarativo; estendê-lo para aceitar colunas SQLAlchemy permite gerar
`order_by` real. Passo intermediário barato e de baixo risco, que resolve os dois
piores casos sem reescrever a factory:

```python
# ui_routes/vendas.py
def _ctx_lista_vendas(session: Session, vendas: list[Venda]) -> dict[str, Any]:
    ids = [v.id for v in vendas]
    if not ids:
        return {"fechamentos_by_venda": {}}
    fechamentos = (
        session.query(FechamentoVenda)
        .filter(FechamentoVenda.venda_id.in_(ids))
        .all()
    )
    return {"fechamentos_by_venda": {f.venda_id: f for f in fechamentos}}
```

E em `_atividades_recentes`, carregar os usuários em uma query só
(`Usuario.id.in_(ids)`).

Tradeoff: a paginação completa é um refactor grande e mexe nos templates HTMX.
Vale medir antes: se as tabelas ainda estão na casa das centenas de linhas, faça
os dois ajustes pontuais acima e adie a paginação.

---

## Atualizações de venda pela UI perdem o autor no log de auditoria

Location: bases/xtreme_system/api/routes/ui_routes/vendas.py:386
Impact: High
Category: Error handling and logging
Estimated effort: Low

Description:
`venda.update` é chamado sem `actor_id`:

```python
try:
    venda.update(session, obj, data)   # actor_id fica None
except IntegrityError:
```

O parâmetro é opcional (`actor_id: int | None = None`, venda/core.py:202-204) e
chega direto em `auditar(..., actor_id=actor_id)` via `crud.update`
(crud/core.py:41-57). A linha de auditoria fica com `usuario_id = NULL`.

A criação, quatro linhas acima, faz certo: `venda.create(session, data, user.id)`
(vendas.py:359). E `session.info["usuario_id"] = user.id` na linha 372 não ajuda —
nada em `auditar` lê `session.info`.

O mesmo defeito aparece em ui_routes/veiculos.py:392:
`caixa.sincronizar_lancamento_veiculo(session, atualizado)` sem `user.id`, o que
grava o UPDATE de `lancamento_investimento` como anônimo.

Why it matters:
A auditoria é a única trilha de quem alterou valores financeiros. O dashboard já
renderiza esses registros como "Sistema" (dashboard.py:122-126), então uma edição
manual de `valor_venda` aparece indistinguível de uma ação automática. É perda
silenciosa de dado — não há erro, teste falhando ou log.

Concrete fix suggestion:

```python
venda.update(session, obj, data, user.id)
```

e

```python
caixa.sincronizar_lancamento_veiculo(session, atualizado, user.id)
```

Depois, um teste que trave a regra:

```python
def test_update_venda_ui_registra_autor(client_admin, venda_existente, admin):
    client_admin.post(f"/ui/vendas/{venda_existente.id}", data={...})
    row = ultima_auditoria(session, tabela="venda", tipo_acao="UPDATE")
    assert row.usuario_id == admin.id
```

Vale ainda considerar tornar `actor_id` obrigatório (posicional sem default) em
`crud.update`/`crud.create`, para que a omissão vire erro de tipo em vez de dado
faltando.

---

## `query_list` engole `TypeError` e mascara bugs dentro das funções de busca

Location: bases/xtreme_system/api/crud_ui/query.py:80-86
Impact: Medium
Category: Error handling and logging
Estimated effort: Low

Description:

```python
if q and search_func is not None:
    try:
        return list(search_func(session, q, column=search_column))
    except TypeError:
        return list(search_func(session, q))
```

O `except TypeError` foi escrito para detectar assinaturas sem `column`, mas ele
captura qualquer `TypeError` levantado em qualquer ponto da execução de
`search_func` — inclusive dentro do SQLAlchemy ou na comparação de tipos
incompatíveis. Nesse caso a busca é executada uma segunda vez, com semântica
diferente (busca global em vez de por coluna), e o usuário recebe resultados
plausíveis mas errados, sem nenhum log.

Na prática o fallback é código morto: todas as sete implementações registradas
(`venda.search`, `veiculo.search`, `cliente.search`, `compra.search`,
`custo_veiculo.search`, `cliente.search_compradores`, `cliente.search_vendedores`)
já aceitam `column`.

Why it matters:
É um try/except que transforma uma exceção diagnosticável em resultado
silenciosamente incorreto — a pior categoria de tratamento de erro. E o custo de
remover é praticamente zero, já que o caminho de fallback nunca é exercitado.

Concrete fix suggestion:
Remover o `try/except` e chamar com `column` diretamente. Se o suporte a
assinaturas antigas for mesmo necessário, decidir por inspeção em vez de exceção:

```python
if q and search_func is not None:
    params = inspect.signature(search_func).parameters
    if "column" in params:
        return list(search_func(session, q, column=search_column))
    return list(search_func(session, q))
```

---

## Rate limiter em banco: uma transação de escrita por request e tabela que só cresce

Location: components/xtreme_system/database/core.py:64-114 (`DatabaseRateLimiterStore.allow`)
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
O store padrão é o de banco (`RATE_LIMIT_STORE` default `"database"`,
bases/xtreme_system/api/setup.py:80-84), e o middleware `_rate_limit` chama
`store.allow` em toda requisição não isenta (setup.py:162-190). Cada chamada abre
uma conexão própria e executa, em uma transação: um `INSERT ... ON CONFLICT DO
NOTHING`, um `SELECT ... FOR UPDATE` e um `UPDATE`.

Dois efeitos:

1. Todo GET de página vira três statements de escrita extras, serializados pelo
   `FOR UPDATE` no bucket do IP. Requisições concorrentes do mesmo cliente —
   exatamente o padrão do HTMX, que dispara vários fragmentos por tela — ficam em
   fila umas atrás das outras.
2. `rate_limit_state` nunca é limpa. `reset()` só é chamado por
   `reset_rate_limiters()`, usado em testes (setup.py:141-143). Um `bucket` é
   criado por IP e por `login:{IP}`, e a linha permanece indefinidamente, com a
   lista JSON de hits dentro dela.

Why it matters:
É custo fixo em toda a aplicação, não em um endpoint específico, e a contenção só
aparece sob carga — quando é mais difícil diagnosticar. O crescimento da tabela é
lento mas monotônico e não tem nenhum processo que o interrompa.

Concrete fix suggestion:
Adicionar uma coluna `atualizado_em` e uma limpeza periódica (job, ou uma
varredura probabilística barata dentro do próprio `allow`):

```python
Column("atualizado_em", DateTime(timezone=True), server_default=func.now())

# ...em allow(), ocasionalmente:
conn.execute(
    delete(rate_limit_state).where(
        rate_limit_state.c.atualizado_em < datetime.now(UTC) - timedelta(hours=1)
    )
)
```

Se o deploy é de instância única (o que o `casaos/docker-compose.yml` sugere),
vale reavaliar o default: `_MemoryRateLimiterStore` já existe, não toca no banco e
é suficiente nesse cenário. Nota menor no mesmo trecho: em `_ensure_bucket`
(linha 90) o `statement` inicial é sempre descartado nos ramos postgresql/sqlite.

---

## Cache negativo permanente do schema de fechamento

Location: components/xtreme_system/fechamento_venda/core.py:131-146 (`_schema_disponivel`)
Impact: Medium
Category: Maintainability
Estimated effort: Low

Description:
O resultado da inspeção é memoizado por engine em um `WeakKeyDictionary`, sem
distinguir resultado positivo de negativo:

```python
disponivel = inspector.has_table(...) and inspector.has_table(...)
_SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel
return disponivel
```

Se o processo subir antes da migração, `False` fica gravado para o tempo de vida
do engine. Rodar `make migrate` com a aplicação no ar não muda nada: `list_all`
continua retornando `[]` (linha 150), `get_by_venda` continua retornando `None`
(linha 163) e `confirmar` continua levantando `ERRO_SCHEMA_DESATUALIZADO`
(linha 194) — cuja mensagem, ironicamente, é "Atualize o banco com `make
migrate`", exatamente o que o operador acabou de fazer.

Pior: `preview` e `_motivo_inelegivel` usam `get_by_venda`, que retorna `None`
quando o schema é tido como ausente. Isso significa "venda ainda não fechada", e
não "não sei" — então a UI apresenta vendas já fechadas como elegíveis.

Why it matters:
Transforma um erro de operação recuperável (esqueci de migrar) em um estado
travado que só um restart resolve, com uma mensagem de erro que aponta para a
ação errada.

Concrete fix suggestion:
Só cachear o resultado positivo — a tabela pode passar a existir, mas nunca
desaparece em operação normal:

```python
disponivel = inspector.has_table(...) and inspector.has_table(...)
if disponivel:
    _SCHEMA_DISPONIVEL_POR_ENGINE[engine] = True
return disponivel
```

O custo é uma inspeção por chamada apenas enquanto o schema estiver
desatualizado — ou seja, no cenário já degradado.

---

## Falha na gravação pós-commit deixa registros apontando para arquivos inexistentes

Location: bases/xtreme_system/api/routes/ui_routes/uploads.py:58-78 e components/xtreme_system/database/core.py:144-150
Impact: Medium
Category: Error handling and logging
Estimated effort: Medium

Description:
`salvar_arquivos` cria a linha no banco e agenda a escrita em disco para depois do
commit. A execução dos callbacks engole qualquer exceção:

```python
def _invoke_post_commit(session: Session) -> None:
    callbacks = session.info.pop(_POST_COMMIT_KEY, [])
    for cb in callbacks:
        try:
            cb()
        except Exception:
            logger.warning("post_commit_callback_failed", exc_info=True)
```

Se `path.write_bytes` falhar — disco cheio, permissão, volume desmontado — a
transação já foi commitada. Sobra um `ImagemVeiculo`/`ImagemComprovanteCompra`
com `url` para um arquivo que não existe, e o usuário vê a tela de sucesso. A
única pista é um `warning` no log.

A ordem é deliberada (não gravar arquivo se o commit falhar) e está correta; o
problema é o lado sem compensação. Existe um `arquivo_disponivel`
(ui_routes/common.py:98) que a template usa para não quebrar a renderização, ou
seja, o sintoma é conhecido — mas nada reconcilia os órfãos. E `remover_orfaos`
(uploads.py:81-91) foi explicitamente esvaziado, com o comentário dizendo que a
reconciliação "deve ocorrer em um processo explícito de limpeza" — processo que
não existe no repositório.

Why it matters:
Não há erro para o usuário, nem alerta, nem caminho de recuperação. O dado fica
inconsistente e ninguém descobre até alguém tentar abrir o documento.

Concrete fix suggestion:
Duas opções, em ordem de esforço:

1. Elevar a severidade e tornar detectável: `logger.error` com `registro_id` e
   `url` no contexto, para dar um gancho de alerta.
2. Compensar: registrar a falha em uma tabela de pendências, ou marcar a linha
   com um flag `arquivo_ok=False` em uma sessão nova, para que uma rotina de
   limpeza possa remover ou reprocessar.

O mínimo útil é (1) — hoje o evento é indistinguível de ruído.

---

## `_resolver_cliente` duplicado em compras, com o helper compartilhado ao lado

Location: bases/xtreme_system/api/routes/ui_routes/compras.py:208-246 vs bases/xtreme_system/api/routes/ui_routes/common.py:112-157
Impact: Medium
Category: Code quality
Estimated effort: Low

Description:
`common.resolver_cliente` foi extraído justamente para ser compartilhado e é
parametrizado para isso (`cliente_field`, `required_msg`, `invalid_selected_msg`,
`invalid_new_msg`). `vendas.py` o importa e usa (vendas.py:25, 332).

`compras.py` mantém uma cópia privada de 38 linhas, idêntica em comportamento —
mesma leitura de `cliente_id`, mesmo `int()` protegido por `try`, mesma checagem
de CPF duplicado, mesmos dez campos `cli_*` montando o `ClienteCreate`, mesmas
mensagens de erro literais.

Why it matters:
São dois lugares para corrigir todo bug de parsing de cliente e para adicionar
todo campo novo. As duas cópias hoje concordam por acaso, não por construção —
qualquer ajuste feito em um dos fluxos de cadastro passa a divergir do outro sem
que nada acuse. E o custo de convergir é baixo justamente porque o helper já foi
parametrizado para este caso.

Concrete fix suggestion:
Apagar `compras._resolver_cliente` e usar o compartilhado — os defaults já batem
com as mensagens da cópia:

```python
from xtreme_system.api.routes.ui_routes.common import resolver_cliente
...
cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
```

`_resolver_veiculo` (compras.py:249-290) não tem equivalente compartilhado e deve
ficar onde está.

---

## `limit`/`offset` sem teto em `/auditoria`

Location: bases/xtreme_system/api/routes/json.py:352-373
Impact: Low
Category: Performance
Estimated effort: Low

Description:

```python
def listar_auditoria(..., limit: int = 50, offset: int = 0) -> list[auditoria.Auditoria]:
```

Os valores vão direto para `stmt.limit(limit).offset(offset)`
(auditoria/core.py:141), sem validação. `limit=100000000` materializa a tabela de
auditoria inteira — que é a tabela que mais cresce no sistema, já que recebe uma
linha por escrita com dois snapshots JSON completos. Valores negativos também
passam.

A rota exige `AdminUser`, o que limita bastante o alcance. Mas `dados_antes` e
`dados_depois` são JSON serializados por linha, então o custo por linha é alto e
um valor grande escolhido sem má intenção já é suficiente para derrubar o worker.

Why it matters:
Impacto contido pelo requisito de admin, mas a correção é uma linha e remove uma
forma trivial de exaurir memória.

Concrete fix suggestion:

```python
from fastapi import Query

limit: Annotated[int, Query(ge=1, le=500)] = 50,
offset: Annotated[int, Query(ge=0)] = 0,
```

O FastAPI passa a rejeitar com 422 antes de tocar no banco. Vale conferir se a UI
de auditoria (ui_routes/auditoria.py) usa os mesmos limites.

---

## Cobertura de testes concentrada na UI, com o enforcement de perfil na API quase sem teste

Location: tests/test_ui.py (2622 linhas, 74 testes) e tests/test_api_compras.py:128
Impact: Medium
Category: Testing
Estimated effort: Medium

Description:
A suíte é substancial (~190 testes) e cobre bem os fluxos HTMX. Mas a distribuição
esconde uma lacuna alinhada com o achado nº 1:

`test_api_compras.py:128` (`test_api_compras_respeita_perfil_em_leitura_e_mutacao`)
é o único teste que verifica perfil na API JSON — e cobre justamente a única
entidade cujas rotas foram escritas à mão com essa checagem. Nenhum teste
equivalente existe para `/veiculos`, `/vendas`, `/clientes`, `/investidores` ou
`/lancamentos-caixa`, que são exatamente as que passam por
`register_crud_routes` e não têm checagem alguma. A suíte não falha porque o
comportamento ausente nunca foi afirmado.

Secundariamente, `test_ui.py` concentra 2622 linhas — quase 40% do código de
teste em um arquivo. Isso torna difícil localizar a cobertura existente antes de
escrever um teste novo, e é um dos motivos plausíveis da lacuna acima ter
passado despercebida.

Why it matters:
A cobertura ausente é precisamente a de controle de acesso, onde um teste vale
mais do que em qualquer outro lugar: a falha é silenciosa (dado a mais na
resposta, não exceção) e não aparece em uso normal.

Concrete fix suggestion:
Um teste parametrizado sobre as rotas geradas pela factory, que falha hoje e
passa a valer como especificação depois da correção do nº 1:

```python
@pytest.mark.parametrize(
    ("rota", "campo"),
    [("/veiculos", "preco"), ("/vendas", "valor_venda")],
)
def test_api_oculta_campos_restritos_por_perfil(client, funcionario_sem_campo, rota, campo):
    resp = client.get(rota, headers=auth_header(funcionario_sem_campo))
    assert resp.status_code == 200
    assert all(campo not in item for item in resp.json())
```

Sobre `test_ui.py`: dividir por domínio (`test_ui_vendas.py`, `test_ui_veiculos.py`,
…) espelhando `ui_routes/`. É mecânico e de baixo risco, mas só vale como
follow-up — não antes do teste de permissão acima.
