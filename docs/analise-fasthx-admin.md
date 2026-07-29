O projeto já resolve, à mão, boa parte do que a lib oferece: register_crud_ui_routes() (crud_ui/routes.py:163) com 5 dataclasses de config (CrudUIResourceConfig, CrudUITemplateConfig, CrudUIBehaviorConfig, ListingSpec, CrudUIExportConfig, CrudUIRouteConfig), hooks de ciclo de vida, sort SQL+Python (crud_ui/query.py), paginação, CSV e — aqui o projeto está à frente da lib — permissão granular por operação e por campo (require_operacao("clientes","cadastrar") em clientes.py:283, perfil.pode_ver_campo em routes.py:349). A lib só tem allowed_users/allowed_groups no nível da view.

Então as ideias abaixo são as que realmente não existem aqui.

---

Alta prioridade

1. ColumnSpec único alimentando tabela + CSV (hoje duplicado e sujeito a divergir)
Hoje as colunas da tela vivem em _linhas_clientes.html / _row_cliente.html e as do CSV em CrudUIExportConfig(csv_headers=[...], csv_row=lambda...) (clientes.py:269-281). São duas listas paralelas, mantidas manualmente, sem nada que garanta a mesma ordem/conteúdo. A lib resolve com column_list + column_labels + column_export_list.
Onde: crud_ui/routes.py:95-102 (config de export) vs. os ~14 partials *linhas.html/row*.html.
2. column_formatters — formatação de célula em Python, não em Jinja
A lib define column_formatters = {"status": fn(value, obj) -&gt; str} e column_formatters_export (texto puro no CSV, badge no HTML). Aqui, formatação está espalhada em macros Jinja (_macros.html:87 status_badge, :99 tipo_badge, :117 acao_badge, :129 papel_badge, :149 moeda) e replicada por entidade. Um registro de formatters por coluna reaproveitaria essas macros e eliminaria os *row**.html quase-idênticos.
3. Geração de formulário declarativa (form_sections / form_widget_overrides / depends_on)
Este é o maior ganho de manutenção disponível. Os formulários são HTML manual e enormes: _form_venda.html 22.7K, _form_compra.html 17.3K, _form_veiculo.html 16.0K. A lib gera o form a partir de form_columns, agrupa em acordeão com form_sections, e cobre os casos difíceis com form_widget_overrides (type: select|textarea|file, placeholder, description, hx_get/hx_target para dropdowns dependentes) e visibilidade condicional via depends_on: "campo_booleano". Não precisa ser tudo ou nada: dá para gerar os campos simples e manter blocos custom onde já existe lógica.
4. form_ajax_refs — selects de FK com busca server-side
_ctx_form_venda (vendas.py:80-86) carrega todos os veículos e todos os clientes em memória a cada abertura do formulário de venda, e injeta tudo no HTML. Isso degrada linearmente com a base. A lib usa form_ajax_refs = {"cliente_id": {"model": Cliente, "fields": ["nome"], "page_size": 10}}, que vira um select com busca ilike paginada. Vale como correção de performance independente do resto.

---

Média prioridade

5. toast_response() / modal_response() — helpers de resposta HTMX
O projeto não emite nenhum header HX-Trigger, HX-Redirect, HX-Refresh ou HX-Location (verificado em todo bases/). Todo feedback é OOB swap: o toast é um #msg com auto-dismiss em JS (base.html:282) e cada modal é um TemplateResponse montado à mão (clientes.py:87, :123, :166). A lib expõe toast_response(msg, type=, refresh=, status_code=) e modal_response(title, body, actions=[...], size=). Adicionar esses dois helpers em crud_ui/responses.py (que hoje tem csv_response, form_response, error_response, list_response, ok_response) removeria dezenas de linhas repetidas.
6. row_actions / multi_row_actions declarativos + diálogo de confirmação rico
Ações de linha hoje são partials fixos (_action_cliente_documentos.html, _action_veiculo_imagens.html, etc.). A lib declara [{"label","icon","hx_post","hx_target","confirm"}] e tem confirmação estruturada (confirm_danger, confirm_title, confirm_lines, confirm_ok_label) — útil justamente em exclusão de veículo/venda, onde hoje o conflito só aparece depois do POST (register_delete_route, routes.py:661-697).
7. Seleção múltipla e ações em lote — ausente por completo
Não há checkbox de seleção em nenhuma listagem. multi_row_actions + multi_row_select_all_pages habilitariam "exportar selecionados", "excluir selecionados", "marcar custos como pagos". Encaixa naturalmente no register_export_route existente (routes.py:328), que hoje só exporta o resultado do filtro atual.
8. Erros de validação com mensagem de domínio
register_create_route (routes.py:492-504) captura ValidationError do Pydantic e responde sempre "Dados inválidos", descartando quais campos falharam; regras de negócio precisam ser levantadas como HTTPException para escapar disso. A lib usa uma ValidationError própria lançada de on_model_change(item, form_data, is_new, db, request) com mensagem por regra. Duas melhorias aqui: (a) propagar exc.errors() para marcar os campos no form; (b) um hook de validação que receba a entidade já hidratada.
9. Hooks incompletos no CrudUIBehaviorConfigon_model_change(item, form_data, is_new, db, request) com mensagem por regra. Duas melhorias aqui: (a) propagar exc.errors() para marcar os campos no form; (b) um hook de validação que receba a entidade já hidratada.
10. Erros de validação com mensagem de domínio
register_create_route (routes.py:492-504) captura ValidationError do Pydantic e responde sempre "Dados inválidos", descartando quais campos falharam; regras de negócio precisam ser levantadas como HTTPException para escapar disso. A lib usa uma ValidationError própria lançada de on_model_change(item, form_data, is_new, db, request) com mensagem por regra. Duas melhorias aqui: (a) propagar exc.errors() para marcar os campos no form; (b) um hook de validação que receba a entidade já hidratada.
11. Hooks incompletos no CrudUIBehaviorConfig
Existem before_create/update/delete e after_create/update (crud_types.py:170-174, ligados em routes.py:82-89), mas: não há after_delete; e BeforeUpdateEntityHook (crud_types.py:172) está declarado e é usado só em route_factories.py:102 (rotas JSON) — a UI usa a variante que não recebe a entidade, então validações "compara valor antigo vs. novo" (o caso on_model_change de sync externo da lib) não são expressáveis na UI.
12. Export XLSX
Só existe CSV (csv_response, responses.py:15), e openpyxl não está nas dependências. A lib oferece export_types = ["csv","xlsx"]. Ponto adjacente e concreto: o CSV atual usa delimitador vírgula e UTF-8 sem BOM — Excel pt-BR abre isso tudo numa coluna só. utf-8-sig + delimiter=";" é correção de uma linha em responses.py:15-24.

---

Baixa prioridade / arquitetural

11. View como classe (CRUDView) em vez de função com 10 parâmetros
register_crud_ui_routes() recebe 10 argumentos e 5 dataclasses de config (routes.py:163-175), e as rotas custom de cada entidade são funções soltas registradas no app global importado de setup (clientes.py:35), o que cria acoplamento por ordem de import. O CRUDView da lib agrupa config + endpoints custom (@CRUDView.endpoint("/{name}/{item_id}/build", methods=["POST"])) + estado de instância na mesma classe, e herança dá reuso entre as duas páginas de cliente que hoje passam por _register_clientes_page(...) com 11 kwargs (clientes.py:211-224).
12. Paginação sem total
list_response deriva tem_proximo = page_count == limit (responses.py:161) — sem COUNT, logo sem número de páginas nem "X de Y". A lib trabalha com page_size e paginação real. Custo: um count() por listagem.
13. htmx_columns (polling por coluna com terminal_states) e console_response com SSE
Menos aplicável a este domínio (não há operação longa tipo deploy), mas o padrão terminal_states: ["online","failed"] — parar o polling quando o estado é final — serviria para acompanhar processamento de uploads/geração de PDF sem recarregar a página. Não há nenhum hx-trigger="every ..." no projeto hoje.

Não recomendo copiar: o ai_chat / ai_complete / tool_registry, a auth OIDC/Keycloak (a auth com pwdlib+JWT+perfis daqui é mais adequada), e a progress_redis_url (introduziria Redis como dependência para pouco ganho).

---

Sugestão de ordem prática: 10 (CSV pt-BR, trivial) → 4 (perf real) → 5 (helpers, desbloqueia 6 e 7) → 1+2 (elimina a maior parte da duplicação de templates) → 3 (o maior projeto).

Fontes: fasthx-admin no PyPI, FastHX docs, volfpeter/fasthx no GitHub.

- Contexto — o que o projeto já resolve à mão, e onde ele está à frente da lib (permissão por operação/campo)
- Alta prioridade (1–4) — ColumnSpec único, column_formatters, geração declarativa de formulários, form_ajax_refs
- Média (5–10) — helpers toast_response/modal_response, row_actions/multi_row_actions, ações em lote, erros de validação por campo, hooks incompletos, XLSX + CSV pt-BR
- Baixa/arquitetural (11–13) — CRUDView como classe, pagina
incompletos, XLSX + CSV pt-BR
- Baixa/arquitetural (11–13) — CRUDView como classe, paginação com total, polling/SSE

