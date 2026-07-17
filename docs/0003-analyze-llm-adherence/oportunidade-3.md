## Opportunity 3: escrita de arquivo antes do commit real, em `_criar_venda` e `_criar_compra`

File: bases/xtreme_system/api/routes/ui_routes/vendas.py (`_persistir_contrato_venda`,
linhas 315-331, e `_criar_venda`, linhas 334-374); bases/xtreme_system/api/routes/ui_routes/compras.py
(`_criar_compra`, linhas 298-378, via `salvar_arquivos`)

Problem:
O commit real da transação de banco acontece de forma centralizada em
`get_session()` (components/xtreme_system/database/core.py:56-66), **depois**
que o handler da rota retorna (`yield session` → `session.commit()`). Tanto
`_criar_venda` quanto `_criar_compra` gravam arquivos em disco (PDF de
contrato, comprovantes de compra) e retornam uma resposta de sucesso *antes*
desse commit acontecer. Se o commit falhar em `get_session` (ex.: constraint
que só é verificada no flush/commit final, não capturada pelos
`except IntegrityError` locais dentro do handler), a transação é revertida
mas o arquivo já escrito em disco não é removido — fica órfão, sem registro
correspondente no banco. `_persistir_contrato_venda` já trata esse caso
*internamente* (remove o arquivo se a própria inserção do documento falhar
dentro do handler), mas não cobre falha do commit externo, que ocorre fora
do escopo da função.

LLM Risk:
Um agente adicionando um novo campo obrigatório ou constraint em `Venda`,
`Compra`, `DocumentoContratoVenda` ou `ImagemComprovanteCompra` pode
raciocinar apenas sobre o `try/except IntegrityError` local dentro do
handler e concluir (incorretamente) que arquivo e banco estão sempre
consistentes — porque não há nada no código do handler que aponte para o
fato de que o commit real acontece em outro arquivo (`database/core.py`),
fora da função que ele está editando. Isso é agravado por ser um padrão
repetido em dois handlers (`_criar_venda` e `_criar_compra` via
`salvar_arquivos`), então uma correção pontual num dos dois deixa o outro
com o mesmo risco.

Action:
Não requer mudar o modelo de transação centralizado (que é intencional,
conforme CLAUDE.md). A ação mínima é: registrar a escrita do arquivo via
`register_post_commit` (o mesmo mecanismo já usado por
`whatsapp.notificar_venda`) em vez de escrever no disco antes do commit —
ou, alternativamente, documentar explicitamente o risco com um comentário
no ponto de escrita apontando para `get_session`, e adicionar um teste que
force falha de commit para verificar se o arquivo fica órfão hoje.

Suggested Interface:
```python
# vendas.py — adiar a escrita do PDF para pós-commit, como já é feito com o whatsapp
def _persistir_contrato_venda(session: Session, obj: venda.Venda) -> None:
    ...
    documento_contrato_venda.create(session, ...)  # grava só o registro na sessão
    pdf_bytes = documento_contrato_venda.gerar_pdf(obj)
    register_post_commit(session, lambda: path.write_bytes(pdf_bytes))
```

Tests:
Teste de integração que força uma exceção no commit (ex.: mockando
`Session.commit` para levantar `IntegrityError` após o handler retornar) e
verifica que nenhum arquivo órfão fica em `uploads/vendas/<id>/contrato/`
nem em `uploads/compras/<id>/comprovantes/`.

Success Metric:
Nenhuma escrita em disco ocorre antes da confirmação de commit da transação
correspondente — verificável isolando o teste acima e checando ausência de
arquivo após rollback simulado.
