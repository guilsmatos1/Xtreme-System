## Opportunity 1: `_snapshot` privado usado como API compartilhada informal

File: components/xtreme_system/auditoria/core.py

Problem:
`_snapshot` (auditoria/core.py:39) tem prefixo `_`, sinalizando "interno ao
módulo", mas é importado diretamente por quatro outros componentes:
`crud/core.py`, `caixa/core.py`, `fechamento_venda/core.py` e
`usuario/core.py`. Na prática é uma função pública de infraestrutura de
auditoria (converte um ORM model num dict serializável, mascarando campos
sensíveis como `senha_hash`/`evolution_api_key`), só que sem contrato
declarado: qualquer alteração de assinatura ou comportamento em
`_snapshot` quebra silenciosamente 4 componentes que não aparecem como
dependentes óbvios no nome.

LLM Risk:
Um agente editando `auditoria/core.py` isoladamente (guiado pelo nome
`_snapshot` e pela ausência de testes de contrato cross-módulo) pode assumir
que é seguro alterar o formato de retorno ou o conjunto `MASK`, sem perceber
que isso se propaga para snapshots de auditoria de usuário, caixa e
fechamento de venda — dados que alimentam trilha de auditoria e podem ter
implicação de compliance (mascaramento de senha).

Action:
Renomear para `snapshot` (público) em `auditoria/core.py` e atualizar os 4
imports. Não requer mudança de assinatura nem nova abstração — apenas tornar
explícito que é uma API pública deste componente.

Suggested Interface:
```python
def snapshot(obj: Any) -> dict[str, Any]:
    """Snapshot serializável de um ORM model para auditoria, mascarando campos sensíveis."""
```

Tests:
Um teste de contrato em `tests/` cobrindo: campo em `MASK` retorna `"***"`;
`Decimal` vira `str`; `date`/`datetime` vira ISO; enum vira `.value`. Isso já
pode não existir hoje — se não existir, é o teste que trava o contrato antes
do rename.

Success Metric:
Nenhum import de `_snapshot` fora de `auditoria/core.py` (verificável com
`rg '_snapshot' --include='*.py'` retornando apenas o arquivo de definição
mais os 4 chamadores já migrados para `snapshot`).
