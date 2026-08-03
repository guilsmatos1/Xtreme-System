#!/usr/bin/env bash
set -euo pipefail

TARGET_BRANCH="${AGENT_FINISH_TARGET_BRANCH:-master}"

current_branch="$(git branch --show-current)"
if [[ -z "${current_branch}" ]]; then
  printf '%s\n' "agent-finish: detached HEAD is not supported" >&2
  exit 1
fi

if [[ "${current_branch}" != "${TARGET_BRANCH}" ]]; then
  if ! git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
    printf '%s\n' "agent-finish: target branch '${TARGET_BRANCH}' does not exist" >&2
    exit 1
  fi

  target_worktree="$(
    git worktree list --porcelain \
      | awk -v branch="refs/heads/${TARGET_BRANCH}" '
          /^worktree / { path = substr($0, 10) }
          /^branch / && substr($0, 8) == branch { print path; exit }
        '
  )"

  if [[ -z "${target_worktree}" ]]; then
    printf '%s\n' "agent-finish: target branch '${TARGET_BRANCH}' is not checked out in a worktree" >&2
    exit 1
  fi

  # Only tracked modifications can be clobbered by the merge. Untracked files
  # (agent logs, scratch output) are ignored here.
  if [[ -n "$(git -C "${target_worktree}" status --porcelain --untracked-files=no)" ]]; then
    printf '%s\n' "agent-finish: target worktree '${target_worktree}' has uncommitted tracked changes" >&2
    exit 1
  fi
fi

# Run the complete repository gate before creating a commit. The commit hook
# repeats this check, but keeping it here ensures a failed check cannot leave a
# commit behind before the merge step is even considered.
if ! uv run pre-commit run --all-files; then
  printf '%s\n' "agent-finish: pre-commit checks failed; refusing commit and merge" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "chore: finish ${current_branch}"
fi

if [[ "${current_branch}" == "${TARGET_BRANCH}" ]]; then
  printf '%s\n' "agent-finish: ok"
  exit 0
fi

git -C "${target_worktree}" merge --no-ff "${current_branch}" \
  -m "Merge branch '${current_branch}'"

printf '%s\n' "agent-finish: committed and merged ${current_branch} into ${TARGET_BRANCH}"
