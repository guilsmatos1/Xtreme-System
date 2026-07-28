#!/usr/bin/env python3
"""Helper for the loops--task-orchestration--skill-dispatcher skill.

Runs the mechanical parts of dispatching ONE job -- a `/skill` invocation on a
specific Orca agent (claude, codex, omp, pi, grok, ...), in either a fresh
worktree, an existing one, or the current one -- and waits for the worker to
report completion (or escalation) through Orca Orchestration before closing
its terminal window.

Deliberately does NOT decide anything the skill's documented rules do not
already fix. Anything unexpected (an escalation, a missing handle, a timeout)
is returned as structured JSON so the calling agent applies judgment instead
of this script guessing silently.

Usage:
  run_jobs.py list-jobs --jobs-file jobs.json [--json]
  run_jobs.py run-jobs  --jobs-file jobs.json [--coordinator-handle term_xxx]
                        [--resume] [--json]
  run_jobs.py start-job --jobs-file jobs.json --index 0 --coordinator-handle term_xxx [--json]
  run_jobs.py wait-job  --task-id task_x --dispatch-id ctx_x --coordinator-handle term_xxx \\
                        --worker-handle term_yyy [--json]

start-job/wait-job print one JSON object to stdout:
  {"status": "pending"|"done"|"escalation"|"stuck"|"error",
   "name": "...", "reason": "...", "detail": {...}, "warnings": [...]}
list-jobs prints the parsed/validated compact job list. run-jobs prints
JSONL progress events plus a final summary object.

New features:
  A. Checkpointing / Resume: progress is saved to a sidecar file
     <jobs-file>.state.json after each completed job. Pass --resume to
     skip jobs whose name already appears with status 'done' in that file.
  B. Retry Policy: each job may declare "retries": N and
     "retry_delay_seconds": M to automatically retry on transient errors
     before propagating failure to the summary.
  D. Static Skill Validation: before the first job starts, all skill names
     declared in the jobs file are checked against the local skills
     directories. Unknown skills produce an immediate error.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

OUTPUT_SNIPPET_LIMIT = 400
DETAIL_STRING_LIMIT = 240
DETAIL_LIST_LIMIT = 5
DETAIL_DICT_LIMIT = 12
LOCK_FILENAME = ".run-jobs.lock"
KNOWN_AGENT_IDS = ("claude", "codex", "omp", "pi", "grok", "opencode", "gemini", "droid", "cursor")

# Directories (relative to repo root or absolute) searched by skill validation (D).
# Each entry is tried relative to the CWD and relative to this script's directory.
_SKILL_SEARCH_DIRS = (
    ".agents/skills",
    "skills-organized",
)
# State file suffix appended to the jobs file path for checkpointing (A).
_STATE_SUFFIX = ".state.json"


def _use_rtk():
    return shutil.which("rtk") is not None


def _tool_command(tool, args):
    return (["rtk", tool] if _use_rtk() else [tool]) + list(args)


def _output_from(proc):
    return (proc.stdout or "") + (proc.stderr or "")


def _compact_text(text, limit=OUTPUT_SNIPPET_LIMIT):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…[truncated {len(text) - limit} chars]"


def _compact_detail(value, depth=0):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _compact_text(value, DETAIL_STRING_LIMIT)
    if depth >= 3:
        return _compact_text(repr(value), DETAIL_STRING_LIMIT)
    if isinstance(value, list):
        items = [_compact_detail(item, depth + 1) for item in value[:DETAIL_LIST_LIMIT]]
        if len(value) > DETAIL_LIST_LIMIT:
            items.append(f"…[truncated {len(value) - DETAIL_LIST_LIMIT} items]")
        return items
    if isinstance(value, dict):
        compact = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= DETAIL_DICT_LIMIT:
                compact["…"] = f"truncated {len(value) - DETAIL_DICT_LIMIT} keys"
                break
            compact[str(key)] = _compact_detail(item, depth + 1)
        return compact
    return _compact_text(repr(value), DETAIL_STRING_LIMIT)


def _compact_warnings(warnings):
    if not warnings:
        return warnings
    return [_compact_text(w, OUTPUT_SNIPPET_LIMIT) for w in warnings]


class OrcaError(RuntimeError):
    def __init__(self, args, command, code, output, reason=None):
        prefix = f"{' '.join(command)} failed (code {code})"
        if reason:
            prefix = f"{prefix}: {reason}"
        snippet = _compact_text(output)
        super().__init__(f"{prefix}: {snippet}" if snippet else prefix)
        self.args_ = args
        self.command = command
        self.code = code
        self.output = output


def orca(args, timeout=60):
    command = _tool_command("orca", [*args, "--json"])
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    out = _output_from(proc)
    if proc.returncode != 0:
        raise OrcaError(args, command, proc.returncode, out)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise OrcaError(args, command, proc.returncode, out, "invalid JSON")


def result(status, name, reason=None, detail=None, warnings=None):
    payload = {"status": status, "name": name}
    if reason is not None:
        payload["reason"] = _compact_text(reason, OUTPUT_SNIPPET_LIMIT)
    if detail is not None:
        payload["detail"] = _compact_detail(detail)
    compact_warnings = _compact_warnings(warnings)
    if compact_warnings:
        payload["warnings"] = compact_warnings
    print(json.dumps(payload))
    return payload


def emit_event(payload):
    print(json.dumps(payload, separators=(",", ":")), flush=True)
    return payload


# --- Job parsing -----------------------------------------------------------

def load_jobs(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError("jobs file must contain a list, or an object with a 'jobs' list")
    return [validate_job(job, idx) for idx, job in enumerate(jobs)]


def validate_job(job, index):
    if not isinstance(job, dict):
        raise ValueError(f"job[{index}] is not an object")

    name = str(job.get("name") or f"job-{index}")
    skill = job.get("skill")
    prompt = job.get("prompt")
    if not skill and not prompt:
        raise ValueError(f"job '{name}': must set 'skill' (with optional 'skill_args') or a raw 'prompt'")

    agent = job.get("agent")
    command = job.get("command")
    if not agent and not command:
        raise ValueError(f"job '{name}': must set 'agent' (e.g. claude, codex, omp, pi, grok) or a raw 'command'")
    if agent and agent not in KNOWN_AGENT_IDS:
        # Not fatal -- Orca may support newer/installed agents this list doesn't know about --
        # but flag it so the caller notices a likely typo.
        job.setdefault("_warnings", []).append(
            f"agent '{agent}' is not in the known list {KNOWN_AGENT_IDS}; passing through as-is"
        )

    worktree = job.get("worktree") or {"mode": "new"}
    mode = worktree.get("mode", "new")
    if mode not in ("new", "existing", "current"):
        raise ValueError(f"job '{name}': worktree.mode must be 'new', 'existing', or 'current'")
    if mode == "existing" and not worktree.get("selector"):
        raise ValueError(f"job '{name}': worktree.mode 'existing' requires worktree.selector")
    if mode == "new" and not worktree.get("name"):
        raise ValueError(f"job '{name}': worktree.mode 'new' requires worktree.name")

    # B: retry fields — validated here so bad values are caught early.
    retries = job.get("retries", 0)
    retry_delay = job.get("retry_delay_seconds", 5)
    if not isinstance(retries, int) or retries < 0:
        raise ValueError(f"job '{name}': 'retries' must be a non-negative integer")
    if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
        raise ValueError(f"job '{name}': 'retry_delay_seconds' must be a non-negative number")

    return {
        "name": name,
        "skill": skill,
        "skill_args": job.get("skill_args", ""),
        "prompt": prompt,
        "agent": agent,
        "command": command,
        "worktree": worktree,
        "keep_open": bool(job.get("keep_open", False)),
        "retries": retries,                    # B
        "retry_delay_seconds": retry_delay,    # B
        "_warnings": job.get("_warnings", []),
    }


# ---------------------------------------------------------------------------
# D: Static skill validation
# ---------------------------------------------------------------------------

def _discover_local_skills():
    """Return a set of known skill names found in the local skills directories."""
    known = set()
    roots = []
    # Search relative to CWD and relative to this script's directory.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.realpath(os.getcwd())
    for base in (repo_root, script_dir):
        for rel in _SKILL_SEARCH_DIRS:
            candidate = os.path.join(base, rel)
            if os.path.isdir(candidate):
                roots.append(candidate)

    for root in roots:
        for entry in os.scandir(root):
            if entry.is_dir():
                # Accept the raw directory name and the slug with dashes replaced.
                name = entry.name
                known.add(name)
                known.add(name.replace("-", "--"))
                known.add(name.replace("--", "-"))
                # Also accept the last segment (e.g. "general" for "coding--analyze--general")
                known.add(name.split("--")[-1])
                known.add(name.split("-")[-1])
    return known


def validate_skills_exist(jobs):
    """Raise ValueError listing every skill name that cannot be resolved locally.

    Jobs that use a raw `prompt` instead of `skill` are skipped — they do not
    reference a skill directory.
    """
    skills_needed = {job["skill"] for job in jobs if job.get("skill")}
    if not skills_needed:
        return  # all prompt-based jobs, nothing to validate

    known = _discover_local_skills()
    missing = sorted(s for s in skills_needed if s not in known)
    if missing:
        searched = ", ".join(
            os.path.join("<cwd>", d) for d in _SKILL_SEARCH_DIRS
        )
        raise ValueError(
            f"Unknown skill(s): {missing}. "
            f"Searched: {searched}. "
            "Fix the name(s) or add the skill directory before retrying."
        )


# ---------------------------------------------------------------------------
# A: Checkpointing / resume
# ---------------------------------------------------------------------------

def _state_path(jobs_file):
    return os.path.abspath(jobs_file) + _STATE_SUFFIX


def load_state(jobs_file):
    """Return {job_name: status_str} for every job recorded in the state file."""
    path = _state_path(jobs_file)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_state(jobs_file, state):
    """Persist the current state dict to the sidecar file (atomic write)."""
    path = _state_path(jobs_file)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass  # non-fatal; worst case the user re-runs without --resume


def build_task_spec(job):
    if job.get("prompt"):
        return job["prompt"]
    spec = f"Invoke the skill `/{job['skill']}`"
    if job.get("skill_args"):
        spec += f" with these arguments: {job['skill_args']}"
    spec += (
        ". Follow that skill's own SKILL.md exactly. Before acting, judge whether the "
        "request in the arguments actually makes sense for this repo; if it does not, "
        "explain the problem and report that as the outcome instead of forcing a change."
    )
    return spec


# --- Worktree / terminal creation -------------------------------------------

def _extract_handle(response):
    r = response.get("result", {})
    handle = r.get("startupTerminal", {}).get("handle") or r.get("agentTerminalHandle")
    if not handle:
        handle = r.get("terminal", {}).get("handle")
    return handle


def create_worker_terminal(job, warnings):
    """Returns (handle, worktree_selector_or_None, error_reason_or_None)."""
    worktree = job["worktree"]
    mode = worktree["mode"]
    agent_or_command = job.get("command") or job.get("agent")

    if mode == "current":
        term = orca(["terminal", "create", "--worktree", "active",
                     "--title", job["name"], "--command", agent_or_command])
        handle = _extract_handle(term)
        return handle, "active", None if handle else "terminal create returned no handle"

    if mode == "existing":
        selector = worktree["selector"]
        term = orca(["terminal", "create", "--worktree", selector,
                     "--title", job["name"], "--command", agent_or_command])
        handle = _extract_handle(term)
        return handle, selector, None if handle else "terminal create returned no handle"

    # mode == "new"
    args = ["worktree", "create", "--name", worktree["name"]]
    if worktree.get("repo"):
        args += ["--repo", worktree["repo"]]
    if worktree.get("base_branch"):
        args += ["--base-branch", worktree["base_branch"]]
    if worktree.get("parent_worktree"):
        args += ["--parent-worktree", worktree["parent_worktree"]]
    elif worktree.get("no_parent", True):
        args += ["--no-parent"]

    if job.get("command"):
        # Custom argv (e.g. a specific Codex model/effort) is not accepted by
        # `worktree create --agent`, so fall back to the documented two-step path:
        # create the worktree bare, then launch the agent with `terminal create`.
        wt = orca(args)
        selector = wt.get("result", {}).get("worktree", {}).get("id")
        if not selector:
            return None, None, "worktree create returned no worktree id"
        term = orca(["terminal", "create", "--worktree", f"id:{selector}",
                     "--title", job["name"], "--command", job["command"]])
        handle = _extract_handle(term)
        return handle, f"id:{selector}", None if handle else "terminal create returned no handle"

    args += ["--agent", job["agent"]]
    wt = orca(args)
    selector = wt.get("result", {}).get("worktree", {}).get("id")
    handle = _extract_handle(wt)
    if not handle and selector:
        # Older CLIs may omit startupTerminal.handle even with --agent; re-resolve.
        listing = orca(["terminal", "list", "--worktree", f"id:{selector}"])
        terminals = listing.get("result", {}).get("terminals", [])
        if terminals:
            handle = terminals[0].get("handle")
            warnings.append("worktree create omitted startupTerminal.handle; re-resolved via terminal list")
    return handle, (f"id:{selector}" if selector else None), None if handle else "worktree create returned no agent handle"


# --- Orchestration polling ---------------------------------------------------

def _message_payload(msg):
    raw_payload = (msg or {}).get("payload", {})
    if isinstance(raw_payload, str):
        try:
            return json.loads(raw_payload or "{}")
        except json.JSONDecodeError:
            return {}
    return raw_payload or {}


def poll_orchestration(coordinator_handle, task_id, dispatch_id, timeout_ms):
    check = orca(
        ["orchestration", "check", "--terminal", coordinator_handle, "--wait",
         "--types", "worker_done,escalation", "--timeout-ms", str(timeout_ms)],
        timeout=(timeout_ms / 1000) + 30,
    )
    messages = check.get("result", {}).get("messages", [])
    for msg in messages:
        payload = _message_payload(msg)
        if payload.get("taskId") != task_id or payload.get("dispatchId") != dispatch_id:
            continue
        if msg.get("type") == "worker_done":
            return "worker_done", msg
        if msg.get("type") == "escalation":
            return "escalation", msg
    return "timeout", None


def close_worker_terminal(worker_handle, warnings):
    if not worker_handle:
        return
    try:
        orca(["terminal", "close", "--terminal", worker_handle, "--tab"])
    except OrcaError as exc:
        warnings.append(f"failed to close worker terminal {worker_handle}: {exc}")


# --- Coordinator handle inference --------------------------------------------

def resolve_coordinator_handle(explicit, warnings):
    if explicit:
        return explicit

    listing = orca(["terminal", "list"], timeout=30)
    terminals = listing.get("result", {}).get("terminals", [])
    cwd = os.path.realpath(os.getcwd())
    candidates = [
        t for t in terminals
        if t.get("connected") and t.get("writable") and t.get("worktreePath")
        and os.path.realpath(t.get("worktreePath")) == cwd
    ]
    if not candidates:
        raise RuntimeError("could not infer coordinator terminal handle; pass --coordinator-handle")
    candidates.sort(key=lambda t: int(t.get("lastOutputAt") or 0), reverse=True)
    if len(candidates) > 1:
        warnings.append(f"multiple coordinator terminal candidates; selected most recent {candidates[0].get('handle')}")
    return candidates[0].get("handle")


# --- start / wait -------------------------------------------------------------

def cmd_start_job(args):
    jobs = load_jobs(args.jobs_file)
    if not (0 <= args.index < len(jobs)):
        return result("error", "?", reason=f"index {args.index} out of range (0..{len(jobs) - 1})")
    return _start_job(jobs[args.index], args.coordinator_handle, args.wait_timeout_ms)


def _start_job(job, coordinator_handle, wait_timeout_ms):
    name = job["name"]
    warnings = list(job.get("_warnings", []))
    try:
        handle, worktree_selector, error = create_worker_terminal(job, warnings)
        if error:
            return result("error", name, reason=error, warnings=warnings)

        try:
            orca(["terminal", "wait", "--terminal", handle, "--for", "tui-idle", "--timeout-ms", "60000"], timeout=90)
        except OrcaError as exc:
            return result("error", name, reason=f"agent TUI failed to reach tui-idle on startup: {exc}",
                          detail={"handle": handle}, warnings=warnings)

        task = orca(["orchestration", "task-create",
                     "--task-title", name[:60], "--spec", build_task_spec(job)])
        task_id = task.get("result", {}).get("task", {}).get("id")
        if not task_id:
            return result("error", name, reason="task-create returned no task id",
                          detail=_compact_detail(task), warnings=warnings)

        dispatch = orca(["orchestration", "dispatch", "--task", task_id, "--to", handle,
                         "--from", coordinator_handle, "--inject"])
        dispatch_id = dispatch.get("result", {}).get("dispatch", {}).get("id")
        if not dispatch_id:
            return result("error", name, reason="dispatch returned no dispatch id",
                          detail=_compact_detail(dispatch), warnings=warnings)
    except OrcaError as exc:
        return result("error", name, reason=str(exc), warnings=warnings)

    detail = {
        "task_id": task_id, "dispatch_id": dispatch_id,
        "coordinator_handle": coordinator_handle, "worker_handle": handle,
        "worktree": worktree_selector,
    }
    return result("pending", name, detail=detail, warnings=warnings)


def cmd_wait_job(args):
    return _wait_job(args.name or "?", args.task_id, args.dispatch_id, args.coordinator_handle,
                     args.worker_handle, args.wait_timeout_ms, args.keep_open, [])


def _wait_job(name, task_id, dispatch_id, coordinator_handle, worker_handle, wait_timeout_ms, keep_open, warnings):
    context = {"task_id": task_id, "dispatch_id": dispatch_id,
               "coordinator_handle": coordinator_handle, "worker_handle": worker_handle}
    try:
        outcome, msg = poll_orchestration(coordinator_handle, task_id, dispatch_id, wait_timeout_ms)
    except OrcaError as exc:
        return result("error", name, reason=f"orchestration check failed: {exc}", detail=context, warnings=warnings)

    if outcome == "timeout":
        return result("pending", name, detail=context, warnings=warnings)

    if outcome == "escalation":
        # Needs a human -- leave the window open on purpose.
        return result("escalation", name, detail=_compact_detail(msg), warnings=warnings)

    # worker_done: the skill invocation is finished (success or failure is the
    # worker's own report, carried in the message body/payload) -- close the window.
    if not keep_open:
        close_worker_terminal(worker_handle, warnings)
    return result("done", name, detail=_compact_detail(msg), warnings=warnings)


# --- run-jobs -----------------------------------------------------------------

def _call_helper_silently(func, args):
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        return func(args)


def run_one_job(job, args, coordinator_handle):
    """Run a single job, respecting its retry policy (B)."""
    name = job["name"]
    max_retries = job.get("retries", 0)  # B
    retry_delay = job.get("retry_delay_seconds", 5)  # B

    for attempt in range(max_retries + 1):  # B: attempt 0..max_retries
        payload = _run_one_attempt(job, args, coordinator_handle)
        status = payload.get("status")

        # B: only retry transient errors, not escalations / stuck / done.
        if status != "error" or attempt >= max_retries:
            if attempt > 0 and status != "error":
                payload.setdefault("warnings", [])
                payload["warnings"].append(f"succeeded on retry attempt {attempt + 1}/{max_retries + 1}")
            return payload

        # B: transient error — log and wait before next attempt.
        emit_event({
            "event": "retry",
            "name": name,
            "attempt": attempt + 1,
            "max_retries": max_retries,
            "reason": payload.get("reason"),
            "delay_seconds": retry_delay,
        })
        if retry_delay > 0:
            time.sleep(retry_delay)

    return payload  # unreachable but satisfies type checkers


def _run_one_attempt(job, args, coordinator_handle):
    """Single dispatch+poll cycle for one job (no retry logic here)."""
    name = job["name"]
    started_at = time.monotonic()
    payload = _start_job(job, coordinator_handle, args.wait_timeout_ms)

    while payload.get("status") == "pending":
        detail = payload.get("detail") or {}
        missing = [k for k in ("task_id", "dispatch_id", "coordinator_handle") if not detail.get(k)]
        if missing:
            return {"status": "error", "name": name,
                    "reason": f"pending result missing {', '.join(missing)}", "detail": detail}

        remaining = args.job_timeout_seconds - (time.monotonic() - started_at)
        if remaining <= 0:
            return {"status": "stuck", "name": name, "reason": "job timeout exceeded", "detail": detail}

        chunk_ms = min(args.wait_timeout_ms, max(1000, int(remaining * 1000)))
        payload = _wait_job(name, detail["task_id"], detail["dispatch_id"], detail["coordinator_handle"],
                            detail.get("worker_handle"), chunk_ms, job.get("keep_open", False), [])

    return payload


def record_job(summary, job, payload):
    status = payload.get("status")
    event = {"event": "job", "name": job["name"], "status": status}
    for key in ("reason", "warnings"):
        if payload.get(key):
            event[key] = payload[key]
    if status in ("error", "escalation", "stuck") and payload.get("detail") is not None:
        event["detail"] = payload["detail"]

    summary["processed"] += 1
    if status in ("done", "escalation", "stuck"):
        summary[status] += 1
    elif status == "error":
        summary["errors"].append({"name": job["name"], "reason": payload.get("reason"), "detail": payload.get("detail")})
    if payload.get("warnings"):
        summary["warnings"].append({"name": job["name"], "warnings": payload["warnings"]})

    emit_event(event)
    return status


def _lock_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), LOCK_FILENAME)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextlib.contextmanager
def run_jobs_lock():
    """Refuse a second concurrent run-jobs, same rationale as the sequential-worktree skill:
    a foreground call killed by a harness timeout does not stop the worker it already
    dispatched, so a second run would race it with its own independent job list."""
    path = _lock_path()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        stale_pid = None
        try:
            with open(path) as f:
                stale_pid = int(f.read().strip())
        except (OSError, ValueError):
            pass
        if stale_pid is not None and _pid_alive(stale_pid):
            raise RuntimeError(
                f"another run-jobs is already active (pid={stale_pid}); refusing to start a "
                f"second instance. Confirm that pid is actually dead before removing {path}."
            )
        os.unlink(path)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        yield
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def cmd_list_jobs(args):
    return emit_event({"jobs": load_jobs(args.jobs_file)})


def cmd_run_jobs(args):
    summary = {
        "event": "summary", "status": "completed", "processed": 0,
        "done": 0, "escalation": 0, "stuck": 0, "errors": [], "warnings": [],
    }
    try:
        with run_jobs_lock():
            jobs = load_jobs(args.jobs_file)

            # D: validate all skill names before starting any work.
            try:
                validate_skills_exist(jobs)
            except ValueError as exc:
                summary["status"] = "error"
                summary["errors"].append({"reason": f"skill validation failed: {exc}"})
                return emit_event(summary)

            # A: load persisted state when --resume is set.
            state = load_state(args.jobs_file) if getattr(args, "resume", False) else {}
            if state:
                skipped = [j["name"] for j in jobs if state.get(j["name"]) == "done"]
                if skipped:
                    emit_event({"event": "resume", "skipping": skipped})

            coordinator_handle = resolve_coordinator_handle(args.coordinator_handle, summary["warnings"])
            emit_event({"event": "jobs_loaded", "count": len(jobs)})

            for job in jobs:
                # A: skip jobs already completed in a previous run.
                if state.get(job["name"]) == "done":
                    emit_event({"event": "skipped", "name": job["name"], "reason": "already done (resume)"})
                    summary["processed"] += 1
                    summary["done"] += 1
                    continue

                payload = run_one_job(job, args, coordinator_handle)
                status = record_job(summary, job, payload)

                # A: persist state after each job so --resume can skip it next time.
                if status == "done":
                    state[job["name"]] = "done"
                    save_state(args.jobs_file, state)

                if status == "error":
                    summary["status"] = "error"
                    return emit_event(summary)
    except (OrcaError, RuntimeError, ValueError) as exc:
        summary["status"] = "error"
        summary["errors"].append({"reason": str(exc)})
        return emit_event(summary)

    return emit_event(summary)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--wait-timeout-ms", type=int, default=480000,
                        help="Bounded poll chunk (default 8min, stays under tool call limits)")
    common.add_argument("--json", action="store_true", help="No-op; output is always JSON")

    list_jobs = sub.add_parser("list-jobs", parents=[common])
    list_jobs.add_argument("--jobs-file", required=True)
    list_jobs.set_defaults(func=cmd_list_jobs)

    start_job = sub.add_parser("start-job", parents=[common])
    start_job.add_argument("--jobs-file", required=True)
    start_job.add_argument("--index", type=int, required=True)
    start_job.add_argument("--coordinator-handle", required=True)
    start_job.set_defaults(func=cmd_start_job)

    wait_job = sub.add_parser("wait-job", parents=[common])
    wait_job.add_argument("--name")
    wait_job.add_argument("--task-id", required=True)
    wait_job.add_argument("--dispatch-id", required=True)
    wait_job.add_argument("--coordinator-handle", required=True)
    wait_job.add_argument("--worker-handle")
    wait_job.add_argument("--keep-open", action="store_true")
    wait_job.set_defaults(func=cmd_wait_job)

    run_jobs = sub.add_parser("run-jobs", parents=[common])
    run_jobs.add_argument("--jobs-file", required=True)
    run_jobs.add_argument("--coordinator-handle")
    run_jobs.add_argument("--job-timeout-seconds", type=int, default=7200)
    run_jobs.add_argument(
        "--resume", action="store_true",
        help="Skip jobs whose name already appears as 'done' in the state sidecar file (A)."
    )
    run_jobs.set_defaults(func=cmd_run_jobs)

    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001 - must always emit exactly one JSON line, never a bare traceback
        result("error", "?", reason=f"{type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
