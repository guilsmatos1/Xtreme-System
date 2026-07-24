---
name: 0003-consolidate-harness-improvements
description: Consolida as dicas de melhoria de harness geradas nas rodadas de worktree. Lê os arquivos GUI-*.md da pasta .loop mais recente, agrupa melhorias equivalentes por dedup semântico e mantém um ranking acumulado (improvements-harness.md, dentro da própria skill) das melhorias mais mencionadas. Use quando pedirem para consolidar dicas de harness, ranquear melhorias das rodadas, ou alimentar o sistema de melhora contínua.
---

# Consolidate Harness Improvements

Consolida, em um único ranking acumulado, as dicas de melhoria de harness que cada rodada de trabalho em worktree deixa na pasta `.loop`. Melhorias equivalentes (mesmo com nomes diferentes) contam como **uma só**, e o número de menções indica quais ajustes de harness dão maior retorno nas próximas rodadas.

O entregável é o arquivo **`improvements-harness.md`**, gravado **dentro desta pasta de skill**. Ele **acumula histórico** entre execuções — cada rodada nova soma menções sobre o que já existe.

## Objetivo (o que é "done")

- `improvements-harness.md` contém uma seção explicativa por melhoria única + uma tabela final de ranking ordenada por menções (desc).
- Nenhuma melhoria duplicada: equivalentes semânticos viram uma entrada com menções somadas.
- A rodada `.loop` processada fica registrada; reexecutar sobre a mesma rodada **não** duplica contagens.

## Fluxo

### 1. Localizar a pasta `.loop` alvo

- Liste `.loop/loop-*`. Escolha a **mais recente** pela data no nome (`loop-N-YYYY-MM-DD`), desempatando pelo número `N` maior.
- **Exija que a pasta contenha ao menos um `GUI-*.md`.** Pule pastas vazias (ex.: uma `loop-1` sem arquivos).
- Reporte ao usuário qual pasta foi escolhida antes de prosseguir.

### 2. Carregar estado acumulado

- Se `improvements-harness.md` (nesta pasta de skill) já existir, leia-o para obter:
  - a lista canônica de melhorias já registradas, seus títulos e contagens;
  - a lista de **"Rodadas processadas"** (pastas `.loop` já contabilizadas).
- Se a pasta escolhida no passo 1 **já constar** como processada, avise o usuário e **pare** — não reprocessar evita contagem dupla. (Se o usuário insistir em reprocessar, remova a rodada da lista antes de recontar.)
- Se o arquivo não existir, comece de um estado vazio.

### 3. Extrair melhorias da rodada atual

- Leia **todos** os `GUI-*.md` da pasta escolhida.
- Formato `GUI-NNN.md` (numerados): blocos
  ```
  Melhoria #N: <Título>
  - Problema: ...
  - Solução: ...
  - Economia estimada: <tokens>
  ```
  Extraia cada bloco como `{título, problema, solução, economia, fonte}`.
- Formato `GUI-Others.md` (texto livre): extraia cada sugestão distinta (subagents, skills, regras de AGENTS.md/hooks) como um item, sintetizando problema/solução/economia quando presentes.
- `fonte` = `<pasta .loop>/<arquivo GUI>`.

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
- Duas menções da mesma melhoria em arquivos GUI diferentes da mesma rodada contam como **2**.

### 5. Reescrever `improvements-harness.md`

Grave o arquivo nesta pasta de skill com esta estrutura:

```markdown
# Melhorias de Harness — Ranking Acumulado

_Última atualização: <data>. Rodadas processadas: <lista de pastas .loop>._

## Melhorias

### <Título canônico 1>
- **Problema:** ...
- **Solução:** ...
- **Economia estimada:** ...
- **Fontes:** <rodada/arquivo>, <rodada/arquivo>, ...

### <Título canônico 2>
...

## Ranking por menções

| # | Melhoria | Menções | Rodadas |
|---|----------|---------|---------|
| 1 | <Título> | 5       | loop-2  |
| 2 | ...      | 3       | ...     |
```

- A tabela é ordenada por **menções desc** (empate: alfabético). O topo = maior prioridade para as próximas rodadas.
- Mantenha a lista "Rodadas processadas" atualizada com a pasta recém-processada.

### 6. Reportar

Ao terminar, informe ao usuário: pasta processada, nº de melhorias novas adicionadas, nº de menções incrementadas em entradas existentes, e o top 3 do ranking.
