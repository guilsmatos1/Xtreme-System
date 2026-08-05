# Improvement opportunities

- **Generated:** 2026-08-05T19:00:22-03:00
- **Total:** 3

## imp-20260805-001 — Tornar exportação uma operação explícita do Perfil

- **Impact:** Medium
- **Category:** Authorization
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** authorization, export, data-exposure, perfis
- **Files affected:** `components/xtreme_system/perfil/policy.py`, `bases/xtreme_system/api/crud_ui/registrars.py`, `bases/xtreme_system/api/routes/ui_routes/investidores.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`, templates de listagem
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/crud_ui/registrars.py:343` — `register_export_route._exportar`

```python
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, user: UIUser, q: str = "") -> Response:
        lista = query_list(
            session, module, listing=config.listing, state=ListState(q=q)
        )
        if config.columns is not None:
            export_columns: list[tuple[ColumnSpec[EntityT], Any]] = []
            for column in config.columns:
                export_value = column.export
                if export_value is None or (
                    config.pagina is not None
                    and column.field is not None
```

### Description

O catálogo de `OPERACOES` não contém `exportar` para nenhuma página. As rotas CSV exigem apenas `UIUser`, que garante a página, mas não chama `require_operacao`. Assim, um perfil com acesso de leitura e zero operações permitidas ainda pode baixar os dados visíveis em massa. O mesmo padrão ocorre na exportação de Investidores e dos lançamentos do Investidor.

### Why it matters

Exportar reduz muito a barreira para replicar ou retirar dados financeiros e cadastrais. A filtragem de campos protege campos já marcados como ocultos, mas não substitui a decisão de quem pode fazer extração em lote.

### Concrete fix

Adicionar `exportar` ao catálogo de cada página que oferece CSV; modelar a operação no `CrudUIExportConfig` e fazer a rota depender de `require_operacao(pagina, "exportar")`. Aplicar a mesma exigência às rotas manuais de Investidores e lançamentos, e ocultar os links quando a operação não for permitida.

### Domain details

#### Acceptance criteria

- Um usuário com a página, mas sem `exportar`, recebe 403 nas rotas CSV e não vê o link.
- Um usuário com `exportar` recebe somente as colunas que o Perfil permite ver.
- Administradores preservam o comportamento atual.

#### Suggested tests

- Cobrir uma exportação gerada pelo registrar e as duas exportações manuais de Investidores.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:** A rota e o catálogo foram verificados; a dependência `UIUser` só exige acesso à página.
- **Weaknesses:** Não foi executada uma requisição autenticada de ponta a ponta nesta análise.
- **Suggested checks:** Criar um Perfil de leitura sem operações e confirmar as respostas 403 após a mudança.

## imp-20260805-002 — Separar consulta RSD da permissão de editar Veículos

- **Impact:** Medium
- **Category:** Authorization
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** authorization, rsd, external-service, perfis
- **Files affected:** `components/xtreme_system/perfil/policy.py`, `bases/xtreme_system/api/routes/ui_routes/rsd.py`, templates dos formulários de veículo/compra/consignação
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/routes/ui_routes/rsd.py:86` — `ui_rsd_puxar_dados`

```python
@router.post("/ui/rsd/puxar-dados")
def ui_rsd_puxar_dados(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
    vei_placa: Annotated[str, Form()] = "",
    rsd_prefix: Annotated[str, Form()] = "",
    rsd_status_id: Annotated[str, Form()] = "rsd-status",
) -> HTMLResponse:
    try:
        placa = _placa_para_puxar_dados(placa, vei_placa)
```

### Description

`puxar-dados`, consulta unitária, acompanhamento e download do dossiê RSD dependem todos de `veiculos:editar`. Não há uma operação RSD no formulário de Perfis. Portanto, não é possível autorizar uma pessoa a consultar o serviço externo sem também dar poder de alterar veículos — nem revogar o RSD de alguém que ainda precisa editar o cadastro.

### Why it matters

RSD consulta um serviço externo, produz dossiês e pode ter custo, limite de uso ou dados mais sensíveis do que a edição rotineira do veículo. Misturar essas capacidades impede a aplicação do menor privilégio.

### Concrete fix

Criar `consultar_rsd` em `OPERACOES["veiculos"]`, trocar as quatro dependências RSD para essa operação e usar o mesmo predicado para exibir os controles de RSD. Manter `editar` exigido somente se a ação também persistir alterações no veículo.

### Domain details

#### Acceptance criteria

- O Perfil permite conceder `consultar_rsd` sem `editar`.
- Sem `consultar_rsd`, todos os endpoints RSD retornam 403.
- Editores sem `consultar_rsd` continuam editando veículos, mas não conseguem iniciar, acompanhar ou baixar dossiês.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:** Todos os endpoints RSD relevantes usam o mesmo predicado `veiculos:editar`.
- **Weaknesses:** A decisão comercial de delegar RSD é necessária; hoje o acoplamento pode ter sido intencional.
- **Suggested checks:** Confirmar se cada consulta RSD tem custo ou limite contratado antes de priorizar como controle obrigatório.

## imp-20260805-003 — Dar controles próprios para visualizar e enviar documentos de Cliente

- **Impact:** Medium
- **Category:** Authorization
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** authorization, documents, cliente, pii, perfis
- **Files affected:** `components/xtreme_system/perfil/policy.py`, `bases/xtreme_system/api/routes/ui_routes/clientes.py`, `bases/xtreme_system/api/templates/_modal_documentos_cliente.html`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/routes/ui_routes/clientes.py:155` — configuração `cliente_documentos`

```python
        upload_dir=_get_uploads_cliente_dir,
        url_prefix=lambda item_id: f"/static/uploads/clientes/{item_id}/documentos",
        create_fn=callback_from(globals(), "imagem_documento_cliente.create"),
        schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
        fk_field="cliente_id",
        delete_fn=callback_from(globals(), "imagem_documento_cliente.delete"),
        upload_field="documentos",
        get_dependency=_EditarClienteDep,
        upload_dependency=_EditarClienteDep,
        delete_dependency=_ExcluirDocumentoDep,
    ),
)
```

### Description

O Perfil tem apenas `clientes:excluir_documento`. Abrir a modal e enviar documentos dependem de `clientes:editar`, de modo que não há como conceder ou revogar acesso a documentos de identificação separadamente da edição completa do Cliente. O catálogo já usa operações distintas para abrir/enviar/excluir comprovantes, contratos, imagens e procurações em outras páginas.

### Why it matters

Documentos de Cliente normalmente contêm PII. A política atual obriga conceder escrita ampla no cadastro para uma tarefa documental, ou impede uma pessoa de anexar/ver documentos quando ela não deveria editar outros dados do Cliente.

### Concrete fix

Adicionar `abrir_documentos` e `enviar_documentos` em `OPERACOES["clientes"]`; configurar as dependências GET e POST da rota de anexos com essas operações e manter `excluir_documento` separado. Condicionar os controles da modal às três permissões.

### Domain details

#### Acceptance criteria

- Abertura, envio e exclusão de documentos têm permissões independentes no formulário de Perfis.
- Um usuário com somente `abrir_documentos` pode listar documentos, mas não enviar, excluir nem editar o Cliente.
- Os controles de outras mídias mantêm seus contratos atuais.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:** A rota de anexos e o catálogo de operações foram verificados; o contraste com as outras mídias está explícito na política.
- **Weaknesses:** Não foram revisados requisitos legais que possam exigir restringir ainda mais a visualização dos arquivos estáticos.
- **Suggested checks:** Confirmar se os arquivos em `/static/uploads/clientes/` precisam também de entrega autenticada antes de ampliar delegação.

## Discarded candidates

### Páginas administrativas ausentes de Perfis

Dashboard, DRE, Usuários, Perfis, Auditoria e Configurações estão explicitamente fora do mapeamento de páginas e suas rotas exigem `UIAdmin`. Isso parece uma decisão deliberada de administração, não uma lacuna acidental.

### Lançamentos manuais de Investidor

Leitura e exportação dos lançamentos acompanham a página Investidores, enquanto criar, editar e excluir exigem `UIAdmin`. Pode virar uma capacidade de Perfil se o negócio quiser delegar caixa, mas o código não sugere que o fluxo deva deixar de ser administrativo.

### Botão de novo Cliente condicionado a administrador

`clientes:cadastrar` já existe e a rota o aplica; apenas o botão em `clientes.html` usa `is_admin(user)`. É uma inconsistência de interface, não um recurso ausente do sistema de acesso.
