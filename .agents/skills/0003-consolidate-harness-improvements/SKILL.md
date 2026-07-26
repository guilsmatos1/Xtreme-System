---
name: 0003-consolidate-harness-improvements
description: Consolida as dicas de melhoria de harness geradas nas rodadas de worktree. Lê relatórios GUI-*.md versionados em docs/0005-analyze-token-efficiency/ e, para rodadas antigas, a pasta .loop mais recente; agrupa melhorias equivalentes por dedup semântico e mantém um ranking acumulado (improvements-harness.md, dentro da própria skill). Use quando pedirem para consolidar dicas de harness, ranquear melhorias das rodadas, ou alimentar o sistema de melhora contínua.
---

# Consolidate Harness Improvements

Consolida, em um único ranking acumulado, as dicas de melhoria de harness que cada rodada de trabalho em worktree deixa em `docs/0005-analyze-token-efficiency/GUI-*.md`. Para relatórios legados, também pode ler a pasta `.loop` mais recente. Melhorias equivalentes (mesmo com nomes diferentes) contam como **uma só**, e o número de menções indica quais ajustes de harness dão maior retorno nas próximas rodadas.

O entregável é o arquivo **`improvements-harness.md`**, gravado **dentro desta pasta de skill**. Ele **acumula histórico** entre execuções — cada fonte nova soma menções sobre o que já existe.

## Objetivo (o que é "done")

- `improvements-harness.md` contém uma seção explicativa por melhoria única + uma tabela final de ranking ordenada por menções (desc).
- Nenhuma melhoria duplicada: equivalentes semânticos viram uma entrada com menções somadas.
- Cada fonte processada fica registrada; reexecutar sobre as mesmas fontes **não** duplica contagens.

## Fluxo

### 1. Localizar fontes alvo

- Primeiro liste `docs/0005-analyze-token-efficiency/GUI-*.md`.
- Se houver arquivos ali, processe **todos os relatórios ainda não registrados** em `improvements-harness.md`.
- Se não houver relatórios versionados novos, use o fallback legado: liste `.loop/loop-*`, escolha a **mais recente** pela data no nome (`loop-N-YYYY-MM-DD` ou similar), desempatando pelo número maior, e processe os `GUI-*.md` dela que ainda não foram registrados.
- **Exija ao menos uma fonte nova.** Se todos os relatórios já constarem como processados, avise o usuário e pare.
- Reporte ao usuário quais fontes serão processadas antes de prosseguir.

### 2. Carregar estado acumulado

- Se `improvements-harness.md` (nesta pasta de skill) já existir, leia-o para obter:
  - a lista canônica de melhorias já registradas, seus títulos e contagens;
  - a lista de **"Fontes processadas"** (arquivos `docs/.../GUI-*.md` ou `.loop/.../GUI-*.md` já contabilizados).
- Remova da fila qualquer fonte que já conste como processada. Não reprocessar evita contagem dupla. Se o usuário insistir em reprocessar, remova a fonte da lista antes de recontar.
- Se o arquivo não existir, comece de um estado vazio.

### 3. Extrair melhorias das fontes atuais

- Leia **todos** os `GUI-*.md` selecionados no passo 1.
- Formato `GUI-NNN.md` (numerados): blocos
  ```
  Melhoria #N: <Título>
  - Problema: ...
  - Solução: ...
  - Economia estimada: <tokens>
  ```
  Extraia cada bloco como `{título, problema, solução, economia, fonte}`.
- Formato `GUI-Others.md` (texto livre): extraia cada sugestão distinta (subagents, skills, regras de AGENTS.md/hooks) como um item, sintetizando problema/solução/economia quando presentes.
- `fonte` = caminho relativo completo, por exemplo `docs/0005-analyze-token-efficiency/GUI-360.md` ou `.loop/loop-4-2026-07-24/GUI-350.md`.

### 4. Consolidar por dedup semântico (você, LLM, faz isso)

Para cada melhoria extraída, compare **pelo significado** — não por string exata — contra as entradas canônicas já existentes. Exemplos de equivalência que devem colapsar em uma entrada:

- "Docs Sob Demanda" ≡ "leitura cega de docs" ≡ "ler ARCHITECTURE/API só se mudar contrato".
- "Diff Completo Só Uma Vez" ≡ "Diffflow Enxuto" ≡ "git diff --stat por padrão".
- "Skill Commit-Merge Compacta" ≡ "Commit Flow Mais Enxuto" ≡ "modo small clean change".
- "Reduzir Comentários Intermediários" ≡ "menos progress updates".
- "Linear Auto-Contexto" ≡ "injetar resumo do issue" ≡ "ler só arquivos referenciados pela issue".

Regras:
- **Casou com existente** → incremente o contador e acrescente a `fonte` à entrada. **Não** reescreva a explicação nem crie entrada nova.
- **É nova** → crie entrada canônica com um **título curto e estável**, explicação sintetizada (problema, solução proposta, economia típica) e menção = 1.
- Ao reescrever o arquivo, **reuse os títulos canônicos já gravados** para não renomear entradas entre execuções.
- Duas menções da mesma melhoria em arquivos GUI diferentes contam como **2**.

### 5. Reescrever `improvements-harness.md`

Grave o arquivo nesta pasta de skill com esta estrutura:

```markdown
# Melhorias de Harness — Ranking Acumulado

_Última atualização: <data>. Fontes processadas: <lista de caminhos relativos>._

## Melhorias

### <Título canônico 1>
- **Problema:** ...
- **Solução:** ...
- **Economia estimada:** ...
- **Fontes:** <rodada/arquivo>, <rodada/arquivo>, ...

### <Título canônico 2>
...

## Ranking por menções

| # | Melhoria | Menções | Fontes |
|---|----------|---------|---------|
| 1 | <Título> | 5       | GUI-360, GUI-361 |
| 2 | ...      | 3       | ...     |
```

- A tabela é ordenada por **menções desc** (empate: alfabético). O topo = maior prioridade para as próximas rodadas.
- Use `Fontes processadas` no cabeçalho para listar os caminhos relativos processados. Se estiver atualizando um arquivo antigo que ainda diz `Rodadas processadas`, migre esse campo para `Fontes processadas` preservando as entradas existentes.
- Na tabela, a coluna `Fontes` deve mostrar os identificadores distintos de origem extraídos das fontes, por exemplo `GUI-360`, `GUI-361`, `loop-4-2026-07-24/GUI-350`.

### 6. Reportar

Ao terminar, informe ao usuário: fontes processadas, nº de melhorias novas adicionadas, nº de menções incrementadas em entradas existentes, e o top 3 do ranking.
