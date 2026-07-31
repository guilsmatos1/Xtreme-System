#!/usr/bin/env python3
"""Helper for the devops--linear--duplicate-triage skill.

Runs the token-heavy, purely mechanical parts of duplicate triage so the
calling agent doesn't have to pull the full backlog JSON (and every issue's
raw description) into its context:

  1. Pull the open backlog once.
  2. Drop everything that isn't in a candidate state
     (Backlog / Todo).
  3. Recall-safe *blocking*: cheaply group issues whose title/description text
     is similar enough that they *might* be duplicates. Blocking deliberately
     over-groups -- it errs toward keeping a pair together so nothing gets
     hidden from the agent; it never decides that two issues ARE duplicates.
  4. Fetch descriptions (truncated) + createdAt only for issues that landed in
     a multi-issue candidate block, so the agent sees the semantic signal for
     exactly the issues it must judge -- not for the whole backlog.
  5. Suggest a canonical per block using the skill's fixed rule
     (workflow position, then newest createdAt), for the agent to confirm.

What this script does NOT do, by design: it never decides a real duplicate and
never writes to Linear. The semantic call ("are these actually the same
request?") and every `status set` / `comment add` stay with the agent, which
carries the skill's confidence and write-safety rules. Blocks are candidates,
not verdicts; `singletons` are listed compactly so the agent can still override.

Usage:
  triage_backlog.py fetch-candidates [--team GUI] [--workspace <id>]
                                     [--limit 216] [--threshold 0.3]
                                     [--desc-chars 300] [--titles-only|--deep]
                                     [--json]

Output (one JSON object on stdout):
  {"workspace": "<id>", "counts": {...},
   "clusters": [ {"suggested_canonical": "GUI-1",
                  "issues": [ {"id","title","desc","state","priority",
                               "createdAt"}, ... ] }, ... ],
   "singletons": [ {"id","title","state"}, ... ],
   "warnings": [ ... ] }

The agent still applies judgment: confirm/split each cluster, then run the
writes itself following the skill's guardrails.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

DEFAULT_TEAM = "GUI"
DEFAULT_WORKSPACE = "e7ff0c6a-7f22-4abd-85fe-153bb2c72687"
DEFAULT_LIMIT = 216
DEFAULT_THRESHOLD = 0.30
DEFAULT_DESC_CHARS = 300
FETCH_WORKERS = 6

# Only these states are ever duplicate candidates (skill step 2).
CANDIDATE_STATES = {"Backlog", "Todo"}
# Furthest-along-first ranking for picking the canonical (skill step 4).
STATE_RANK = {"Todo": 0, "Backlog": 1}

# Short/common Portuguese + English words that carry no disambiguating signal.
STOPWORDS = {
    "para", "com", "sem", "por", "dos", "das", "que", "uma", "uns", "umas",
    "nao", "sao", "aos", "pelo", "pela", " como", "mais", "the", "and", "for",
    "que", "esta", "este", "isso", "ser", "tem", "foi", "seu", "sua", "num",
    "numa", "ate", "sobre", "quando", "onde", "todo", "toda", "todos", "todas",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _use_rtk():
    return shutil.which("rtk") is not None


def _tool_command(tool, args):
    return (["rtk", tool] if _use_rtk() else [tool]) + list(args)


class OrcaError(RuntimeError):
    pass


def orca(args, timeout=120):
    command = _tool_command("orca", [*args, "--json"])
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        snippet = (proc.stderr or proc.stdout or "").strip()[:400]
        raise OrcaError(f"{' '.join(command)} failed (code {proc.returncode}): {snippet}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise OrcaError(f"{' '.join(command)} returned invalid JSON: {proc.stdout[:400]}")


def _strip_accents(text):
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def tokenize(text):
    """Accent-free, lowercase, length>=3, non-stopword word tokens."""
    normalized = _strip_accents(str(text or "")).lower()
    return {
        tok for tok in TOKEN_RE.findall(normalized)
        if len(tok) >= 3 and tok not in STOPWORDS
    }


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


class UnionFind:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self):
        out = {}
        for node in self.parent:
            out.setdefault(self.find(node), []).append(node)
        return list(out.values())


def _state_name(issue):
    state = issue.get("state") or {}
    return state.get("name") if isinstance(state, dict) else str(state)


def load_candidates(args):
    listing = orca([
        "linear", "list", "--filter", "open", "--team", args.team,
        "--limit", str(args.limit), "--workspace", args.workspace,
    ])
    issues = listing.get("result", {}).get("issues", [])
    candidates = []
    for issue in issues:
        if _state_name(issue) not in CANDIDATE_STATES:
            continue
        identifier = issue.get("identifier")
        if not identifier:
            continue
        candidates.append({
            "id": str(identifier),
            "title": str(issue.get("title", "")),
            "state": _state_name(issue),
            "priority": issue.get("priority"),
            "updatedAt": issue.get("updatedAt"),
        })
    return len(issues), candidates


def fetch_description(args, identifier):
    """Return (createdAt, truncated_description) for one issue, or (None, None)
    on any failure -- a missing description must not abort the whole run."""
    try:
        payload = orca([
            "linear", "issue", identifier, "--workspace", args.workspace,
        ], timeout=60)
    except OrcaError:
        return None, None, f"could not read description for {identifier}"
    issue = payload.get("issue") or payload.get("result", {}).get("issue") or {}
    desc = issue.get("description")
    if isinstance(desc, str) and len(desc) > args.desc_chars:
        desc = desc[:args.desc_chars] + "…"
    return issue.get("createdAt"), desc, None


def block(candidates, threshold, text_of):
    """Recall-safe blocking: union issues whose token sets are similar enough.
    text_of(issue) -> the string to tokenize (title, or title+description)."""
    tokens = {c["id"]: tokenize(text_of(c)) for c in candidates}
    uf = UnionFind([c["id"] for c in candidates])
    ids = [c["id"] for c in candidates]
    for i in range(len(ids)):
        ti = tokens[ids[i]]
        for j in range(i + 1, len(ids)):
            if jaccard(ti, tokens[ids[j]]) >= threshold:
                uf.union(ids[i], ids[j])
    return uf.groups()


def suggest_canonical(issues):
    """Skill step 4: furthest-along state wins; tie-break newest createdAt,
    then newest updatedAt as a fallback when createdAt is absent."""
    def key(issue):
        return (
            STATE_RANK.get(issue.get("state"), len(STATE_RANK)),
            _neg_iso(issue.get("createdAt")),
            _neg_iso(issue.get("updatedAt")),
        )
    return sorted(issues, key=key)[0]["id"]


def _neg_iso(value):
    """Sort key that puts newer ISO timestamps first; missing sorts last."""
    return ("0", "") if not value else ("1", _invert(str(value)))


def _invert(text):
    # Invert chars so a normal ascending sort yields descending (newest-first).
    return "".join(chr(0x10FFFF - ord(ch)) if ord(ch) < 0x10FFFF else ch for ch in text)


def fetch_candidates(args):
    total_open, candidates = load_candidates(args)
    warnings = []
    by_id = {c["id"]: c for c in candidates}

    if args.deep:
        # Fetch descriptions for every candidate, then block on title+desc.
        to_fetch = list(by_id)
    elif args.titles_only:
        to_fetch = []
    else:
        # Two-stage: cheap title blocking picks who is worth a description read.
        title_blocks = block(candidates, args.threshold, lambda c: c["title"])
        to_fetch = [i for g in title_blocks if len(g) > 1 for i in g]

    if to_fetch:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            for identifier, (created, desc, warn) in zip(
                to_fetch, pool.map(lambda i: fetch_description(args, i), to_fetch)
            ):
                by_id[identifier]["createdAt"] = created
                by_id[identifier]["desc"] = desc
                if warn:
                    warnings.append(warn)

    text_of = (lambda c: c["title"]) if args.titles_only else (
        lambda c: c["title"] + " " + str(c.get("desc") or "")
    )
    blocks = block(candidates, args.threshold, text_of)

    clusters, singletons = [], []
    for group in blocks:
        members = [by_id[i] for i in group]
        if len(members) < 2:
            issue = members[0]
            singletons.append({"id": issue["id"], "title": issue["title"], "state": issue["state"]})
            continue
        members.sort(key=lambda m: STATE_RANK.get(m.get("state"), len(STATE_RANK)))
        clusters.append({
            "suggested_canonical": suggest_canonical(members),
            "issues": [_emit_issue(m) for m in members],
        })

    clusters.sort(key=lambda c: c["issues"][0]["id"])
    singletons.sort(key=lambda s: s["id"])
    return {
        "workspace": args.workspace,
        "counts": {
            "open_total": total_open,
            "candidates": len(candidates),
            "clustered": sum(len(c["issues"]) for c in clusters),
            "clusters": len(clusters),
            "singletons": len(singletons),
            "descriptions_fetched": len(to_fetch),
        },
        "clusters": clusters,
        "singletons": singletons,
        "warnings": warnings,
    }


def _emit_issue(issue):
    out = {
        "id": issue["id"],
        "title": issue["title"],
        "state": issue["state"],
        "priority": issue.get("priority"),
    }
    if issue.get("createdAt"):
        out["createdAt"] = issue["createdAt"]
    if issue.get("desc"):
        out["desc"] = issue["desc"]
    return out


def build_parser():
    parser = argparse.ArgumentParser(description="Linear duplicate triage helper")
    sub = parser.add_subparsers(dest="command", required=True)
    fc = sub.add_parser("fetch-candidates", help="Pull, filter, block, and compact the backlog")
    fc.add_argument("--team", default=DEFAULT_TEAM)
    fc.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    fc.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    fc.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="Jaccard similarity to link two issues (lower = more recall-safe)")
    fc.add_argument("--desc-chars", type=int, default=DEFAULT_DESC_CHARS,
                    help="Truncate each fetched description to this many chars")
    group = fc.add_mutually_exclusive_group()
    group.add_argument("--titles-only", action="store_true",
                       help="Never fetch descriptions; block on titles only (cheapest, lower recall)")
    group.add_argument("--deep", action="store_true",
                       help="Fetch every candidate's description and block on title+description (max recall)")
    fc.add_argument("--json", action="store_true", help="Accepted for symmetry; output is always JSON")
    fc.set_defaults(func=fetch_candidates)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload = args.func(args)
    except OrcaError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
