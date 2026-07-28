---
name: devops--deploy--git-push
description: Push the current branch to the remote origin.
metadata:
    skill-organizer:
        original-name: devops--deploy--git-push
        source-relative-path: devops/deploy/git-push
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Git Push

Push the current branch to `origin`.

## Triggers

- "push"
- "git push"
- "enviar"
- "fazer push"
- "enviar pro github"

## Flow

### 1. Verify remote

```bash
git remote get-url origin
```

If no remote `origin` exists, ask the user for the URL.

### 2. Get current branch

```bash
git branch --show-current
```

### 3. Push

```bash
git push -u origin <branch>
```

If push is rejected (remote has diverged), ask the user if they want to force push. Never force push without confirmation.
