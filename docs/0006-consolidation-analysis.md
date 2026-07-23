# Análise de Consolidação — Xtreme Motors

Dez oportunidades de unificar código duplicado sem perder comportamento, ordenadas por
risco de duplicação × blast radius, descontado o custo de migração.

Todas as propostas são **behavior-preserving**: onde as cópias divergem, a divergência está
declarada e o destino unificado preserva a união dos comportamentos.

---

## Cinco implementações paralelas de `search(session, term, column)`

Type: parallel implementation
Sites:
- components/xtreme_system/veiculo/core.py:163
- components/xtreme_system/venda/core.py:216
- components/xtreme_system/compra/core.py:160
- components/xtreme_system/custo_veiculo/core.py:86
- components/xtreme_system/cliente/core.py:160 (`_search_com_vinculo`)
Layer: component
Duplication risk: High
Blast radius: as 5 telas de listagem com busca (`/ui/veiculos`, `/ui/vendas`, `/ui/compras`,
`/ui/custos-veiculos`, `/ui/clientes` + compradores/vendedores), o export CSV de cada uma
(`register_export_route`) e `query_list` em `crud_ui/query.py:70`
Estimated effort: Medium
Behavior change: none (required) — cada componente continua declarando o próprio
`columns_map` e a própria lista de colunas do modo "todas"; só o motor de montagem da query
passa a ser um.

What is duplicated:
A mesma regra de busca textual, escrita cinco vezes: montar `pattern = f"%{term}%"`,
consultar um `columns_map: dict[str, InstrumentedAttribute]`, e então
(a) se `column` está no mapa, filtrar só nela com `cast(col, String).ilike(pattern)`;
(b) senão, filtrar com `or_(...)` sobre um conjunto fixo de colunas padrão.

Differences between the copies:
- `veiculo.search`: sem `join`, sem `.distinct()`. `columns_map` com 16 entradas, incluindo
  `"investidor": Veiculo.investidor` — um **relacionamento**, não uma coluna; `cast(rel, String)`
  não é a mesma coisa que as demais entradas.
- `venda.search` e `compra.search`: `join(Cliente)` + `join(Veiculo)` explícitos e `.distinct()`
  nos dois ramos.
- `custo_veiculo.search`: **não faz join** com `Veiculo`, mas o ramo "todas as colunas" filtra
  por `Veiculo.modelo` / `Veiculo.placa`, e o `columns_map` expõe `"veiculo"` e `"placa"`
  apontando para colunas de `Veiculo`. Sem join isso vira produto cartesiano implícito, e sem
  `.distinct()` as linhas repetem. Comportamento diferente das outras quatro cópias.
- `cliente._search_com_vinculo`: retorna a `Query` (não `list`), para que
  `search_compradores` / `search_vendedores` encadeiem `.join(Venda)` / `.join(Compra)` depois.
  O `columns_map` é um módulo-level `_COLUNAS_BUSCA` em vez de um local.
- Ramo "todas as colunas": conjuntos diferentes por componente (3 colunas em `veiculo`,
  6 em `venda`, 5 em `compra`, 4 em `custo_veiculo`, 4 em `cliente`).

Proposed consolidation:
Criar em `components/xtreme_system/crud/core.py` — que já é o brick de helpers CRUD
compartilhados — uma função:

```python
def aplicar_busca(query, term, column, columns_map, colunas_padrao, *, distinct=False):
```

que devolve a `Query` filtrada. Cada `core.py` continua dono do seu `columns_map`, do seu
`colunas_padrao` e do seu `join`; passa a `Query` já montada e recebe a `Query` filtrada.
`search()` de cada componente vira 5–8 linhas. `cliente` chama sem `.all()` (mantendo o retorno
`Query`); os outros quatro fazem `list(... .all())` como hoje.

How functionality is preserved:
Nenhum `columns_map` muda. `distinct=True` só em `venda` e `compra` (as únicas que usam hoje).
O join de `custo_veiculo` **continua ausente** — o helper não adiciona join nenhum, então a
consulta gerada é a mesma de hoje, bug incluído. Corrigir o join é uma mudança de
comportamento separada e não faz parte desta consolidação; está registrada em `## Riscos`.
A entrada `"investidor": Veiculo.investidor` continua sendo passada e sofrendo `cast(...)`
exatamente como hoje.

Verification:
- `tests/test_ui.py` — os testes de busca por coluna e busca livre de veículos, vendas,
  compras, custos e clientes devem continuar passando sem alteração.
- `tests/test_route_factories_ui.py:429` (`register_crud_ui_routes` com `search_func`) cobre o
  caminho `query_list` → `search_func(session, q, column=...)`.
- Novo teste necessário: pinar que `custo_veiculo.search(session, termo)` produz hoje o mesmo
  conjunto de resultados antes e depois — é a única cópia sem join e a mais fácil de mudar
  sem querer.

---

## `campos_form_map` declarado duas vezes por página e o loop de filtro escrito três vezes

Type: literal duplication
Sites:
- bases/xtreme_system/api/routes/ui_routes/vendas.py:107 (dict dentro de `_filtrar_campos_ocultos_venda`)
- bases/xtreme_system/api/routes/ui_routes/vendas.py:252 (`campos_form_map=` passado à fábrica)
- bases/xtreme_system/api/routes/ui_routes/compras.py:87 (dict dentro de `_filtrar_campos_ocultos_compra`)
- bases/xtreme_system/api/routes/ui_routes/compras.py:453 (`campos_form_map=` passado à fábrica)
- bases/xtreme_system/api/crud_ui/routes.py:513 (o loop, dentro de `register_update_route`)
Layer: cross-layer (rota + fábrica)
Duplication risk: High
Blast radius: toda escrita em `/ui/vendas` e `/ui/compras` (criar e atualizar) para perfis
não-admin; é a barreira que impede um perfil de gravar campo que ele não pode ver
Estimated effort: Low
Behavior change: none (required) — o mesmo dict passa a existir uma vez e a ser consumido pelos
dois caminhos (rota manual de create e fábrica de update), sem alterar chaves nem a ordem
das checagens.

What is duplicated:
O mapa `campo interno → nome do input HTML` de vendas (16 pares) e de compras (7 pares), cada um
escrito duas vezes no mesmo arquivo; e o loop
`for campo, campo_form in map.items(): if not perfil.pode_ver_campo(user, pagina, campo): data.pop(campo_form, None)`,
escrito três vezes.

Differences between the copies:
- vendas.py:107 vs vendas.py:252 — **os 16 pares são idênticos**; só a ordem difere
  (`cliente, veiculo, data_venda, ...` na função vs `cliente, veiculo, data_venda, ...` na
  fábrica — mesma ordem, de fato byte-idêntico como conteúdo de dict).
- compras.py:87 vs compras.py:453 — **os 7 pares são idênticos**, mesma ordem.
- O loop em `crud_ui/routes.py:513` é guardado por `if pagina and campos_form_map:`; os loops em
  `_filtrar_campos_ocultos_venda` / `_compra` não têm guarda porque `pagina` é literal
  (`"vendas"` / `"compras"`). Fora isso, corpo idêntico.
- `custos_veiculos.py:97` passa `campos_form_map={"valor": "valor"}` e **não** tem função
  espelho — só o caminho da fábrica. Não é sítio duplicado, é o caso já correto.

Proposed consolidation:
Em cada módulo, promover o dict a constante de módulo (`_CAMPOS_FORM_VENDA`,
`_CAMPOS_FORM_COMPRA`) e usá-la nos dois pontos: na chamada `campos_form_map=` e dentro da
função de filtro. Extrair o loop para uma função em `crud_ui/routes.py` (ou em
`ui_routes/common.py`, se preferir não importar a fábrica nas rotas):

```python
def remover_campos_ocultos(user, pagina, dados, campos_form_map) -> dict[str, Any]:
```

`register_update_route` passa a chamá-la mantendo a guarda `if pagina and campos_form_map:`;
`_filtrar_campos_ocultos_venda` / `_compra` viram uma linha cada, ou desaparecem.

How functionality is preserved:
Mesmas chaves, mesma `pagina`, mesma chamada a `perfil.pode_ver_campo`, mesmo `data.pop(..., None)`.
A guarda da fábrica continua na fábrica; as rotas manuais continuam sem guarda porque sempre
passam `pagina` literal. Nenhum campo passa a ser removido ou preservado que não fosse antes.

Verification:
- `tests/test_ui.py` — testes de perfil com `campos_ocultos` em vendas e compras que checam que
  o campo oculto não é gravado nem no create manual nem no update pela fábrica.
- `tests/test_perfil.py` — cobertura de `pode_ver_campo`.
- Novo teste necessário: um teste que afirme
  `_CAMPOS_FORM_VENDA` é o mesmo objeto passado em `campos_form_map=`, para que os dois pontos
  não voltem a divergir silenciosamente.

---

## Cinco fluxos de anexo (modal + upload + excluir) reescritos por entidade

Type: near duplication
Sites:
- bases/xtreme_system/api/routes/ui_routes/veiculos_imagens.py:38 (modal), :77 (upload), :119 (excluir)
- bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py:31, :68, :95
- bases/xtreme_system/api/routes/ui_routes/veiculos_procuracao.py:37, :74, :101
- bases/xtreme_system/api/routes/ui_routes/clientes.py:116, :149, :181
- bases/xtreme_system/api/routes/ui_routes/compras.py:136, :174, :202
Layer: route
Duplication risk: High
Blast radius: 15 endpoints HTMX; toda a gestão de imagens de veículo, documento de veículo,
procuração, documento de cliente e comprovante de compra
Estimated effort: Medium
Behavior change: none (required) — a divergência de `actor_id` em `clientes.py:193` é preservada
explicitamente (ver abaixo) até que se decida corrigi-la como mudança própria.

What is duplicated:
A tríade completa, por entidade:
1. `_X_modal(request, session, user, fk_id, erro=None, *, action_oob=False)` — busca o dono,
   chama `remover_orfaos(...)`, e devolve `TemplateResponse` com
   `{dono, user, erro, action_oob, pending_upload_paths(session)}`, com
   `status_code=400 if erro else 200`.
2. rota POST de upload — `_found(dono)`, `_validar_uploads(arquivos)`, retorna o modal com erro,
   senão `salvar_arquivos(session, upload_dir=..., url_prefix=..., create_fn=..., schema=...,
   fk_field=..., fk_id=..., arquivos=..., actor_id=user.id)`, e devolve o modal com `action_oob=True`.
3. rota POST de excluir — `_found(anexo)`, checa `anexo.<fk> != fk_id` → `HTTPException(404)`,
   `modulo.delete(...)`, `_uploaded_file_path(url)` → `_remover_upload(path)`, devolve o modal
   com `action_oob=True`.

Differences between the copies:
- **`clientes.py:193` chama `imagem_documento_cliente.delete(session, doc)` sem `user.id`.** As
  outras quatro passam `actor_id`. Consequência: a exclusão de documento de cliente entra na
  auditoria com `usuario_id` nulo. Divergência real, e é a razão pela qual esta consolidação
  não pode ser feita "no olho".
- `veiculos_imagens.py` é o único que **não** aceita `erro` como parâmetro do modal: monta um
  `TemplateResponse` separado no upload (linhas 89–104), duplicando o contexto, e injeta
  `pode_enviar_imagens` / `pode_excluir_imagens` no contexto em vez de deixar o template chamar
  `pode_operacao(user, ...)` como fazem procuração, clientes e compras. Também **não** passa
  `user` no contexto do modal.
- `veiculos_documentos.py` usa uma única dependency (`upload_documento`) para abrir, enviar e
  excluir; imagens e procuração usam três (`abrir_*`, `enviar_*`, `excluir_*`); compras usa três
  (`abrir_comprovante`, `enviar_comprovante`, `excluir_comprovante`); clientes usa uma
  (`excluir_documento`) só no excluir.
- `compras.py:136` busca a lista de comprovantes por consulta (`list_by_compra`) e a consulta
  **duas vezes** (linhas 146 e 148, em torno de `remover_orfaos`); os outros quatro leem uma
  relação do ORM e chamam `session.refresh(item)`.
- Posição de `session.info["usuario_id"] = user.id`: no topo do handler em veículos/imagens/
  documentos/procuração/clientes, no meio em compras (linhas 187, 215). Irrelevante — ver o
  item "Atribuição morta de `session.info`" abaixo.
- `_uploads_dir(...)` vs `_uploads_procuracao_dir(...)` vs `_uploads_compra_dir(...)` vs
  `_uploads_cliente_dir(...)`, e o `url_prefix` correspondente.

Proposed consolidation:
Criar `bases/xtreme_system/api/routes/ui_routes/anexos.py` com um registrador:

```python
def register_anexo_routes(
    app, *, prefix, segmento, dono_get, dono_label, modulo, schema, fk_field,
    template, contexto_key, colecao, upload_dir, url_prefix, campo_form,
    dep_abrir, dep_enviar, dep_excluir, ctx_extra=lambda user: {},
    passar_actor_no_delete=True,
) -> None
```

Os cinco módulos passam a ser uma chamada de configuração cada. `ctx_extra` cobre o
`pode_enviar_imagens` / `pode_excluir_imagens` de imagens; `passar_actor_no_delete` cobre a
divergência de clientes.

How functionality is preserved:
- Cada módulo mantém suas próprias dependencies — quem usava uma continua com uma, quem usava
  três continua com três; o registrador só recebe os três slots e o chamador repete a mesma
  dependency onde hoje ela é repetida.
- `passar_actor_no_delete=False` **só** para clientes, preservando literalmente o
  `delete(session, doc)` sem actor de hoje. A união dos comportamentos é mantida: nenhum
  registro de auditoria muda de conteúdo.
- `ctx_extra` para imagens injeta as duas flags e omite `user`, reproduzindo o contexto atual
  daquele template; os outros quatro passam `user` como hoje.
- O caminho de erro de upload de imagens (que hoje devolve 400 com um contexto próprio, sem
  `remover_orfaos`) é reproduzido pelo mesmo `erro=` + `status_code=400 if erro else 200`; a
  diferença observável (imagens não roda `remover_orfaos` no ramo de erro) precisa ser
  reproduzida por uma flag `limpar_orfaos_no_erro=False` para imagens, ou aceita como mudança —
  e nesse caso deve ser declarada.

Verification:
- `tests/test_uploads.py` inteiro (28 testes) — `salvar_arquivos`, `remover_orfaos`,
  `_validar_uploads`, `_uploaded_file_path`.
- `tests/test_ui.py` — testes de modal de imagens, documentos, procuração, documentos de cliente
  e comprovantes de compra, incluindo os 404 de anexo pertencente a outro dono.
- Novo teste necessário: um teste de auditoria que pina que excluir documento de cliente grava
  `usuario_id = None` hoje — sem ele, a consolidação "consertaria" o bug silenciosamente e
  quebraria a promessa de preservação.

---

## `register_create_route` e `register_update_route` são o mesmo handler duas vezes

Type: near duplication
Sites:
- bases/xtreme_system/api/crud_ui/routes.py:371 (`register_create_route` / `_criar`)
- bases/xtreme_system/api/crud_ui/routes.py:477 (`register_update_route` / `_atualizar`)
Layer: route (fábrica)
Duplication risk: High
Blast radius: todas as telas geradas pela fábrica — veículos, clientes, compras, vendas,
custos-veículos, além do `register_ui_simples`
Estimated effort: Medium
Behavior change: none (required) — a divergência do `user=` faltante é preservada ou corrigida
por decisão explícita, não por efeito colateral.

What is duplicated:
Dentro dos dois handlers, o mesmo esqueleto:
`form = await request.form()` → `parse_form` → `schema.model_validate` + `run_hook(before_*)`
→ `except ValidationError` devolvendo `error_response(..., erro="Dados inválidos", status_code=400)`
→ `except HTTPException as exc` devolvendo `error_response(..., erro=str(exc.detail), status_code=400)`
→ `try: <write>_with_hook(...)` / `except IntegrityError` devolvendo
`rollback_integrity_error_response(session, lambda: conflict_form_response(..., erro=write_conflict_detail(label)))`
→ `query_list(session, module, q="", searchable=..., list_func=..., search_func=...)`
→ `ok_response(templates, request, ok_partial_template, user=user, list_key=..., lista=lista, ctx_list=ctx_list(session, lista))`.

Além disso, o bloco `query_list(session, module, q="", searchable=searchable, list_func=list_func,
search_func=search_func)` aparece **quatro vezes** no arquivo: linhas 458, 560, 611 e 635.

Differences between the copies:
- `_atualizar` começa com `obj = _found(module.get(session, item_id), label)` e passa `item=obj`
  em todos os `error_response` / `conflict_form_response`; `_criar` passa `item=None`.
- `_atualizar` aplica o filtro de `campos_form_map` sobre `dados_form` antes de validar
  (linhas 513–516); `_criar` não aplica.
- `_criar` tem um `except IntegrityError` **a mais**, em volta da validação + `before_create`
  (linhas 429–441), que `_atualizar` não tem em volta de `before_update`.
- **Nesse `except` extra (linha 432), `conflict_form_response` é chamado sem `user=user`.**
  As outras duas chamadas de conflito (linhas 447 e 549) passam `user=user`. Como
  `form_response` só injeta `"user"` no contexto quando `user is not None`
  (`crud_ui/responses.py:39`), esse caminho renderiza o formulário **sem `user`** — os templates
  que chamam `pode_operacao(user, ...)` recebem `Undefined` nesse 409 específico.
- `_criar` usa `dep = cadastrar_dep or require_ui_admin`; `_atualizar` usa
  `dep = editar_dep or require_ui_admin`.

Proposed consolidation:
Extrair, no mesmo arquivo, duas funções privadas:

```python
def _lista_atual(session, module, *, searchable, list_func, search_func): ...
def _form_erro(templates, request, form_template, *, ctx_form, item_key, item, user, erro, status_code): ...
```

`_lista_atual` substitui as quatro cópias de `query_list(..., q="")`. `_form_erro` substitui os
quatro `error_response` de `ValidationError`/`HTTPException`. O esqueleto restante
(`try/validate/hook/except/write/except/lista/ok`) vira uma corrotina auxiliar
`_processar_escrita(...)` parametrizada por `item`, `schema`, `write_fn` e `pre_validate`
(o filtro de `campos_form_map`, que só `_atualizar` passa).

How functionality is preserved:
- `item=None` vs `item=obj` continua sendo argumento do chamador.
- O `except IntegrityError` extra de `_criar` continua existindo só em `_criar`, passado como
  flag ou mantido no chamador — `_atualizar` não ganha esse caminho.
- **Decisão explícita necessária sobre o `user=` faltante na linha 432**: a consolidação deve
  passar `user=None` naquele ponto para manter o comportamento atual, e a correção
  (`user=user`) deve ser um commit separado com teste próprio. Escolher `user=user` durante a
  refatoração é mudança de comportamento e viola a premissa desta análise.
- `dep` continua resolvido no `register_*_route` correspondente.

Verification:
- `tests/test_route_factories_ui.py` inteiro — cobre criar, atualizar, excluir, conflito de
  integridade e rollback tardio (`test_register_ui_simples_rolls_back_when_write_fails_late`).
- `tests/test_route_factories_atomicity.py` — atomicidade dos hooks.
- Novo teste necessário: um teste que force `IntegrityError` **durante `before_create`** e
  afirme que o HTML de 409 resultante é renderizado sem `user` no contexto. Sem ele, a
  divergência da linha 432 desaparece na consolidação e ninguém percebe.

---

## Seis bricks de anexo com o mesmo model, os mesmos schemas e o mesmo CRUD

Type: near duplication
Sites:
- components/xtreme_system/imagem_veiculo/core.py:11
- components/xtreme_system/documento_veiculo/core.py:11
- components/xtreme_system/documento_procuracao/core.py:11
- components/xtreme_system/imagem_comprovante_venda/core.py:11
- components/xtreme_system/imagem_comprovante_compra/core.py:11
- components/xtreme_system/imagem_documento_cliente/core.py:11
Layer: component
Duplication risk: Medium
Blast radius: 6 bricks, ~390 linhas; consumidos pelas 5 rotas de anexo e por `veiculo`/`cliente`/
`compra`/`venda` via relacionamento
Estimated effort: Medium
Behavior change: none (required) — `__tablename__`, nomes de classe, nomes de FK e schemas
públicos permanecem exatamente os mesmos; só o corpo repetido some.

What is duplicated:
Os seis arquivos têm a mesma estrutura, linha a linha:
`class X(Base)` com `id`, `<fk>_id: Mapped[int] = mapped_column(ForeignKey("<t>.id", ondelete="CASCADE"), index=True)`, `url: Mapped[str]`;
`XCreate(BaseModel)` com `<fk>_id: int` e `url: str`;
`XRead(BaseModel)` com `model_config = ConfigDict(from_attributes=True)`, `id`, `<fk>_id`, `url`;
e `list_all` / `list_by_<fk>` / `get` / `create` / `delete` delegando a `crud.*`.

Differences between the copies:
- `XUpdate(BaseModel)` com `url: str | None = None` e a função `update()` existem em
  `imagem_veiculo`, `documento_veiculo` e `imagem_documento_cliente`; **não existem** em
  `documento_procuracao`, `imagem_comprovante_venda` e `imagem_comprovante_compra`.
- `imagem_comprovante_compra` tem um `list_by_compra_ids(session, compra_ids)` a mais
  (linhas 44–54), com `if not compra_ids: return []` e
  `.order_by(compra_id, id)` — nenhuma das outras cinco tem equivalente.
- Nome do parâmetro de `get`: `imagem_id` em quatro, `documento_id` em `documento_veiculo` e
  `documento_procuracao`. Posicional em todos os chamadores — irrelevante em runtime, relevante
  para quem chama por keyword.
- Docstring de módulo: uma linha, textualmente diferente em cada.
- Fora isso: byte-idêntico módulo os nomes.

Proposed consolidation:
Em `components/xtreme_system/crud/core.py`, adicionar um mixin declarativo e uma fábrica de
schemas:

```python
class AnexoMixin:                       # id + url, sem __tablename__ e sem FK
def anexo_schemas(nome, fk_field): ...  # devolve (Create, Read) — e (Update,) sob demanda
```

Cada `core.py` de anexo passa a declarar apenas `__tablename__`, a FK e a linha
`class X(AnexoMixin, Base)`, e a montar seus schemas pela fábrica. As funções `list_all` / `get` /
`create` / `update` / `delete` continuam existindo em cada módulo (são a API pública do brick,
usada como `CrudModule` pelas fábricas de rota) mas viram one-liners como já são.

How functionality is preserved:
- `__tablename__` e o nome da coluna FK são declarados no próprio módulo — nenhuma migration é
  afetada, nenhum índice muda.
- `XUpdate` e `update()` continuam existindo **só nos três** módulos que os têm hoje. Adicionar
  aos outros três seria ampliar a API pública sem pedido — fora de escopo.
- `list_by_compra_ids` fica onde está, em `imagem_comprovante_compra`.
- Os nomes de parâmetro (`imagem_id` / `documento_id`) são preservados por módulo.

Verification:
- `tests/test_uploads.py` e `tests/test_ui.py` — todos os fluxos de anexo.
- `tests/test_migrations.py` — garante que o schema gerado continua batendo com as migrations;
  é o teste decisivo aqui, porque um mixin mal declarado muda a ordem/tipo de coluna.
- Novo teste necessário: nenhum. `test_migrations.py` já pina exatamente o que esta mudança
  poderia quebrar.

---

## `/compras` JSON é uma reimplementação manual de `register_crud_routes`

Type: parallel implementation
Sites:
- bases/xtreme_system/api/routes/json.py:306 (`_compra_json`) vs bases/xtreme_system/api/route_factories.py:54 (`_json_visible`)
- bases/xtreme_system/api/routes/json.py:314 (`_require_compra_operacao`) vs bases/xtreme_system/api/route_factories.py:75 (`_require_json_operacao`)
- bases/xtreme_system/api/routes/json.py:319–373 (os 5 handlers) vs bases/xtreme_system/api/route_factories.py:84 (`register_crud_routes`)
Layer: route
Duplication risk: Medium
Blast radius: 5 endpoints JSON de compras (`GET`, `GET/{id}`, `POST`, `PATCH`, `DELETE`)
Estimated effort: Medium
Behavior change: none (required) — apenas os dois helpers são unificados; os handlers continuam
manuais, preservando as três divergências listadas abaixo.

What is duplicated:
`_compra_json` refaz o que `_json_visible` faz: `jsonable_encoder(ReadSchema.model_validate(obj))`
seguido de `for campo in perfil.CAMPOS_PROTEGIDOS[pagina]: if not pode_ver_campo: data.pop(campo, None)`.
`_require_compra_operacao` refaz o que `_require_json_operacao` faz: checar
`perfil.pode_operacao(user, pagina, operacao)` e levantar `HTTPException(403, "Operação não permitida")`.
Os handlers refazem o `_found` + `before_*` + `_safe_write(conflict_msg=f"{label} já existe")` +
`except IntegrityError → 409 "{label} possui veículos vinculados"` da fábrica.

Differences between the copies:
- `_compra_json` **não** chama `_require_json_page(user, "compras")`. `_json_visible` chama
  sempre que `pagina is not None`. Ou seja: hoje um usuário com perfil que não inclui a página
  `compras` consegue ler `GET /compras`; pela fábrica receberia 403.
- `_compra_json` não aceita `campos` extra (o `campos_protegidos` da fábrica); usa só
  `perfil.CAMPOS_PROTEGIDOS["compras"]`.
- `_require_compra_operacao` **não** tem o early-return `if usuario.is_admin(user): return` nem a
  checagem `operacao in {op for op, _ in perfil.OPERACOES[pagina]}`. Na prática o admin passa
  igual (`perfil.pode_operacao` já retorna `True` para admin em `perfil/core.py:216`), mas para
  um não-admin cujo perfil libere uma operação **não declarada** em `OPERACOES["compras"]`, a
  versão de `json.py` permite e a da fábrica nega.
- `criar_compra` faz `data.usuario_id = user.id` inline; a fábrica faria via `actor_field="usuario_id"`.
- Mensagem de conflito no delete: `"Compra possui veículos vinculados"` literal vs
  `f"{label} possui veículos vinculados"` — idêntico para `label="Compra"`.

Proposed consolidation:
Quebrar `_json_visible` em duas partes em `route_factories.py`:

```python
def filtrar_campos_visiveis(obj, user, pagina, campos, read_schema) -> dict[str, Any]   # sem checar página
def _json_visible(obj, user, pagina, campos, read_schema):                              # _require_json_page + filtrar_...
```

`json.py` passa a chamar `filtrar_campos_visiveis(obj, user, "compras", (), compra.CompraRead)`
no lugar de `_compra_json`, e `_require_compra_operacao` continua como está.

How functionality is preserved:
`filtrar_campos_visiveis` não checa acesso à página — exatamente como `_compra_json` hoje. O
403 de página continua ausente em `/compras` e continua presente nas rotas geradas pela fábrica.
`_require_compra_operacao` fica intacto, preservando a ausência do filtro por `OPERACOES`.
Nenhum status code, mensagem ou campo do payload muda.

Verification:
- `tests/test_api_compras.py` inteiro.
- `tests/test_api_perfil.py` — filtragem de campos por perfil nas rotas JSON geradas pela fábrica.
- Novo teste necessário: um teste afirmando que `GET /compras` com um usuário não-admin **sem**
  a página `compras` no perfil retorna 200 (o comportamento de hoje). É o que impede a
  consolidação de introduzir o 403 sem querer.

---

## `route_factories` reexporta `crud_ui` repetindo assinaturas de 40 parâmetros

Type: redundant layer
Sites:
- bases/xtreme_system/api/route_factories.py:221 (`register_crud_ui_routes`) vs bases/xtreme_system/api/crud_ui/routes.py:58
- bases/xtreme_system/api/route_factories.py:199 (`register_ui_simples`) vs bases/xtreme_system/api/crud_ui/simple.py:19
- bases/xtreme_system/api/route_factories.py:44 (`_sort_key = sort_key`) e :45 (`_csv_response = csv_response`)
Layer: route
Duplication risk: Medium
Blast radius: 5 módulos importam `register_crud_ui_routes` de `route_factories`; 8 importam
`_sort_key` / `_csv_response` de lá
Estimated effort: Low
Behavior change: none (required) — são aliases e repasses posicionais/nomeados idênticos; trocar
o import não muda nada em runtime.

What is duplicated:
`route_factories.register_crud_ui_routes` (linhas 221–303) declara os **mesmos 40 parâmetros**
com os **mesmos defaults** de `crud_ui/routes.register_crud_ui_routes` (linhas 58–99), e o corpo
inteiro é um repasse 1:1 para `_register_crud_ui_routes_impl`. `register_ui_simples`
(linhas 199–218) faz o mesmo para `crud_ui/simple.register_ui_simples`.
`_sort_key` e `_csv_response` são apenas outros nomes para `crud_ui.query.sort_key` e
`crud_ui.responses.csv_response`.

Differences between the copies:
Nenhuma. Assinatura, defaults e ordem de argumentos são byte-idênticos entre
`route_factories.py:221–262` e `crud_ui/routes.py:58–99`. O repasse não filtra, não valida e não
transforma nada.

Adicionalmente: `register_ui_simples` **não tem nenhum chamador de produção** — o único uso é
`tests/test_route_factories_ui.py:64` e `:144`, que testam `crud_ui/simple.py` através do alias.

Proposed consolidation:
1. Trocar, nos 5 módulos, `from xtreme_system.api.route_factories import register_crud_ui_routes`
   por `from xtreme_system.api.crud_ui.routes import register_crud_ui_routes`; apagar as
   linhas 221–303 de `route_factories.py`.
2. Trocar `_sort_key` → `sort_key` (de `crud_ui.query`) e `_csv_response` → `csv_response`
   (de `crud_ui.responses`) nos 8 módulos; apagar as linhas 44–45.
3. `register_ui_simples`: apontar `tests/test_route_factories_ui.py` para
   `crud_ui.simple.register_ui_simples` e apagar as linhas 199–218. Não apagar
   `crud_ui/simple.py` — é o teste que depende dela, e código morto pré-existente não é escopo
   desta consolidação (ver `## Riscos`).

`route_factories.py` fica com o que é realmente seu: `register_crud_routes` e os helpers JSON.

How functionality is preserved:
Só imports mudam. Nenhuma rota é registrada de forma diferente; a função chamada ao final é
literalmente a mesma objeto-função de hoje.

Verification:
- `tests/test_route_factories_ui.py` e `tests/test_route_factories_atomicity.py` — precisam dos
  imports atualizados e devem passar sem mais nenhuma alteração.
- `uv run pytest` completo — um import quebrado aparece na coleta.
- Novo teste necessário: nenhum. É uma mudança puramente de import, e a suíte inteira é a
  verificação.

---

## Cinco modais de anexo em Jinja, ~90% idênticos

Type: template duplication
Sites:
- bases/xtreme_system/api/templates/_modal_imagens_veiculo.html:1
- bases/xtreme_system/api/templates/_modal_documentos_veiculo.html:1
- bases/xtreme_system/api/templates/_modal_procuracao_veiculo.html:1
- bases/xtreme_system/api/templates/_modal_documentos_cliente.html:1
- bases/xtreme_system/api/templates/_modal_comprovantes_compra.html:1
Layer: template
Duplication risk: Medium
Blast radius: 5 modais, ~320 linhas de HTML; toda mudança visual ou de acessibilidade em anexo
precisa hoje de 5 edições
Estimated effort: Medium
Behavior change: none (required) — o HTML renderizado para cada modal permanece idêntico,
inclusive os `aria-label`, os textos e os `id` de título.

What is duplicated:
Praticamente o arquivo inteiro: `modal` → `modal__panel` → `modal__head` com contador
`mmgr__count` e botão de fechar → `modal__body` com `{% if erro %}{{ ui.alert(erro) }}{% endif %}`
→ grid `mmgr__grid` com, por item, o trio thumb+`<dialog class="image-preview">` / link
`mmgr__doc` de PDF / `mmgr__doc--missing` guardado por `arquivo_disponivel(url, pending_upload_paths)`
→ botão `mmgr__del` → bloco `{% else %}{{ ui.empty(...) }}` → `<form class="mmgr__upload">` com
`mmgr__drop`, o mesmo `onchange` inline de contagem de arquivos e o mesmo botão de submit →
`{% if action_oob %}{% set ... %}{% include "_action_*.html" %}{% endif %}`.

Differences between the copies:
- `_modal_imagens_veiculo.html` **não** tem o ramo `is_imagem` / PDF: só imagem ou "Indisponível"
  (linhas 17–31). Os outros quatro têm os três ramos.
- Guarda do botão de excluir: `pode_excluir_imagens` (variável de contexto) em imagens;
  `pode_operacao(user, 'veiculos', 'excluir_procuracao')` em procuração;
  `pode_operacao(user, 'clientes', 'excluir_documento')` em clientes;
  `pode_operacao(user, 'compras', 'excluir_comprovante')` em compras;
  **nenhuma guarda** em `_modal_documentos_veiculo.html:39`.
- Guarda do formulário de upload: `pode_enviar_imagens` / `pode_operacao(... 'enviar_procuracao')` /
  `pode_operacao(... 'enviar_comprovante')`; **sem guarda** em documentos de veículo e documentos
  de cliente.
- `accept` do input: `.jpg,.jpeg,.png,.webp` em imagens; `.pdf,.jpg,.jpeg,.png,.webp` nos outros
  quatro. `name` do input: `imagens` / `documentos` / `documentos` / `documentos` / `comprovantes`.
- Fonte da coleção: `veiculo.imagens` / `veiculo.documentos` / `veiculo.documentos_procuracao` /
  `cliente.documentos` / `comprovantes` (variável avulsa, não relação).
- `_modal_comprovantes_compra.html` é o único cujo bloco `action_oob` tem
  `{% set has_comprovantes = comprovantes %}` e uma guarda `pode_operacao(... 'abrir_comprovante')`
  em torno do `include`.

Proposed consolidation:
Adicionar a `_macros.html` um macro `anexos(...)` recebendo:
`itens`, `titulo`, `modal_id`, `url_base`, `campo`, `accept`, `hint`, `label_singular`,
`pode_enviar`, `pode_excluir`, `permitir_pdf`, `empty_icon`, `empty_titulo`, `empty_texto`.
Os cinco templates viram ~10 linhas: `{% import %}`, a chamada do macro e o bloco `action_oob`
próprio (que permanece em cada arquivo, porque o `include` e os `set` diferem).

How functionality is preserved:
- `permitir_pdf=False` só em imagens, reproduzindo a ausência do ramo PDF.
- `pode_enviar` / `pode_excluir` são **valores booleanos calculados pelo chamador**: cada template
  passa exatamente a expressão que usa hoje, e `True` onde hoje não há guarda (documentos de
  veículo, documentos de cliente). Nenhum botão aparece ou some.
- `accept`, `name`, `hint` e os textos de `ui.empty` vêm por parâmetro, com os valores atuais.
- O bloco `action_oob` fica fora do macro, então a guarda extra de comprovantes é preservada.

Verification:
- `tests/test_ui.py` — os testes que afirmam presença/ausência dos botões de enviar e excluir
  por perfil em cada um dos cinco modais.
- Novo teste necessário: um teste por modal afirmando que o botão de excluir **aparece** em
  `_modal_documentos_veiculo.html` para um perfil não-admin sem `excluir_documento` — é o
  comportamento atual (sem guarda) e o mais fácil de perder ao unificar.

---

## Atribuição morta de `session.info["usuario_id"]` em 44 handlers

Type: dead-by-duplication
Sites (a atribuição efetiva vive em bases/xtreme_system/api/deps.py:34, `_bind_usuario`):
- bases/xtreme_system/api/routes/json.py:77, :93, :105, :213
- bases/xtreme_system/api/routes/ui_routes/usuarios.py:109, :134, :158, :186, :233
- bases/xtreme_system/api/routes/ui_routes/vendas.py:351, :402, :449, :495
- bases/xtreme_system/api/routes/ui_routes/compras.py:187, :215, :291
- bases/xtreme_system/api/routes/ui_routes/veiculos_imagens.py:73, :85, :127
- bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py:64, :76, :103
- bases/xtreme_system/api/routes/ui_routes/veiculos_procuracao.py:70, :82, :109
- bases/xtreme_system/api/routes/ui_routes/veiculos_cliente_vendedor.py:77, :89, :120
- bases/xtreme_system/api/routes/ui_routes/investidores.py:190, :244, :275
- bases/xtreme_system/api/routes/ui_routes/perfis.py:97, :141, :174
- bases/xtreme_system/api/routes/ui_routes/lancamentos.py:159, :180, :203
- bases/xtreme_system/api/routes/ui_routes/veiculos.py:287, :366
- bases/xtreme_system/api/routes/ui_routes/clientes.py:166, :192
- bases/xtreme_system/api/routes/ui_routes/conta.py:47
Layer: route
Duplication risk: Low
Blast radius: 44 linhas em 14 arquivos; nenhuma mudança de comportamento esperada
Estimated effort: Low
Behavior change: none (required) — a atribuição já ocorre antes, na dependency de autenticação;
as 44 cópias reescrevem o mesmo valor.

What is duplicated:
`session.info["usuario_id"] = user.id` (ou `admin.id` / `current.id`), repetido no corpo de 44
handlers. `deps.py:34` já faz exatamente isso dentro de `_bind_usuario`, chamado no `return` de
`get_current_user` (`deps.py:63`) e de `get_ui_user` (`deps.py:110`).

Differences between the copies:
- Nome da variável: `user.id` em 40 sítios; `admin.id` em json.py:77, :105, :213; `current.id`
  em json.py:93.
- Posição: primeira linha do handler na maioria; depois do `_found(...)` em json.py:92–93,
  :104–105, :212–213 e compras.py:182–187, :210–215; dentro do `try` em vendas.py:495.
- Fora isso, byte-idêntico.

Toda dependency usada por esses handlers desemboca em `get_current_user` ou `get_ui_user`:
`CurrentUser` → `get_current_user`; `AdminUser` → `require_admin(user: CurrentUser)`;
`UIUser` → `get_ui_user`; `UIAdmin` → `require_ui_admin(user: UIUser)`;
`require_operacao(...)` → `_dep(user: UIUser)` (`deps.py:129`). Todas recebem a **mesma**
`SessionDep` do handler e executam antes do corpo. Logo `session.info["usuario_id"]` já está
preenchido com o mesmo `id` quando a linha duplicada roda.

Proposed consolidation:
Apagar as 44 linhas. Nenhum código novo.

How functionality is preserved:
`_bind_usuario` continua sendo o único ponto de escrita, e escreve o mesmo valor no mesmo
objeto de sessão antes de o handler começar. `components/xtreme_system/auditoria/core.py:20`
documenta `session.info['usuario_id']` como pré-requisito das escritas auditadas — o
pré-requisito continua satisfeito pela dependency.

Verification:
- `tests/test_auditoria.py` e `tests/test_crud.py` — pinam que `usuario_id` chega na tabela
  `auditoria` a partir de `session.info`.
- `tests/test_api_auth.py:65` e `:93` — afirmam explicitamente que `db_session.info["usuario_id"]`
  está preenchido após autenticar. São exatamente o teste desta consolidação.
- `tests/test_ui.py` — os testes de auditoria por tela cobrem os handlers UI.
- Novo teste necessário: nenhum. `test_api_auth.py:65`/`:93` já pinam a garantia da dependency.

---

## `_ok_*` / `_erro_*` reimplementam `ok_response` / `error_response`

Type: reimplemented helper
Sites:
- bases/xtreme_system/api/routes/ui_routes/vendas.py:273 (`_ok_venda`)
- bases/xtreme_system/api/routes/ui_routes/vendas.py:284 (`_erro_venda`)
- bases/xtreme_system/api/routes/ui_routes/vendas.py:501 (bloco inline, ramo de erro do fechamento)
- bases/xtreme_system/api/routes/ui_routes/vendas.py:513 (bloco inline, cópia literal de `_ok_venda`)
- bases/xtreme_system/api/routes/ui_routes/compras.py:267 (`_erro_compra`)
- bases/xtreme_system/api/routes/ui_routes/compras.py:278 (`_ok_compra`)
- helpers existentes: bases/xtreme_system/api/crud_ui/responses.py:147 (`ok_response`) e :51 (`error_response`)
Layer: route
Duplication risk: Low
Blast radius: os caminhos manuais de criar/atualizar venda, criar compra e fechar venda
Estimated effort: Low
Behavior change: none (required) — os helpers montam o contexto na mesma ordem e com as mesmas
chaves; os `status_code` são passados explicitamente.

What is duplicated:
`_ok_venda` monta `{"user": user, "vendas": vendas, **_ctx_lista_vendas(session, vendas)}` —
que é literalmente o que `ok_response(..., user=user, list_key="vendas", lista=vendas,
ctx_list=_ctx_lista_vendas(session, vendas))` produz (`responses.py:160`).
`_ok_compra` idem com `list_key="compras"` e `ctx_list={}`.
`_erro_venda` monta `{**_ctx_form_venda(session), "venda": venda_obj, "user": user, "erro": msg}`
com `status_code=400` — que é `error_response(..., ctx_form=_ctx_form_venda(session),
item_key="venda", item=venda_obj, user=user, erro=msg, status_code=400)` (`responses.py:63` →
`form_response` em `responses.py:38`). `_erro_compra` idem com `item_key="compra"`, `item=None`.
Além disso, vendas.py:513–518 é uma cópia literal do corpo de `_ok_venda`, a 240 linhas de
distância dele.

Differences between the copies:
- `_ok_compra` **não** inclui `_ctx_lista_compras(session, compras)` no contexto (portanto não
  passa `comprovantes_por_compra`), enquanto o caminho da fábrica passa. Divergência real: o
  parcial `_compras_ok.html` renderizado logo após criar uma compra não recebe os comprovantes.
- `_erro_venda` aceita `venda_obj` opcional; `_erro_compra` sempre passa `None`.
- vendas.py:513–518 vs `_ok_venda` (linhas 273–281): byte-idêntico no corpo.
- vendas.py:501–512 monta o contexto de `_modal_fechamento_venda.html` com as mesmas 5 chaves de
  vendas.py:465–475 e vendas.py:529–539, diferindo em `preview`, `fechamento`, `erro` e
  `status_code`.

Proposed consolidation:
1. `_ok_venda` e `_ok_compra` passam a delegar a `ok_response`; `_erro_venda` e `_erro_compra`
   a `error_response`. Continuam existindo como funções nomeadas (encapsulam o `ctx_form` /
   `ctx_list` da página) — só o corpo encolhe para uma chamada.
2. Substituir o bloco de vendas.py:513–518 por `return _ok_venda(request, session, user)`.
3. Extrair em vendas.py um `_modal_fechamento(request, venda_obj, user, *, preview, fechamento,
   erro=None, status_code=200)` e usá-lo nos três pontos (465, 501, 529).

How functionality is preserved:
- `_ok_compra` continua passando `ctx_list={}` — a ausência de `comprovantes_por_compra` é
  mantida. Passar `_ctx_lista_compras` seria mudança de comportamento e fica fora deste item.
- `form_response` só injeta `"user"` quando `user is not None` e `"erro"` quando `erro is not None`;
  os quatro chamadores sempre passam ambos, então o contexto resultante é idêntico.
- Ordem das chaves no dict de contexto é irrelevante para o Jinja, e mesmo assim `ok_response`
  usa `{"user": ..., list_key: ..., **ctx_list}` — a mesma ordem de `_ok_venda`.

Verification:
- `tests/test_ui.py` — criar/atualizar venda (sucesso e erro de validação), criar compra,
  fechar venda (sucesso e erro), detalhe de fechamento.
- `tests/test_fechamento_venda.py` — o modal de fechamento nos três estados.
- Novo teste necessário: um teste afirmando que o HTML devolvido por `POST /ui/compras` (sucesso)
  **não** contém marcação de comprovante — pinando a divergência de `_ok_compra` antes de ela
  virar um "conserto" acidental.

---

## Descartados

- **`ui.moeda` reimplementado inline em 20 pontos** (`_row_venda.html:27–29`, `_row_veiculo.html:11,23`,
  `_linhas_investidores.html:11–13`, `veiculo_detalhe.html:39,45,102,145`, e mais 8) — duplicação real
  do macro em `_macros.html:146`, esforço baixíssimo, mas risco e blast radius menores que os dez
  acima; fica como próximo item da fila, não como descarte definitivo.
- **Bloco de toolbar de busca em Jinja, 5 cópias** (`clientes.html:31`, `compras.html:32`,
  `custos_veiculos.html:39`, `veiculos.html:59`, `vendas.html:33`) — idêntico módulo o prefixo da
  rota, o `id` do toolbar e o `aria-label`; candidato claro a macro, abaixo do corte por ser
  puramente apresentacional.
- **10 arquivos `_*_ok.html` de uma linha** — todos `{% with oob=True %}{% include "_linhas_X.html" %}{% endwith %}`;
  consolidar exigiria mudar o contrato `ok_partial_template` da fábrica para receber
  `list_partial_template` + `oob=True` no contexto, o que é mais mudança do que economia.
- **`_validate_venda_update` duplicado** em `json.py:262` e `vendas.py:131` — mesma regra, mas os
  dois arquivos não têm dependência entre si e mover para `routes/workflows.py` cruzaria a fronteira
  UI/JSON por 4 linhas; abaixo do corte.
- **`ordenar_investidores`** (`investidores.py:43–84`) — 5 ramos `sorted(...)` quase idênticos,
  colapsáveis num dict `sort → attr`; contido em uma única função, blast radius mínimo.
- **`if request.headers.get("HX-Request")` em 7 pontos** (`auditoria.py:138`, `relatorios.py:87`,
  `lancamentos.py:89`, `usuarios.py:66`, `investidores.py:135`, `crud_ui/routes.py:252`,
  `crud_ui/simple.py:66`) — padrão idiomático de HTMX de 3 linhas; extrair um helper trocaria
  duplicação por indireção sem ganho claro.
- **`_login` / `_login_ui` / `_login_admin` em 4 arquivos de teste** (`test_configuracoes_backup.py:20`,
  `test_relatorio_dre.py:241`, `test_venda_regerar_contrato.py:26`, `test_ui.py:1718`) — repetição
  intencional de setup de teste; dois deles afirmam `status_code == 200` e dois não, e unificar
  acoplaria arquivos de teste hoje independentes.
- **`_ctx_form_venda` vs `_ctx_form_compra`** — parecem irmãos, mas montam listas diferentes
  (`veiculos_disponiveis` + `veiculos_troca` vs `investidores` + `tipo_entradas`). Semelhança
  coincidental de formato, não duplicação.
- **`sort_key` (`crud_ui/query.py:18`) vs `_filter_repr` (`crud_ui/query.py:33`)** — compartilham
  as três linhas de `getattr(value, "value", value)` / `hasattr(value, "nome")`, mas divergem no
  contrato de saída (chave de ordenação tipada vs string lowercase para `in`); unificar exigiria
  um parâmetro de modo e deixaria as duas piores.
- **`imagem_comprovante_compra.list_by_compra_ids` vs os `list_by_*` simples** — só o de compras
  tem versão em lote com `order_by`; não é cópia, é uma otimização de N+1 que os outros não
  receberam.

## Riscos

- **`custo_veiculo.search` sem join** (item 1): consolidar o motor de busca torna óbvio que essa
  cópia filtra por colunas de `Veiculo` sem `join` nem `.distinct()`. Resista à tentação de
  "consertar junto" — o conjunto de resultados mudaria. Pine o comportamento atual num teste,
  consolide, e trate o join como mudança separada.
- **`conflict_form_response` sem `user=`** (item 4, `crud_ui/routes.py:432`): ao unificar
  `_criar` e `_atualizar`, o caminho natural é passar `user=user` nos três pontos. Isso muda o
  contexto renderizado naquele 409 específico. Escolha deliberada e testada, ou preserve
  `user=None`.
- **`actor_id` ausente em `clientes.py:193`** (item 3): o registrador de anexos vai querer passar
  `user.id` em todos os cinco. Se passar, a auditoria de exclusão de documento de cliente muda de
  `usuario_id=None` para o id real. É provavelmente o comportamento desejado — mas é mudança, e
  precisa de commit e teste próprios.
- **Checagem de página ausente em `GET /compras`** (item 6): unificar com `_json_visible` sem
  cuidado adiciona um 403 para usuários sem a página `compras` no perfil. Pode ser correto do
  ponto de vista de segurança; não é behavior-preserving.
- **Guardas de permissão ausentes em `_modal_documentos_veiculo.html`** (item 8): o botão de
  excluir e o formulário de upload não têm `pode_operacao`. Ao parametrizar o macro, o default
  precisa ser `True` para esse template, ou usuários perdem acesso a um botão que hoje veem.
- **`register_ui_simples` e `crud_ui/simple.py`** (item 7): sem chamador de produção, sustentados
  apenas por `tests/test_route_factories_ui.py`. Remover o alias em `route_factories.py` é seguro;
  remover `crud_ui/simple.py` seria apagar código morto pré-existente — fora do escopo desta
  análise, e vale confirmar com o dono do repositório antes.
