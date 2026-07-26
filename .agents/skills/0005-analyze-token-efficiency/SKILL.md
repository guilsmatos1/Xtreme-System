---
name: 0005-analyze-token-efficiency
description: Analyzes the compact profile of the latest Codex worker session and identifies up to 5 harness improvements that would have produced the SAME result with fewer tokens. Requires evidence, estimated savings, and same-result testing. Use in token retrospectives or to feed skill 0003.
---

# Analyze Token Efficiency

Identify harness improvements that would have produced exactly the same deliverable with fewer tokens. Do not reduce investigation, tests, or quality.

## Flow

### 1. Extract The Profile

Run the extractor once. It reads the rollout indicated by `CODEX_THREAD_ID`, uses the latest `token_count` as the cutoff to exclude this retrospective, and returns only compact aggregates and candidates:

```bash
python .agents/skills/0005-analyze-token-efficiency/profile_session.py \
  --session-id "${CODEX_THREAD_ID:?}" > /tmp/codex-token-profile.json
```

Read `/tmp/codex-token-profile.json` once. Do not read the rollout directly unless the extractor fails or indispensable evidence is missing.

The profile contains:

- `tokens`: real Codex totals; `cached_input_tokens` is already part of `input_tokens`;
- `tool_counts`;
- `largest_outputs`: highest-volume calls;
- `duplicate_calls`: repeated identical calls;
- `failed_calls`: failed attempts;
- `task_prompt`: user request, truncated.

`estimated_output_tokens` uses 4 characters per token and is only an estimate. Do not attribute the whole cache to one specific call.

### 2. Choose Improvements

Cross-check candidates against the task. An improvement is valid only when it:

1. has evidence in the profile;
2. changes a channel consumed by Codex: `AGENTS.md`, skill, RTK, graphify, worker prompt/script, hook/config/plugin, or tool strategy;
3. removes duplicated information, unused output, avoidable attempts, or unnecessary volume;
4. preserves code, tests, and final deliverable as equally correct and complete.

Sort by estimated savings desc. Produce up to 5 improvements; if there are fewer valid candidates, do not invent any.

### 3. Write One Canonical Representation

When `CODEX_TOKEN_REPORT_PATH` is set by the hook, use it unchanged. Otherwise, locate the main checkout and current run:

```bash
if [ -n "${CODEX_TOKEN_REPORT_PATH:-}" ]; then
  OUT="$CODEX_TOKEN_REPORT_PATH"
else
  MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
  LOOP="$(find "$MAIN/.loop" -maxdepth 1 -type d -name 'loop-*' 2>/dev/null | sort | tail -1)"
  ISSUE="${CODEX_SOURCE_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
  OUT="${LOOP:-$MAIN/docs/0005-analyze-token-efficiency}/$ISSUE.md"
fi
mkdir -p "$(dirname "$OUT")"
```

Write only the canonical format consumed by `0003-consolidate-harness-improvements`:

```markdown
# Eficiência de tokens — <issue>
_Codex: <session_id> · input: <N> · cached: <N> · output: <N> · total: <N>_

Melhoria #1: <title>
- Problema: <observed waste>
- Evidência: <tool/call, repetition, or size>
- Solução: <Codex channel and concrete change>
- Economia estimada: ~<N> tokens
- Teste de mesmo-resultado: <why the deliverable would be identical>

Melhoria #2: ... up to #5.
```

When done, respond in one line with session, totals, path, and titles/savings.

## Guardrails

- Analyze Codex, not Opencode or Claude Code.
- Do not load full outputs just to measure size.
- Use real profile totals; estimate only isolated costs.
- Do not include the retrospective itself.
- Do not edit product code.
- In automatic execution, write only to `CODEX_TOKEN_REPORT_PATH`; do not alter `.codex/.hook-state` or orchestration files.
