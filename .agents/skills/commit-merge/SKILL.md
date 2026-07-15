---
name: commit-merge
description: Stage, commit, and merge the current branch into master with --no-ff. Handles worktree conflicts.
---

# Commit & Merge

Flow para stage + commit + merge no master com `--no-ff`.

## Gatilhos

- "commit and merge"
- "commit + merge"
- "commita e faz merge"
- "git add . && git commit && git merge"

## Fluxo

### 1. Verifica se master está livre

```bash
git worktree list
```

Se `master` aparece em outro worktree (não no atual), o merge será feito **no worktree principal** (aquele que tem `master`).

### 2. Stage + commit

```bash
git add .
git commit -am "<mensagem>"
```

Escreva uma mensagem concisa no estilo do repo (inglês, lowercase, imperative).

### 3. Merge

Se master **não** está em outro worktree:

```bash
git checkout master
git merge - --no-ff -m "merge <branch>: <msg>"
```

Se master **está** em outro worktree (ex: `~/orca/projects/xtreme-system [master]`):

```bash
# No worktree principal (use o workdir do bash tool, não mude de branch aqui)
git merge <nome-da-branch> --no-ff -m "merge <branch>: <msg>"
```

### 4. Confirma

Mostre `git log --oneline --graph -5` no final.
