---
name: 0005-analyze-token-efficiency
description: Analisa o histórico JSONL da última sessão do worker Codex e cita 5 melhorias de harness que teriam obtido o MESMO resultado consumindo menos tokens, sem perder qualidade. Para cada melhoria, exige evidência concreta da sessão, custo em tokens, alvo de harness, economia estimada e teste de mesmo resultado. Use em retrospectivas de eficiência de tokens do worker, ao investigar onde tokens foram desperdiçados ou para alimentar a skill 0003.
---

# Analyze Token Efficiency

Analise a sessão que o **worker Codex** acabou de executar e responda:

> Quais melhorias no harness teriam produzido exatamente o mesmo resultado com menos tokens?

O entregável são **exatamente 5 melhorias**, ordenadas por economia estimada, cada uma apoiada por evidência concreta da sessão. Não proponha reduzir investigação, testes ou qualidade.

Esta skill alimenta a `0003-consolidate-harness-improvements`: grave blocos no formato `Melhoria #N` / Problema / Solução / Economia estimada em `.loop/loop-*/GUI-*.md`.

## Canais elegíveis

As melhorias devem beneficiar o Codex. Alvos válidos:

- `AGENTS.md` e instruções importadas por ele;
- skills em `.agents/skills` ou `~/.codex/skills`;
- `RTK.md` e uso do RTK;
- graphify;
- prompts e scripts que iniciam workers Codex;
- hooks, configuração ou plugins do Codex;
- estratégia de ferramentas e, quando permitido, subagentes.

Configuração exclusiva do Opencode ou Claude Code é inelegível.

## Critérios de conclusão

1. Identificar o rollout da sessão-alvo pelo `CODEX_THREAD_ID` ou pelo `cwd`.
2. Extrair um perfil compacto do JSONL sem despejar outputs completos no contexto.
3. Produzir até 5 melhorias comprovadas, ordenadas por economia estimada.
4. Gravar o relatório da rodada em formato compatível com a skill 0003.
5. Manter a própria análise econômica em tokens.

## Como o Codex registra tokens

Os rollouts ficam em `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`.

- `session_meta.payload`: `session_id`, `cwd`, origem e versão.
- `event_msg` com `payload.type == "token_count"`: uso cumulativo em `payload.info.total_token_usage`.
- `response_item` com `payload.type == "function_call"`: ferramenta e argumentos.
- `response_item` com `payload.type == "function_call_output"`: output e `call_id`.

Use o **último** evento `token_count` anterior ao início desta retrospectiva. Seus campos são:

- `input_tokens`
- `cached_input_tokens`
- `cache_write_input_tokens`
- `output_tokens`
- `reasoning_output_tokens`
- `total_tokens`

Os totais são reais. Para isolar um output específico, use `length / 4` apenas como aproximação e rotule-a como estimativa. Contexto grande inserido cedo tende a reaparecer em `cached_input_tokens`, então priorize desperdícios iniciais e recorrentes.

## Fluxo

### 1. Localizar a sessão-alvo

Prefira o id fornecido pelo invocador. Na sessão corrente, use `CODEX_THREAD_ID`:

```bash
SID="${CODEX_THREAD_ID:-<id-fornecido>}"
ROLLOUT="$(find ~/.codex/sessions -type f -name "*${SID}*.jsonl" -print -quit)"
```

Se não houver id, escolha o rollout mais recente cujo `session_meta.payload.cwd` seja o diretório atual:

```bash
CWD="$(pwd)"
ROLLOUT="$(
  find ~/.codex/sessions -type f -name 'rollout-*.jsonl' -print0 |
  xargs -0 ls -t |
  while IFS= read -r f; do
    jq -e --arg cwd "$CWD" \
      'select(.type=="session_meta" and .payload.cwd==$cwd)' "$f" >/dev/null &&
      { printf '%s\n' "$f"; break; }
  done
)"
SID="$(jq -r 'select(.type=="session_meta") | .payload.session_id' "$ROLLOUT")"
```

Garanta que o `cwd` e a issue correspondem ao trabalho analisado. Exclua somente as chamadas feitas pela própria retrospectiva. Trabalho anterior de commit/merge faz parte do custo real.

### 2. Extrair um perfil compacto

Nunca imprima o rollout inteiro nem outputs integrais. Use agregações:

```bash
# Metadados
jq -c 'select(.type=="session_meta") |
  .payload | {session_id,cwd,originator,cli_version,source}' "$ROLLOUT"

# Totais reais: use o último token_count anterior à retrospectiva
jq -c 'select(.type=="event_msg" and .payload.type=="token_count") |
  .payload.info.total_token_usage' "$ROLLOUT" | tail -1

# Contagem por ferramenta
jq -r 'select(.type=="response_item" and .payload.type=="function_call") |
  .payload.name' "$ROLLOUT" | sort | uniq -c | sort -nr

# Chamadas com argumentos grandes; tamanho, não conteúdo
jq -r 'select(.type=="response_item" and .payload.type=="function_call") |
  [.timestamp,.payload.name,(.payload.arguments|length)] | @tsv' "$ROLLOUT" |
  sort -k3,3nr | head -12

# Maiores outputs; tamanho, não conteúdo
jq -r 'select(.type=="response_item" and .payload.type=="function_call_output") |
  [.timestamp,.payload.call_id,(.payload.output|length)] | @tsv' "$ROLLOUT" |
  sort -k3,3nr | head -12

# Comandos e caminhos, truncados para inspeção segura
jq -r 'select(.type=="response_item" and .payload.type=="function_call") |
  [.timestamp,.payload.name,((.payload.arguments|fromjson? // {}) |
    (.cmd // .path // .query // .target // tostring)[0:240])] | @tsv' "$ROLLOUT"
```

Quando necessário, correlacione `function_call.id` com `function_call_output.call_id` usando `jq -s`, mas retorne apenas nome, timestamp, argumento resumido e quantidade de caracteres.

### 3. Diagnosticar desperdícios

Compare as chamadas com o objetivo real da issue. Procure:

- documentos lidos sem gatilho;
- mesmo arquivo ou busca repetidos sem mudança relevante;
- `git diff`, logs, listagens ou testes com output maior do que o necessário;
- output grande inserido cedo e carregado nos turnos seguintes;
- chamadas que falharam por sintaxe ou descoberta evitável;
- buscas amplas que graphify ou `rg` mais específico resolveriam;
- leitura integral quando um recorte por linha bastava;
- múltiplas inspeções equivalentes do mesmo estado;
- atualizações ou narração que não mudaram decisões;
- contexto reconstruído que já existia na issue ou no grafo.

Para cada candidato, registre:

1. timestamp e ferramenta;
2. chamada ou arquivo envolvido;
3. tamanho do output ou repetição observada;
4. custo estimado;
5. canal Codex que evitaria o desperdício.

### 4. Selecionar as melhorias

Cada melhoria precisa passar neste teste:

> Se a regra já existisse, o código, os testes e a entrega final continuariam igualmente corretos e completos?

Explique por que o custo removido era redundante: informação duplicada, output não utilizado, tentativa evitável ou volume além do necessário. Descarte qualquer proposta que dependa de fazer menos validação útil.

Ordene por economia estimada decrescente. Se menos de 5 candidatos tiverem evidência e passarem no teste, reporte apenas os válidos; não invente para completar cinco.

### 5. Gravar o relatório

`.loop` existe apenas no checkout principal:

```bash
MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
LOOP="$(find "$MAIN/.loop" -maxdepth 1 -type d -name 'loop-*' 2>/dev/null | sort | tail -1)"
ISSUE="$(git rev-parse --abbrev-ref HEAD)"
OUT="${LOOP:-$MAIN/docs/0005-analyze-token-efficiency}/$ISSUE.md"
mkdir -p "$(dirname "$OUT")"
```

Use este formato:

```markdown
# Retrospectiva de Eficiência de Tokens — <issue>

_Sessão Codex: <session_id> · worktree: <cwd> · modelo: <modelo, se disponível> · data: <data>_

## Perfil de execução
- input: <N> · cached_input: <N> · output: <N> · reasoning: <N> · total: <N>
- Ferramentas: <exec_command xN, apply_patch xN, ...>
- Maiores outputs e repetições: <resumo compacto>

## As 5 melhorias

### 1. <título>
- **Padrão:** <tipo de desperdício>
- **Evidência:** <timestamp, ferramenta, repetição/tamanho>
- **Custo observado:** ~<N> tokens (<exato ou estimado>)
- **Alvo de harness (Codex):** <arquivo ou canal>
- **Solução:** <mudança concreta>
- **Economia estimada:** ~<N> tokens
- **Teste de mesmo-resultado:** <por que a entrega não muda>

### 2. ... até ### 5.

## Total estimado economizado
~<N> tokens (~<percentual>), sem mudança no resultado entregue.

---

## Blocos para o pipeline

Melhoria #1: <título>
- Problema: <...>
- Solução: <alvo Codex + mudança concreta>
- Economia estimada: ~<N> tokens

Melhoria #2: ... até #5.
```

### 6. Reportar

O arquivo é o entregável. Ao terminar, responda em uma linha com sessão, totais reais, caminho gravado e títulos/economias. Não faça narração longa.

## Guardrails

- Analise Codex, não Opencode.
- Evidência real é obrigatória.
- Use totais reais do último `token_count`; estime apenas custos isolados.
- Nunca carregue outputs completos só para medir tamanho.
- Não atribua todo `cached_input_tokens` a uma única leitura; trate o efeito de cache como estimativa.
- Não edite código do produto. Esta skill produz apenas análise e blocos de melhoria de harness.
- Não inclua chamadas da própria retrospectiva no custo analisado.
