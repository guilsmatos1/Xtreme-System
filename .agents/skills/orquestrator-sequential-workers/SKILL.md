---
name: orquestrator-sequential-workers
description: Execute uma lista de tarefas sequencialmente. Cada tarefa roda em um subagent isolado. Use quando o usuario fornecer uma lista numerada de itens para implementar, ou disser "execute sequencialmente", "roda item por item", "implemente a lista", "orquestre as tarefas".
---

# Orquestrador Sequencial com Workers

Voce e o ORQUESTRADOR. Sua funcao e executar uma lista de tarefas sequencialmente, cada uma em um subagent worker isolado.

## Fluxo Principal

1. **Receba a lista** de tarefas do usuario.
2. **Para cada item**, execute o ciclo abaixo.
3. **Ao final**, entregue o relatorio de validacao geral.

## Ciclo por Item

Para cada tarefa `N` da lista:

### 1. Coleta de Estado
Antes de lancar o worker, colete o estado atual do repositorio:
- `git status --short`
- `git diff --stat`
- Lista dos commits recentes: `git log --oneline -5`

### 2. Criar Subagent Worker
Lance um subagent do tipo `general` com um prompt contendo:

```
Tarefa: [descricao do item atual]

Estado do repositorio:
[git status]

Alteracoes ja aplicadas nos itens anteriores:
[resumo cumulativo dos itens 1..N-1, com arquivos modificados]

Instrucoes:
- Implemente APENAS a tarefa descrita acima.
- Nao altere codigo nao relacionado.
- Siga as convencoes do projeto (AGENTS.md).
- Ao terminar, rode os testes e linters relevantes para validar.
- Retorne: (a) resumo do que foi feito, (b) lista de arquivos modificados,
  (c) comandos de teste/lint executados e seus resultados.
```

Regras:
- **Sempre** use um subagent novo (task_id ausente). Nunca reuse contexto de worker anterior.
- O worker deve retornar exatamente o que foi pedido: resumo, arquivos, testes.

### 3. Validacao Pos-Worker
Apos o worker concluir:
- Confira os arquivos modificados com `git diff --stat`
- Execute os testes/lints que o worker indicou (se necessario, complemente)
- Se houver falhas, corrija ou solicite ajuste antes de commitar

### 4. Commit
```bash
git add [arquivos modificados]
git commit -m "[descricao concisa da tarefa]"
```
Capture o hash do commit.

### 5. Atualizar Estado Cumulativo
Acrescente ao resumo cumulativo:
```
Item N: [descricao]
  Arquivos: [lista]
  Commit: [hash]
  Resumo: [1-2 linhas]
```

### 6. Fechar e Avancar
O subagent worker encerra automaticamente. Prossiga para o proximo item.

## Resolucao de Conflitos

Se o item `N` conflitar com alteracoes de itens anteriores:
- Ajuste o prompt do worker para considerar o estado atual dos arquivos.
- Se necessario, forneca trechos especificos do codigo ja modificado.
- Se o conflito for inevitavel (ex: duas tarefas alteram a mesma funcao de formas incompatíveis), reporte ao usuario e pare.

## Relatorio Final

Ao concluir todos os itens, execute uma validacao geral:
```bash
git diff --stat HEAD~N   # todas as alteracoes da sessao
uv run ruff check .
uv run pytest -q
```

Entregue:

```
=== RELATORIO DE EXECUCAO ===

Itens concluidos: N/N
Tempo total: Xmin

Commits:
  [hash1] Item 1: descricao
  [hash2] Item 2: descricao
  ...

Arquivos alterados:
  src/foo.py
  src/bar.py
  tests/test_foo.py

Testes executados:
  ruff check .  -> Passed
  pytest -q     -> XX passed

Riscos pendentes:
  [listar apenas se houver]
```
