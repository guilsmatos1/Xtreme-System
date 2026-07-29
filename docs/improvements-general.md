# Improvement opportunities

- **Generated:** 2026-07-29T18:02:34-03:00
- **Source analysis timestamp:** 2026-07-29T17:12:31-03:00
- **Total:** 10

## imp-20260729-001 — Unificar colunas de tabela e CSV em ColumnSpec

- **Impact:** High
- **Category:** Maintainability
- **Estimated effort:** High
- **Priority:** high
- **Risk level:** medium
- **Tags:** crud-ui, csv, templates, deduplication
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/routes/ui_routes/clientes.py`
  - `bases/xtreme_system/api/templates/_linhas_clientes.html`
  - `bases/xtreme_system/api/templates/_row_cliente.html`
- **Related opportunities:** imp-20260729-002

### Location

`bases/xtreme_system/api/routes/ui_routes/clientes.py:269-280` — `_register_clientes_page`

```python
        export=CrudUIExportConfig[cliente.Cliente](
            csv_filename=csv_filename,
            csv_headers=["ID", "Nome", "CPF", "Telefone", "Tipo", "Cidade", "Estado"],
            csv_row=lambda c: [
                c.id,
                c.nome,
                c.documento,
                c.telefone or "",
                c.tipo.value,
                c.cidade or "",
                c.estado or "",
            ],
```

### Description

As colunas exportadas são declaradas em CrudUIExportConfig enquanto as colunas visíveis permanecem em partials de tabela, criando duas definições independentes de ordem, rótulo e valor.

### Why it matters

Mudanças de coluna podem deixar a tela e o CSV divergentes sem erro detectável, multiplicando manutenção por entidade.

### Concrete fix

Criar um ColumnSpec com chave, rótulo, acesso ao valor, visibilidade e opções de exportação; derivar dele tanto o contexto da tabela quanto csv_headers e csv_row.

### Self-critique

- **Confidence:** 9.0/10
- **Uncertain:** No
- **Strengths:**
  - A declaração paralela do CSV foi verificada no código atual.
  - Os partials de linhas e linha de cliente existem no workspace.
- **Weaknesses:**
  - A solução exigirá preservar a permissão granular por campo já aplicada nos templates.
- **Suggested checks:**
  - Prototipar primeiro em clientes e comparar HTML e CSV por teste de integração.

## imp-20260729-002 — Declarar formatadores HTML e exportação por coluna

- **Impact:** High
- **Category:** Maintainability
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** crud-ui, formatters, jinja, csv
- **Files affected:**
  - `bases/xtreme_system/api/templates/_macros.html`
  - `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260729-001

### Location

`bases/xtreme_system/api/templates/_macros.html:87-98` — `status_badge`

```jinja
{% macro status_badge(status) -%}
{%- if status.value == "disponivel" -%}
  <span class="badge badge--success badge--plain">Disponível</span>
{%- elif status.value == "vendido" -%}
  <span class="badge badge--info badge--plain">Vendido</span>
{%- elif status.value == "reservado" -%}
  <span class="badge badge--warning badge--plain">Reservado</span>
{%- else -%}
  <span class="badge badge--plain">{{ status.value }}</span>
{%- endif -%}
{%- endmacro %}
```

### Description

Formatadores de status, tipo, ação, papel e moeda vivem como macros Jinja chamadas diretamente por templates de entidade, sem um registro por coluna nem uma variante explícita para exportação.

### Why it matters

A formatação fica acoplada aos partials de cada entidade e tende a ser repetida ou ficar inconsistente entre HTML e CSV.

### Concrete fix

Adicionar formatadores HTML e de exportação ao ColumnSpec, mantendo as macros atuais como renderizadores reutilizáveis e permitindo texto puro no CSV.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - As macros e usos em templates foram verificados.
- **Weaknesses:**
  - A redução exata de partials depende de diferenças específicas entre as entidades.
- **Suggested checks:**
  - Inventariar os formatos usados nos partials antes de fechar a interface do formatter.

## imp-20260729-003 — Gerar campos simples de formulários por configuração

- **Impact:** High
- **Category:** Architecture and design
- **Estimated effort:** High
- **Priority:** high
- **Risk level:** high
- **Tags:** crud-ui, forms, jinja, declarative-ui
- **Files affected:**
  - `bases/xtreme_system/api/templates/_form_venda.html`
  - `bases/xtreme_system/api/templates/_form_compra.html`
  - `bases/xtreme_system/api/templates/_form_veiculo.html`
  - `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260729-004

### Location

`bases/xtreme_system/api/templates/_form_venda.html:1-12` — function not specified

```jinja
{% import "_macros.html" as ui %}
{% set dados = dados or {} %}
<div class="modal" onclick="if(event.target===this)closeModalOnBackdrop(this)">
  <div class="modal__panel{% if not venda %} modal__panel--wizard{% endif %}" role="dialog" aria-modal="true" aria-labelledby="mv-title">
    <div class="modal__head">
      <h3 id="mv-title">{{ 'Editar venda' if venda else 'Nova venda' }}</h3>
      <button class="icon-btn" type="button" aria-label="Fechar"
              onclick="closeModalOnBackdrop(this.closest('.modal'))">{{ ui.icon("close") }}</button>
    </div>
    <form hx-post="/ui/vendas{% if venda %}/{{ venda.id }}{% endif %}" hx-target="#modal" hx-swap="innerHTML"
          {% if not venda %}id="form-nova-venda"{% endif %}>
      <div class="modal__body">
```

### Description

Os formulários de venda, compra e veículo são templates manuais extensos; o formulário de venda verificado possui 498 linhas e 23.239 bytes.

### Why it matters

Campos simples, mensagens, atributos HTMX e estrutura visual precisam ser mantidos repetidamente, elevando o custo e o risco de inconsistência em alterações de formulário.

### Concrete fix

Introduzir form_columns, form_sections, form_widget_overrides e depends_on no CRUD UI; migrar primeiro somente campos simples e preservar blocos customizados para os fluxos complexos.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Tamanho e existência dos três formulários foram verificados.
  - A migração incremental reduz o risco da mudança.
- **Weaknesses:**
  - Não foi feito inventário completo dos widgets e comportamentos especiais.
- **Suggested checks:**
  - Classificar campos simples e customizados de um formulário piloto antes de definir toda a API.

## imp-20260729-004 — Adicionar busca paginada para selects de chaves estrangeiras

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** performance, forms, foreign-key, pagination
- **Files affected:**
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/templates/_form_venda.html`
  - `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260729-003

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:80-90` — `_ctx_form_venda`

```python
def _ctx_form_venda(session: Session) -> dict[str, Any]:
    veiculos = veiculo.list_all(session)
    veiculos_disponiveis = [
        v for v in veiculos if v.status == veiculo.StatusVeiculo.disponivel
    ]
    return {
        "clientes": cliente.list_all(session),
        "veiculos": veiculos_disponiveis,
        "veiculos_troca": veiculos,
        "status": list(venda.StatusVenda),
        "tipos": list(cliente.TipoCliente),
```

### Description

A abertura do formulário de venda chama list_all para clientes e veículos e filtra os veículos disponíveis em memória.

### Why it matters

Tempo de consulta, memória e tamanho do HTML crescem junto com a base, degradando uma interação frequente.

### Concrete fix

Criar endpoint de busca paginada por modelo/campo e configurar cliente_id e veiculo_id como referências AJAX com page_size limitado e filtro server-side.

### Potential savings

Evita carregar e renderizar todos os clientes e veículos a cada abertura do formulário de venda; o custo passa de linear no total cadastrado para uma página pequena por busca.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - As chamadas list_all e o filtro em memória foram verificados diretamente.
- **Weaknesses:**
  - Não foram medidos volumes atuais nem latência de produção.
- **Suggested checks:**
  - Adicionar benchmark com base representativa e teste de paginação.

## imp-20260729-005 — Centralizar respostas HTMX de toast e modal

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** htmx, responses, toast, modal
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/responses.py`
- **Related opportunities:** imp-20260729-006, imp-20260729-007

### Location

`bases/xtreme_system/api/crud_ui/responses.py:28-39` — `form_response`

```python
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    *,
    ctx_form: dict[str, Any],
    item_key: str,
    item: EntityT | None,
    user: object = None,
    erro: str | None = None,
    dados: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
```

### Description

responses.py centraliza CSV e respostas de formulário/listagem, mas não oferece helpers específicos para toast e modal ou headers de controle HTMX.

### Why it matters

Rotas customizadas precisam montar respostas e contexto de feedback repetidamente, aumentando divergência de comportamento e apresentação.

### Concrete fix

Adicionar toast_response e modal_response com parâmetros explícitos para mensagem, tipo, refresh/redirect, título, corpo, ações e tamanho, preservando compatibilidade com os swaps OOB atuais.

### Self-critique

- **Confidence:** 8.0/10
- **Uncertain:** No
- **Strengths:**
  - A superfície atual de responses.py foi verificada.
- **Weaknesses:**
  - A quantidade exata de rotas beneficiadas não foi contada.
  - O snippet mostra a resposta existente, não todas as montagens manuais de modal.
- **Suggested checks:**
  - Migrar duas rotas representativas antes de estabilizar a assinatura dos helpers.

## imp-20260729-006 — Declarar ações de linha e confirmações

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** crud-ui, row-actions, confirmation, htmx
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/templates/_action_cliente_documentos.html`
  - `bases/xtreme_system/api/templates/_action_veiculo_imagens.html`
- **Related opportunities:** imp-20260729-005, imp-20260729-007

### Location

`bases/xtreme_system/api/crud_ui/routes.py:661-672` — `_excluir`

```python
    @app.post(f"{prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        try:
            delete_with_hook(module, session, obj, before_delete, user.id)
        except IntegrityError:
```

### Description

Ações específicas são representadas por partials fixos, e a exclusão tenta a operação antes de apresentar conflitos, sem um modelo declarativo de ação e confirmação rica.

### Why it matters

Cada entidade precisa manter marcação e comportamento de ações manualmente; operações destrutivas têm menor previsibilidade para o usuário.

### Concrete fix

Criar RowActionSpec com label, ícone, método/URL HTMX, target e configuração de confirmação; renderizar as ações pelo CRUD UI e permitir conteúdo de confirmação derivado da entidade.

### Self-critique

- **Confidence:** 8.0/10
- **Uncertain:** No
- **Strengths:**
  - O fluxo de exclusão e os partials citados existem no código atual.
- **Weaknesses:**
  - Nem toda ação de linha necessariamente se adapta ao mesmo contrato declarativo.
- **Suggested checks:**
  - Separar ações simples de ações com corpo customizado no desenho da API.

## imp-20260729-007 — Adicionar seleção múltipla e ações em lote

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** High
- **Priority:** medium
- **Risk level:** high
- **Tags:** crud-ui, bulk-actions, selection, export
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/templates`
- **Related opportunities:** imp-20260729-005, imp-20260729-006

### Location

`bases/xtreme_system/api/crud_ui/routes.py:328-339` — `register_export_route`

```python
def register_export_route(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    listing: ListingSpec[EntityT],
    csv_filename: str,
    csv_headers: list[str],
    csv_row: CsvRow[EntityT],
    csv_fields: list[str | None] | None = None,
    pagina: str | None = None,
) -> None:
```

### Description

A infraestrutura de listagem/exportação não recebe IDs selecionados nem uma configuração de ações em lote; as ocorrências atuais de checkbox são campos de formulários, não seleção de linhas.

### Why it matters

Usuários precisam operar registros individualmente e não conseguem exportar somente uma seleção, excluir vários itens ou atualizar estados em lote.

### Concrete fix

Adicionar seleção por linha e selecionar tudo da página, BulkActionSpec com autorização e confirmação, e suporte opcional a IDs selecionados no exportador.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - A assinatura do exportador foi verificada.
  - A busca limitada confirmou que checkboxes atuais pertencem a formulários.
- **Weaknesses:**
  - A semântica de selecionar todas as páginas exige definir snapshot de filtro e limites operacionais.
- **Suggested checks:**
  - Começar com seleção da página atual e exportação selecionada antes de ações mutáveis.

## imp-20260729-008 — Preservar erros de validação por campo e de domínio

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** validation, forms, pydantic, error-handling
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/crud_ui/responses.py`
  - `bases/xtreme_system/api/crud_types.py`
- **Related opportunities:** imp-20260729-009

### Location

`bases/xtreme_system/api/crud_ui/routes.py:492-503` — `_criar`

```python
        except ValidationError:
            return error_response(
                form.templates,
                request,
                form.form_template,
                ctx_form=form.ctx_form(session),
                item_key=form.item_key,
                item=None,
                user=user,
                erro="Dados inválidos",
                status_code=400,
                dados=dados_form,
```

### Description

A criação captura ValidationError sem usar exc.errors() e devolve apenas a mensagem genérica Dados inválidos.

### Why it matters

O usuário não sabe qual campo corrigir, e regras de domínio precisam usar caminhos de exceção diferentes para comunicar mensagens úteis.

### Concrete fix

Capturar a exceção, mapear exc.errors() por campo para o contexto do formulário e adicionar um hook de validação de domínio que possa devolver erros globais e por campo após hidratar a entidade.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - O descarte do conteúdo de ValidationError foi verificado diretamente.
- **Weaknesses:**
  - A representação visual final dos erros por campo ainda precisa ser definida.
- **Suggested checks:**
  - Adicionar testes para erros simples, aninhados e regras de domínio.

## imp-20260729-009 — Completar hooks de ciclo de vida da UI

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** crud-ui, hooks, lifecycle, validation
- **Files affected:**
  - `bases/xtreme_system/api/crud_types.py`
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/route_factories.py`
- **Related opportunities:** imp-20260729-008

### Location

`bases/xtreme_system/api/crud_types.py:166-175` — function not specified

```python
    ctx_form: CtxForm
    item_key: str


BeforeCreateHook = Callable[[Session, CreateSchemaT], None]
BeforeUpdateHook = Callable[[Session, UpdateSchemaT], None]
BeforeUpdateEntityHook = Callable[[Session, EntityT, UpdateSchemaT], None]
BeforeDeleteHook = Callable[[Session, EntityT, int | None], None]
AfterWriteHook = Callable[[Session, EntityT, int | None], Any]
```

### Description

Os tipos incluem BeforeUpdateEntityHook, mas CrudUIBehaviorConfig expõe apenas BeforeUpdateHook sem entidade; também não existe after_delete no comportamento da UI.

### Why it matters

Validações que comparam estado antigo e novo não são expressáveis uniformemente na UI, e integrações pós-exclusão não têm um ponto de extensão equivalente.

### Concrete fix

Expor before_update_entity e after_delete em CrudUIBehaviorConfig, encaminhar a entidade e o usuário nas fábricas de rota e manter os hooks antigos com adaptação compatível.

### Self-critique

- **Confidence:** 9.0/10
- **Uncertain:** No
- **Strengths:**
  - Os aliases de hook e a configuração de comportamento foram verificados.
- **Weaknesses:**
  - A compatibilidade com todos os chamadores precisa ser conferida durante a implementação.
- **Suggested checks:**
  - Adicionar testes de ordem de hooks e propagação de exceções.

## imp-20260729-010 — Corrigir CSV para Excel pt-BR e habilitar XLSX

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** csv, xlsx, excel, localization
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/responses.py`
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `pyproject.toml`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/crud_ui/responses.py:15-25` — `csv_response`

```python
def csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### Description

O exportador usa csv.writer com delimitador padrão de vírgula e resposta UTF-8 sem BOM; não há suporte a XLSX nem dependência openpyxl localizada.

### Why it matters

Excel configurado para pt-BR pode abrir o CSV em uma única coluna, e usuários que dependem de planilhas precisam converter o arquivo manualmente.

### Concrete fix

Primeiro emitir CSV com delimiter=';' e codificação utf-8-sig; depois abstrair o formato de exportação e adicionar XLSX com uma dependência dedicada e testes de tipos de célula.

### Self-critique

- **Confidence:** 9.0/10
- **Uncertain:** No
- **Strengths:**
  - Delimitador e charset atuais foram verificados no código.
- **Weaknesses:**
  - A preferência exata dos consumidores por CSV ou XLSX não foi medida.
  - A busca de dependência foi limitada aos manifests disponíveis.
- **Suggested checks:**
  - Validar o CSV gerado no Excel pt-BR e adicionar teste de workbook para XLSX.
