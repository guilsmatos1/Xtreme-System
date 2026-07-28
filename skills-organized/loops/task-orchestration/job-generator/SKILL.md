---
name: loops--task-orchestration--job-generator
description: >-
    Generates JSON job files for the skill-dispatcher skill. Uses an agent-routing.json config to automatically assign the correct Orca agent (claude, codex, omp, etc.) to each skill based on prefix matching. Accepts skill names from the CLI or from a requests file, and produces a ready-to-run jobs JSON file.
metadata:
    skill-organizer:
        original-name: loops--task-orchestration--job-generator
        source-relative-path: loops/task-orchestration/job-generator
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Job Generator for Skill Dispatcher

Generates JSON job files that the `loops--task-orchestration--skill-dispatcher`
skill consumes. The key feature is **agent routing**: an `agent-routing.json`
config maps skill prefixes to agents, so you never need to remember which agent
runs which kind of skill.

## Files

| File                 | Purpose                                                    |
| -------------------- | ---------------------------------------------------------- |
| `agent-routing.json` | Maps skill prefixes → agents, plus default worktree/retry. |
| `generate_jobs.py`   | CLI that reads routing + requests and emits a jobs JSON.   |

## Quick start

### 1. Generate from skill names on the command line

```bash
python3 .agents/skills/loops--task-orchestration--job-generator/generate_jobs.py \
  create --skills coding--analyze--general coding--analyze--ui-ux devops--linear--send \
  -o my-jobs.json
```

This reads `agent-routing.json`, matches each skill against the routing rules
(longest prefix wins), and writes `my-jobs.json` with the correct agent per job.

### 2. Generate from a requests file

Create a requests file (`requests.json`):

```json
[
  { "skill": "coding--analyze--general", "skill_args": "foco na API layer" },
  { "skill": "coding--analyze--ui-ux" },
  { "skill": "devops--linear--send", "skill_args": "criar issues do audit" }
]
```

Or even simpler — a plain list of skill names:

```json
["coding--analyze--general", "coding--analyze--ui-ux", "devops--linear--send"]
```

Then generate:

```bash
python3 .agents/skills/loops--task-orchestration--job-generator/generate_jobs.py \
  create --from-file requests.json -o my-jobs.json
```

### 3. Run with the dispatcher

```bash
python3 .agents/skills/loops--task-orchestration--skill-dispatcher/run_jobs.py \
  run-jobs --jobs-file my-jobs.json --json
```

### 4. Inspect the routing table

```bash
python3 .agents/skills/loops--task-orchestration--job-generator/generate_jobs.py routing
```

## Agent routing config

The `agent-routing.json` file controls which agent handles each skill category:

```json
{
  "routing": [
    { "prefix": "coding--analyze",  "agent": "claude" },
    { "prefix": "coding--refactor", "agent": "claude" },
    { "prefix": "devops--deploy",   "agent": "codex"  },
    { "prefix": "devops--linear",   "agent": "codex"  }
  ],
  "default_agent": "claude",
  "defaults": {
    "worktree": {
      "mode": "new",
      "repo": "name:xtreme-system",
      "base_branch": "master"
    },
    "retries": 1,
    "retry_delay_seconds": 10
  }
}
```

### Matching rules

- Rules are matched by **longest prefix** first (most specific wins).
- If no prefix matches, `default_agent` is used.
- Any field in a request object can override the routing (e.g. setting `"agent": "omp"`
  on a specific request bypasses the routing table for that job).

### Defaults

The `defaults` object provides fallback values for `worktree`, `retries`, and
`retry_delay_seconds`. Per-request overrides always take precedence.

## Request object fields

Each request in a `--from-file` JSON can have:

| Field                 | Required | Description                                           |
| --------------------- | -------- | ----------------------------------------------------- |
| `skill`               | yes*     | Skill name (e.g. `coding--analyze--general`).         |
| `prompt`              | yes*     | Raw prompt (alternative to `skill`).                  |
| `skill_args`          | no       | Arguments passed to the skill.                        |
| `name`                | no       | Job name (auto-generated from skill if omitted).      |
| `agent`               | no       | Override the routed agent for this specific job.      |
| `command`             | no       | Raw shell command (replaces `agent`).                 |
| `worktree`            | no       | Override default worktree config.                     |
| `retries`             | no       | Override default retry count.                         |
| `retry_delay_seconds` | no       | Override default retry delay.                         |
| `keep_open`           | no       | Keep terminal open after completion.                  |

\* One of `skill` or `prompt` is required.

## Output format

The generated JSON is directly compatible with the skill-dispatcher:

```json
{
  "jobs": [
    {
      "name": "coding-analyze-general",
      "agent": "claude",
      "skill": "coding--analyze--general",
      "skill_args": "foco na API layer",
      "retries": 1,
      "retry_delay_seconds": 10,
      "worktree": {
        "mode": "new",
        "name": "coding-analyze-general",
        "repo": "name:xtreme-system",
        "base_branch": "master"
      }
    }
  ]
}
```

## Editing the routing

To change which agent handles which skills, edit `agent-routing.json` directly.
No code changes are needed. The routing is re-read every time `generate_jobs.py`
runs.
