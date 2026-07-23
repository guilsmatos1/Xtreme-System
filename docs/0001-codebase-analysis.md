# Análise de codebase — 10 oportunidades de melhoria

Escopo analisado: `bases/xtreme_system/api/`, `components/xtreme_system/`, `tests/`,
configuração de CI e build. Ordenado do maior para o menor impacto.

---

## Denylist de campos da API JSON divergiu de `perfil.CAMPOS_PROTEGIDOS` e vaza campos sensíveis

Location: bases/xtreme_system/api/routes/json.py:141-153 e :306-311; components/xtreme_system/perfil/core.py:24-80
Impact: High
Category: Architecture and design (separation of concerns / duplicated source of truth)
Estimated effort: Medium

Description:
`perfil.CAMPOS_PROTEGIDOS["veiculos"]` declara 17 campos ocultáveis, incluindo
`marca`, `chassi`, `renavam`, `proprietario_registrado`, `debitos` e
`tempo_estoque`. A tupla `campos_protegidos` passada para
`register_crud_routes(..., "/veiculos", ...)` lista apenas 11 e **não inclui**
`marca`, `chassi`, `renavam` nem `proprietario_registrado`. Como
`VeiculoRead` expõe todos esses campos, um perfil que marca `chassi` como oculto
continua recebendo o chassi em `GET /veiculos` e `GET /veiculos/{id}`.

O mesmo padrão aparece em compras: `_compra_json` (json.py:306) filtra somente
`valor_compra` e `debitos`, enquanto `CAMPOS_PROTEGIDOS["compras"]` define 10
campos ocultáveis (`documento_cliente`, `placa`, `observacoes`, `usuario`, …).

A causa raiz é estrutural: a lista de campos protegidos existe hoje em pelo
menos quatro lugares independentes por página — `CAMPOS_PROTEGIDOS`,
`campos_protegidos` (JSON), `csv_fields` (exportação) e `campos_form_map`
(escrita na UI). Nada força os quatro a concordarem.

Why it matters:
É uma falha de autorização silenciosa: a UI esconde o campo, o admin acredita
que o perfil não tem acesso, e a mesma informação sai pela API JSON com o mesmo
token de cookie/Bearer. E, por ser divergência de listas literais, ela reaparece
toda vez que alguém adiciona um campo novo.

Concrete fix suggestion:
Derivar as listas de `perfil.CAMPOS_PROTEGIDOS` em vez de redigitá-las, e travar
com um teste que compare as duas fontes.

Example:

```python
# bases/xtreme_system/api/routes/json.py
def _campos_da_pagina(pagina: str) -> tuple[str, ...]:
    return tuple(campo for campo, _label in perfil.CAMPOS_PROTEGIDOS[pagina])

register_crud_routes(
    app, veiculo, "/veiculos", "Veículo",
    ...,
    pagina="veiculos",
    campos_protegidos=_campos_da_pagina("veiculos"),
)
```

```python
# tests/test_api_perfil.py
def test_campos_protegidos_json_cobrem_todos_os_campos_do_perfil() -> None:
    for pagina, campos in perfil.CAMPOS_PROTEGIDOS.items():
        declarados = {c for c, _ in campos}
        assert declarados <= set(_campos_expostos_na_api(pagina))
```

---

## Rotas de escrita da API JSON não checam acesso à página; só as de leitura checam

Location: bases/xtreme_system/api/route_factories.py:120-192 (`_create`, `_update`, `_delete`, `_require_json_operacao`)
Impact: High
Category: Architecture and design (autorização inconsistente)
Estimated effort: Low

Description:
Nas rotas geradas, a leitura passa por `_json_visible` → `_require_json_page`,
que valida `perfil.pode_acessar(user, pagina)`. Já `_create`, `_update` e
`_delete` chamam apenas `_require_json_operacao`, que consulta
`perfil.pode_operacao` — e `pode_operacao` (perfil/core.py:213-221) **não
verifica se a página está em `user.perfil.paginas`**, ao contrário de
`pode_ver_campo` (perfil/core.py:200-210), que verifica.

Consequência: um perfil de quem se removeu a página `vendas` de `paginas`, mas
cujo `restricoes["vendas"]["operacoes"]` ainda contém `"excluir"`, continua
autorizado em `DELETE /vendas/{id}`. `_delete` não chama `_json_visible` em
ponto algum, então não existe nem a checagem tardia que `_create`/`_update`
acabam herdando pela serialização da resposta.

Na UI o mesmo perfil seria bloqueado, porque `get_ui_user` roda
`perfil.pagina_da_rota` + `pode_acessar` antes da dependency de operação. A
divergência é exatamente entre os dois transportes.

Why it matters:
Revogar o acesso de um perfil a uma página é a operação natural do admin, e ela
não revoga de fato as escritas pela API. Além disso, `pode_acessar` e
`pode_operacao` discordarem sobre "página não liberada" é uma armadilha para
qualquer endpoint novo.

Concrete fix suggestion:
Fazer `pode_operacao` exigir a página (alinhando com `pode_ver_campo`) e chamar
`_require_json_page` também nos caminhos de escrita.

Example:

```python
# components/xtreme_system/perfil/core.py
def pode_operacao(user: Any, pagina: str, operacao: str) -> bool:
    from xtreme_system.usuario.core import is_admin  # noqa: PLC0415

    if is_admin(user):
        return True
    if not user.perfil or pagina not in user.perfil.paginas:
        return False
    permitidas = (user.perfil.restricoes or {}).get(pagina, {}).get("operacoes", [])
    return operacao in permitidas
```

```python
# bases/xtreme_system/api/route_factories.py
def _require_json_operacao(user: usuario.Usuario, pagina: str, operacao: str) -> None:
    if usuario.is_admin(user):
        return
    _require_json_page(user, pagina)          # <- passa a checar a página
    operacoes = {op for op, _label in perfil.OPERACOES.get(pagina, [])}
    ...
```

---

## Rate limit de login é contornável porque `X-Forwarded-For` é confiado sem restrição

Location: bases/xtreme_system/api/setup.py:151-188 (`_client_ip`, `_rate_limit`)
Impact: High
Category: Error handling and logging / segurança operacional
Estimated effort: Low

Description:
`_client_ip` usa o primeiro valor de `X-Forwarded-For` sempre que o header
existe, sem verificar se a requisição veio de um proxy confiável. O bucket do
limiter de login é `f"login:{client_ip}"`, então um cliente que envia
`X-Forwarded-For: <valor aleatório>` a cada tentativa recebe um bucket novo toda
vez e o limite de 5 tentativas/minuto em `/login` e `/ui/login` deixa de existir.
O limite geral de 100 req/min tem o mesmo furo.

O `make run` sobe uvicorn com `--proxy-headers`, mas a checagem de origem do
uvicorn não protege este código: o middleware lê o header cru do `Request`.

Why it matters:
O rate limiter de login é a única defesa contra brute force de senha do sistema
(argon2 protege o hash, não o endpoint). Hoje ele só atrapalha quem não sabe
mandar um header.

Concrete fix suggestion:
Só honrar `X-Forwarded-For` quando o peer imediato estiver numa lista de proxies
confiáveis, configurável por env; caso contrário usar `request.client.host`.

Example:

```python
_TRUSTED_PROXIES = {
    ip.strip()
    for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",")
    if ip.strip()
}


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "desconhecido"
    if peer in _TRUSTED_PROXIES:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",", 1)[0].strip()
            if client_ip:
                return client_ip
    return peer
```

---

## Nenhuma rota de listagem tem paginação: tabelas inteiras carregadas e ordenadas em Python

Location: bases/xtreme_system/api/crud_ui/query.py:70-94 e :58-67; bases/xtreme_system/api/crud_ui/routes.py:228-269; components/xtreme_system/crud/core.py:14
Impact: High
Category: Performance
Estimated effort: High

Description:
`query_list` sempre termina em `module.list_all(session)` → `session.query(model).all()`,
sem `LIMIT`/`OFFSET`. A ordenação (`sorted_list`) e a filtragem (`filter_list`)
acontecem em memória, sobre a lista completa. Isso vale para veículos, vendas,
compras, clientes, custos, investidores e usuários — e também para
`GET /{prefix}` na API JSON (`route_factories.py:101-108`).

O efeito é amplificado pelos relacionamentos `lazy="selectin"` de `Venda`
(`cliente`, `veiculo`, `veiculo_troca`, `vendedor`) e de `Veiculo`
(`investidor`): listar N vendas dispara 5 queries que trazem N linhas cada, e
depois a resposta ainda é ordenada em Python. `/auditoria` é o único lugar do
código com `limit`/`offset` (auditoria/core.py:121-142), o que mostra que o
padrão paginado já é conhecido, apenas não foi aplicado.

Why it matters:
O custo é linear no tamanho da tabela para toda visualização de tela, inclusive
as parciais HTMX que recarregam a lista inteira depois de cada create/update/delete
(`register_create_route`/`register_update_route` recarregam `query_list` no fim).
Numa concessionária com histórico de alguns anos de vendas isso vira timeout de
página, não lentidão marginal.

Concrete fix suggestion:
Empurrar ordenação e recorte para o SQL, começando pelas duas telas mais
pesadas (vendas e veículos), com `page`/`per_page` na querystring.

Example:

```python
def query_list(session, module, *, q, searchable, list_func, search_func,
               search_column=None, sort=None, order="asc",
               limit=50, offset=0) -> list[EntityT]:
    stmt = module.select_all()            # novo: cada módulo devolve um Select
    if q:
        stmt = module.apply_search(stmt, q, search_column)
    if sort:
        stmt = module.apply_sort(stmt, sort, order)
    return list(session.scalars(stmt.limit(limit).offset(offset)))
```

Tradeoff: é a mudança mais invasiva da lista — muda a assinatura da fábrica CRUD
e os templates precisam de controles de página. Vale fazer por página, não de
uma vez.

---

## `except TypeError` em `query_list` engole erros reais e reexecuta a busca

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

O `try` envolve a execução inteira da função de busca, não apenas a chamada. Um
`TypeError` levantado **dentro** de `venda.search` ou `veiculo.search` (por
exemplo comparando `None` com um `Decimal`, ou um `cast` mal formado) é
interpretado como "essa função não aceita `column`" e a busca é executada uma
segunda vez, agora sem a coluna. O usuário recebe silenciosamente resultados
errados em vez de um erro, e a query roda duas vezes.

Why it matters:
É um bug que se disfarça de funcionalidade: o sintoma é "a busca por coluna às
vezes ignora a coluna", sem nenhum log, e o `logger` do módulo nem é usado aqui.

Concrete fix suggestion:
Decidir a assinatura por introspecção, fora do bloco de execução — ou
simplesmente padronizar todas as `search_func` para aceitarem `column`.

Example:

```python
import inspect

if q and search_func is not None:
    aceita_column = "column" in inspect.signature(search_func).parameters
    if aceita_column:
        return list(search_func(session, q, column=search_column))
    return list(search_func(session, q))
```

---

## Mapa campo→input duplicado por página, em desacordo com a fábrica que já recebe o mesmo mapa

Location: bases/xtreme_system/api/routes/ui_routes/vendas.py:104-128 vs :249-266; bases/xtreme_system/api/routes/ui_routes/compras.py:84-100 vs :453-461
Impact: Medium
Category: Code quality (duplicação)
Estimated effort: Low

Description:
Em `vendas.py`, o dicionário `campos_form_map` aparece duas vezes com conteúdo
literalmente idêntico (16 entradas): uma dentro de `_filtrar_campos_ocultos_venda`,
usada pelas rotas manuais `_criar_venda`/`_atualizar_venda`, e outra passada
para `register_crud_ui_routes`, usada por `register_update_route`
(crud_ui/routes.py:513-517), que executa exatamente o mesmo laço. `compras.py`
repete a estrutura com 7 entradas. `veiculos.py:44-61` mantém uma terceira
variante (`_CAMPO_FORM_MAP`).

Why it matters:
Adicionar um campo protegido novo exige lembrar de duas cópias por página. Se só
uma for atualizada, o filtro de campos ocultos passa a valer na edição pela
fábrica mas não na criação manual (ou vice-versa) — e a diferença não aparece em
nenhum teste, porque as duas cópias hoje coincidem.

Concrete fix suggestion:
Definir o mapa uma vez por módulo de rota e reusá-lo nos dois pontos.

Example:

```python
# vendas.py
_CAMPOS_FORM_VENDA = {
    "cliente": "cliente_id",
    ...
}


def _filtrar_campos_ocultos_venda(user, data):
    for campo, campo_form in _CAMPOS_FORM_VENDA.items():
        if not perfil.pode_ver_campo(user, "vendas", campo):
            data.pop(campo_form, None)
    return data


register_crud_ui_routes(..., campos_form_map=_CAMPOS_FORM_VENDA)
```

---

## Contexto das listas refaz consultas já feitas e carrega tabelas inteiras só para obter ids

Location: bases/xtreme_system/api/routes/ui_routes/vendas.py:139-141; bases/xtreme_system/api/routes/ui_routes/veiculos.py:64-75 e :102-113
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
Dois casos concretos:

1. `_ctx_lista_vendas` chama `fechamento_venda.list_all(session)` a cada
   renderização da lista de vendas — inclusive nas parciais HTMX após criar,
   editar ou excluir. `FechamentoVenda` tem `venda`, `usuario` e `participacoes`
   com `lazy="selectin"`, e `Venda` por sua vez tem quatro `selectin`; carregar
   todos os fechamentos para montar um `dict {venda_id: fechamento}` traz a
   árvore inteira quando bastaria `venda_id` + o id do fechamento.

2. `_ctx_form_veiculo` faz `veiculo.list_all(session)` **apenas para extrair os
   ids** e passar a `compra.latest_by_veiculo_ids`. Abrir o formulário de um
   veículo carrega todos os veículos com seus investidores.

3. Na listagem de veículos, `compra.latest_by_veiculo_ids` é chamada duas vezes
   sobre o mesmo conjunto: em `_preparar_veiculos_lista` (:102) e de novo em
   `_ctx_lista_veiculos` (:87).

Why it matters:
São multiplicadores do problema de paginação acima, mas com correção barata e
isolada — não dependem de refatorar a fábrica.

Concrete fix suggestion:
Selecionar só as colunas necessárias e reaproveitar o resultado já computado.

Example:

```python
# vendas.py
def _ctx_lista_vendas(session: Session, vendas: list[Any]) -> dict[str, Any]:
    ids = [v.id for v in vendas]
    rows = session.query(
        fechamento_venda.FechamentoVenda.venda_id,
        fechamento_venda.FechamentoVenda.id,
    ).filter(fechamento_venda.FechamentoVenda.venda_id.in_(ids)).all()
    return {"fechamentos_by_venda": dict(rows)}
```

```python
# veiculos.py — resolve os ids sem materializar os objetos
ids = [row[0] for row in session.query(veiculo.Veiculo.id).all()]
```

---

## Restore de banco roda de forma síncrona no thread da requisição, com o dump inteiro em memória

Location: components/xtreme_system/exportacao/core.py:45-110; bases/xtreme_system/api/routes/ui_routes/configuracoes.py:30-34 e :256-289
Impact: Medium
Category: Maintainability / risco operacional
Estimated effort: Medium

Description:
`POST /ui/configuracoes/importar` lê o upload inteiro (`arquivo.file.read()`),
chama `_fechar_transacao_da_rota` — que faz `expunge` + `rollback` + `close` na
sessão da request e depois **continua usando essa mesma sessão** para
`whatsapp.get_config(session)` e `empresa.get_config(session)` — e executa
`pg_restore --clean --if-exists --single-transaction` no processo da API.

Três problemas concretos:
- `--clean` derruba e recria todos os objetos do banco enquanto os outros
  workers seguem servindo requisições com conexões abertas; não há lock,
  drenagem, nem modo manutenção.
- `dump_database()` mantém o dump completo em `result.stdout` e depois na
  resposta HTTP; `_salvar_backup_pre_restore` gera um segundo dump em memória
  antes do restore. Para um banco de alguns GB isso é OOM no container.
- Um restore demorado bloqueia o worker além de qualquer timeout de proxy, e o
  cliente não recebe progresso nem confirmação confiável.

Why it matters:
É a operação mais destrutiva do sistema e a menos protegida. Um restore
interrompido por timeout de gateway deixa o operador sem saber se o banco foi
restaurado.

Concrete fix suggestion:
Como passo mínimo, fazer streaming em vez de bufferizar, e exigir confirmação
explícita. Como passo seguinte, mover dump/restore para um job fora do processo
que atende HTTP.

Example:

```python
def dump_database_para(path: Path) -> None:
    cmd = ["pg_dump", *_pg_args(), "-Fc", "-Z", "6", "-f", str(path)]
    result = subprocess.run(cmd, env=_pg_env(), capture_output=True, check=False)
    if result.returncode != 0:
        raise ExportacaoError(result.stderr.decode() or "pg_dump falhou")
# e responder com FileResponse(path) em vez de Response(content=dump)
```

---

## `register_crud_ui_routes` em `route_factories.py` é um repasse que duplica uma assinatura de 40 parâmetros

Location: bases/xtreme_system/api/route_factories.py:217-299
Impact: Medium
Category: Maintainability
Estimated effort: Low

Description:
A função declara 40 parâmetros e o corpo inteiro é `_register_crud_ui_routes_impl(...)`
repassando cada um deles, sem adicionar nenhum comportamento. `register_ui_simples`
(:195-214) é o mesmo caso. Na prática, todo parâmetro novo da fábrica precisa ser
escrito três vezes: na declaração do wrapper, na chamada do wrapper e na
implementação real em `crud_ui/routes.py`.

O módulo também mantém aliases puramente cosméticos (`_sort_key = sort_key`,
`_csv_response = csv_response`), com `vendas.py` importando `_sort_key` — um
nome privado — de outro módulo.

Why it matters:
Não é preferência de estilo: é a superfície onde parâmetros novos se perdem
silenciosamente. Um parâmetro esquecido no repasse vira `None`/default sem erro
de tipo, e o efeito aparece como "a restrição de perfil não pegou nessa página".

Concrete fix suggestion:
Reexportar a implementação em vez de reescrever a assinatura.

Example:

```python
# bases/xtreme_system/api/route_factories.py
from xtreme_system.api.crud_ui.routes import register_crud_ui_routes
from xtreme_system.api.crud_ui.simple import register_ui_simples
from xtreme_system.api.crud_ui.query import sort_key

__all__ = ["register_crud_routes", "register_crud_ui_routes",
           "register_ui_simples", "sort_key"]
```

E trocar `from ... import _sort_key` por `sort_key` nos módulos de rota.

---

## Testes de rota nunca exercitam o commit/rollback de `get_session`

Location: tests/conftest.py:85-91; components/xtreme_system/database/core.py:212-222
Impact: Medium
Category: Testing
Estimated effort: Medium

Description:
O override de sessão usado por praticamente todos os testes de rota é:

```python
def override() -> Iterator[Session]:
    yield session
    if invoke_post_commit:
        _invoke_post_commit(session)
```

Ele não faz `commit()`, não faz `rollback()` e não propaga exceção pelo mesmo
caminho que `get_session`. Ou seja: a semântica transacional real da aplicação —
commit ao final de toda request, rollback centralizado no `except`, disparo de
`_invoke_post_commit` só após commit bem-sucedido, descarte dos callbacks em
`after_rollback` — não é coberta pelos ~200 testes de rota.

Só `tests/test_route_factories_atomicity.py` (3 testes) monta um override com
`rollback`, e mesmo assim sem `commit`. Isso é exatamente a área que o
`CLAUDE.md` sinaliza como delicada ("Rollback é centralizado em `get_session()`;
não chame `session.rollback()` nesse caminho"), e é onde estão os handlers de
`IntegrityError` que decidem entre `rollback_integrity_error_response` e deixar o
`get_session` cuidar.

Why it matters:
Os bugs mais caros desse desenho — escrita parcial commitada, callback
post-commit disparado após rollback, arquivo de contrato órfão no disco — são
invisíveis para a suíte atual por construção, não por falta de casos.

Concrete fix suggestion:
Fazer o override espelhar `get_session` e adicionar um teste por caminho.

Example:

```python
def override() -> Iterator[Session]:
    try:
        yield session
        session.commit()
        _invoke_post_commit(session)
    except Exception:
        session.rollback()
        raise
```

```python
def test_falha_apos_criar_venda_nao_deixa_contrato_no_disco(make_client, tmp_path):
    # força erro depois de _persistir_contrato_venda e assere que o PDF sumiu
    ...
```

Tradeoff: ligar o commit real provavelmente quebra testes que hoje dependem de
enxergar objetos não commitados na mesma sessão. Vale migrar por arquivo, não de
uma vez.
