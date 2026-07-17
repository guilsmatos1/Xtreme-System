## Opportunity 2: `_resolver_cliente` duplicado byte-a-byte entre vendas.py e compras.py

File: bases/xtreme_system/api/routes/ui_routes/vendas.py (linhas 273-312),
bases/xtreme_system/api/routes/ui_routes/compras.py (linhas 200-238)

Problem:
As duas funções `_resolver_cliente` são idênticas (uma única linha de
docstring de diferença): resolvem um cliente existente por `cliente_id` do
form ou constroem um `ClienteCreate` a partir de campos `cli_*`, incluindo a
mesma checagem de CPF duplicado. Já existe `bases/xtreme_system/api/routes/ui_routes/common.py`
como módulo de helpers compartilhados entre rotas HTMX (contém
`_uploads_contrato_venda_dir`, `_uploads_compra_dir`, `_remover_upload`
etc.), mas essa lógica de resolução de cliente não foi movida para lá.

LLM Risk:
Se um agente for instruído a "corrigir a validação de CPF duplicado na
resolução de cliente", é muito provável que edite apenas uma das duas cópias
(a que aparece primeiro na busca, ou a do arquivo mencionado no pedido do
usuário), deixando a outra rota com comportamento divergente sem que nada no
código sinalize a duplicação.

Action:
Mover `_resolver_cliente` para `common.py`, tornando-a pública (sem `_`) já
que passa a ser cross-module, e importá-la em `vendas.py` e `compras.py`.

Suggested Interface:
```python
# common.py
def resolver_cliente(
    session: Session, form: Any
) -> tuple[cliente.Cliente | None, cliente.ClienteCreate | None, str | None]:
    """Retorna (cliente_existente, dados_novo_cliente, erro)."""
```

Tests:
Um teste único em `tests/` cobrindo os três ramos (cliente existente válido,
cliente existente inválido, novo cliente com CPF duplicado, novo cliente
válido) substitui qualquer teste duplicado que hoje possa existir
separadamente para vendas e compras.

Success Metric:
`rg -n 'def _resolver_cliente' -g '*.py'` retorna zero ocorrências fora de
`common.py`; testes de vendas e compras continuam passando importando a
versão compartilhada.
