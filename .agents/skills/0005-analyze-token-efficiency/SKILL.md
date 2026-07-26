---
name: 0005-analyze-token-efficiency
description: Analisa o perfil compacto da última sessão do worker Codex e identifica até 5 melhorias de harness que obteriam o MESMO resultado com menos tokens. Exige evidência, economia estimada e teste de mesmo resultado. Use em retrospectivas de tokens ou para alimentar a skill 0003.
---

# Analyze Token Efficiency

Identifique melhorias de harness que teriam produzido exatamente a mesma entrega com menos tokens. Não reduza investigação, testes ou qualidade.

## Fluxo

### 1. Extrair o perfil

Execute o extrator uma única vez. Ele lê o rollout indicado por `CODEX_THREAD_ID`, usa o último `token_count` como corte para excluir esta retrospectiva e retorna somente agregados e candidatos compactos:

```bash
python .agents/skills/0005-analyze-token-efficiency/profile_session.py \
  --session-id "${CODEX_THREAD_ID:?}" > /tmp/codex-token-profile.json
```

Leia `/tmp/codex-token-profile.json` uma única vez. Não leia o rollout diretamente, salvo se o extrator falhar ou faltar evidência indispensável.

O perfil contém:

- `tokens`: totais reais do Codex; `cached_input_tokens` já faz parte de `input_tokens`;
- `tool_counts`;
- `largest_outputs`: chamadas com maior volume;
- `duplicate_calls`: chamadas idênticas repetidas;
- `failed_calls`: tentativas que falharam;
- `task_prompt`: pedido do usuário, truncado.

`estimated_output_tokens` usa 4 caracteres por token e é apenas estimativa. Não atribua todo o cache a uma chamada específica.

### 2. Escolher as melhorias

Cruze os candidatos com a tarefa. Uma melhoria só é válida quando:

1. possui evidência no perfil;
2. muda um canal consumido pelo Codex: `AGENTS.md`, skill, RTK, graphify, prompt/script de worker, hook/config/plugin ou estratégia de ferramentas;
3. elimina informação duplicada, output não usado, tentativa evitável ou volume desnecessário;
4. preserva código, testes e entrega final igualmente corretos e completos.

Ordene por economia estimada decrescente. Produza até 5 melhorias; se houver menos candidatos válidos, não invente.

### 3. Gravar uma única representação

Localize o checkout principal e a rodada atual:

```bash
MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
LOOP="$(find "$MAIN/.loop" -maxdepth 1 -type d -name 'loop-*' 2>/dev/null | sort | tail -1)"
ISSUE="$(git rev-parse --abbrev-ref HEAD)"
OUT="${LOOP:-$MAIN/docs/0005-analyze-token-efficiency}/$ISSUE.md"
mkdir -p "$(dirname "$OUT")"
```

Grave somente o formato canônico consumido pela `0003-consolidate-harness-improvements`:

```markdown
# Eficiência de tokens — <issue>
_Codex: <session_id> · input: <N> · cached: <N> · output: <N> · total: <N>_

Melhoria #1: <título>
- Problema: <desperdício observado>
- Evidência: <ferramenta/chamada, repetição ou tamanho>
- Solução: <canal Codex e mudança concreta>
- Economia estimada: ~<N> tokens
- Teste de mesmo-resultado: <por que a entrega seria idêntica>

Melhoria #2: ... até #5.
```

Ao terminar, responda em uma linha com sessão, totais, caminho e títulos/economias.

## Guardrails

- Analise Codex, não Opencode ou Claude Code.
- Não carregue outputs completos para medir tamanho.
- Use os totais reais do perfil; estime apenas custos isolados.
- Não inclua a própria retrospectiva.
- Não edite código do produto.
