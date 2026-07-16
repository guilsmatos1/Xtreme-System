---
name: commit-merge
description: Stage, commit, and merge the current branch into master with --no-ff. Handles worktree conflicts.
---
# Commit &amp; Merge

Flow for stage + commit + merge into master with `--no-ff`.

## Triggers

- "commit and merge"
- "commit + merge"
- "commita e faz merge"
- "git add . &amp;&amp; git commit &amp;&amp; git merge"

## Flow

### 1. Check if master is free

```bash
git worktree list
```

If `master` appears in another worktree (not the current one), the merge will be done **in the main worktree** (the one that has `master`).

### 2. Stage + commit

```bash
git add .
git commit -am "<message>"
```

Write a concise message in the repo style (English, lowercase, imperative).

### 3. Merge

If master is **not** in another worktree:

```bash
git checkout master
git merge - --no-ff -m "merge <branch>: <msg>"
```

If master **is** in another worktree (e.g. `~/orca/projects/xtreme-system [master]`):

```bash
# In the main worktree (use the bash tool's workdir, don't switch branches here)
git merge <branch-name> --no-ff -m "merge <branch>: <msg>"
```

