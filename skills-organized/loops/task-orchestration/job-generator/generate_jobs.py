#!/usr/bin/env python3
"""Generate JSON job files for the skill-dispatcher skill.

Reads an agent-routing config to decide which agent handles each skill prefix,
then produces a ready-to-run jobs JSON file.

Usage:
  generate_jobs.py create  --skills s1 [s2 ...] [--output jobs.json]
  generate_jobs.py create  --from-file requests.json [--output jobs.json]
  generate_jobs.py routing [--routing-file agent-routing.json]

  create      Build a dispatcher-compatible jobs JSON file.
  routing     Show the current routing table and which agent owns each prefix.

The requests file (--from-file) accepts either:
  1. A plain list of skill names:   ["coding--analyze--general", "coding--analyze--ui-ux"]
  2. A list of objects:
     [
       {"skill": "coding--analyze--general", "skill_args": "focus on API"},
       {"skill": "devops--linear--send"}
     ]
  3. An object with a "requests" key wrapping either format above.

Each object may override any job field (agent, worktree, retries, etc.);
omitted fields are filled from the routing config + defaults.
"""
import argparse
import json
import os
import re
import sys


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_ROUTING_FILE = os.path.join(_SCRIPT_DIR, "agent-routing.json")


# ---------------------------------------------------------------------------
# Routing config
# ---------------------------------------------------------------------------

def load_routing(path):
    """Load and validate the routing config."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rules = data.get("routing", [])
    if not isinstance(rules, list):
        raise ValueError("routing must be a list of {prefix, agent} objects")
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict) or "prefix" not in rule or "agent" not in rule:
            raise ValueError(f"routing[{idx}] must have 'prefix' and 'agent'")

    # Sort by prefix length descending so longest-prefix match wins.
    rules.sort(key=lambda r: len(r["prefix"]), reverse=True)

    return {
        "rules": rules,
        "default_agent": data.get("default_agent", "claude"),
        "defaults": data.get("defaults", {}),
    }


def resolve_agent(skill_name, routing):
    """Return the agent for a skill based on longest-prefix match."""
    for rule in routing["rules"]:
        if skill_name.startswith(rule["prefix"]):
            return rule["agent"]
    return routing["default_agent"]


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def _slugify(text, max_len=40):
    """Turn a skill name into a safe worktree / job name slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len]


def load_requests(path):
    """Load a requests file (list of strings or objects, or wrapped in {requests: ...})."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("requests", data.get("jobs", []))
    if not isinstance(items, list):
        raise ValueError("requests file must be a list or contain a 'requests'/'jobs' list")
    return [_normalize_request(item, idx) for idx, item in enumerate(items)]


def _normalize_request(item, index):
    """Accept either a plain string (skill name) or a dict with optional overrides."""
    if isinstance(item, str):
        return {"skill": item}
    if isinstance(item, dict):
        if "skill" not in item and "prompt" not in item:
            raise ValueError(
                f"request[{index}]: must have 'skill' or 'prompt'"
            )
        return item
    raise ValueError(f"request[{index}]: must be a string (skill name) or an object")


def requests_from_cli_skills(skill_names):
    """Convert a list of CLI --skills arguments into request dicts."""
    return [{"skill": s} for s in skill_names]


# ---------------------------------------------------------------------------
# Job generation
# ---------------------------------------------------------------------------

def build_job(request, index, routing):
    """Build a single dispatcher-compatible job dict from a request + routing."""
    defaults = routing.get("defaults", {})

    skill = request.get("skill")
    prompt = request.get("prompt")

    # Determine agent: explicit override > routing table > default.
    if request.get("agent"):
        agent = request["agent"]
    elif skill:
        agent = resolve_agent(skill, routing)
    else:
        agent = request.get("agent") or routing["default_agent"]

    # Name: explicit > slugified skill > job-N.
    name = request.get("name") or (_slugify(skill) if skill else f"job-{index}")

    # Worktree: explicit override > defaults (with auto-generated name).
    if request.get("worktree"):
        worktree = request["worktree"]
    else:
        wt_defaults = defaults.get("worktree", {})
        worktree = {
            "mode": wt_defaults.get("mode", "new"),
            "name": name,
        }
        if wt_defaults.get("repo"):
            worktree["repo"] = wt_defaults["repo"]
        if wt_defaults.get("base_branch"):
            worktree["base_branch"] = wt_defaults["base_branch"]

    job = {
        "name": name,
        "agent": request.get("command") and None or agent,
        "worktree": worktree,
    }

    # Skill or prompt.
    if skill:
        job["skill"] = skill
        if request.get("skill_args"):
            job["skill_args"] = request["skill_args"]
    elif prompt:
        job["prompt"] = prompt

    # Command override (replaces agent).
    if request.get("command"):
        job.pop("agent", None)
        job["command"] = request["command"]

    # Retry policy: explicit > defaults.
    job["retries"] = request.get("retries", defaults.get("retries", 0))
    job["retry_delay_seconds"] = request.get(
        "retry_delay_seconds", defaults.get("retry_delay_seconds", 5)
    )

    # Keep open.
    if request.get("keep_open"):
        job["keep_open"] = True

    # Clean up None values.
    return {k: v for k, v in job.items() if v is not None}


def generate_jobs(requests, routing):
    """Build the full jobs list from a list of request dicts."""
    seen_names = set()
    jobs = []
    for idx, req in enumerate(requests):
        job = build_job(req, idx, routing)
        # Deduplicate worktree/job names by appending a counter.
        base_name = job["name"]
        if base_name in seen_names:
            counter = 2
            while f"{base_name}-{counter}" in seen_names:
                counter += 1
            job["name"] = f"{base_name}-{counter}"
            job["worktree"]["name"] = job["name"]
        seen_names.add(job["name"])
        jobs.append(job)
    return jobs


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    routing = load_routing(args.routing_file)

    if args.from_file:
        requests = load_requests(args.from_file)
    elif args.skills:
        requests = requests_from_cli_skills(args.skills)
    else:
        print(json.dumps({"error": "provide --skills or --from-file"}))
        sys.exit(1)

    jobs = generate_jobs(requests, routing)
    output = {"jobs": jobs}

    if args.output and args.output != "-":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")
        # Also print a summary to stdout.
        summary = []
        for j in jobs:
            agent = j.get("agent") or j.get("command", "?")
            skill_or_prompt = j.get("skill") or "(prompt)"
            summary.append({"name": j["name"], "agent": agent, "skill": skill_or_prompt})
        print(json.dumps({
            "event": "jobs_generated",
            "output_file": os.path.abspath(args.output),
            "count": len(jobs),
            "jobs": summary,
        }, indent=2))
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_routing(args):
    routing = load_routing(args.routing_file)
    table = []
    for rule in routing["rules"]:
        table.append({"prefix": rule["prefix"], "agent": rule["agent"]})
    print(json.dumps({
        "routing": table,
        "default_agent": routing["default_agent"],
        "defaults": routing.get("defaults", {}),
    }, indent=2))


def build_parser():
    p = argparse.ArgumentParser(
        description="Generate dispatcher-compatible job files with agent routing."
    )
    p.add_argument(
        "--routing-file", default=_DEFAULT_ROUTING_FILE,
        help=f"Path to agent-routing.json (default: {_DEFAULT_ROUTING_FILE})"
    )
    sub = p.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Generate a jobs JSON file")
    group = create.add_mutually_exclusive_group()
    group.add_argument(
        "--skills", nargs="+", metavar="SKILL",
        help="Skill names to include (e.g. coding--analyze--general coding--analyze--ui-ux)"
    )
    group.add_argument(
        "--from-file", metavar="PATH",
        help="Path to a JSON file with requests (list of skill names or objects)"
    )
    create.add_argument(
        "--output", "-o", default="-",
        help="Output file path (default: stdout)"
    )
    create.set_defaults(func=cmd_create)

    routing_cmd = sub.add_parser("routing", help="Show the current routing table")
    routing_cmd.set_defaults(func=cmd_routing)

    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
