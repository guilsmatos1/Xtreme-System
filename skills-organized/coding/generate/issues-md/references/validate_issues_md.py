#!/usr/bin/env python3
"""Validate an issues Markdown document against references/issues-contract.md.

Two modes:

    python3 validate_issues_md.py --now
        Print the ISO-8601 local timestamp for the `Generated` field and exit.

    python3 validate_issues_md.py <path>
        Report every contract violation at once. Exit 0 when clean, 1 otherwise.

The point of this script is that one run surfaces *all* violations, so the
document is fixed in a single edit instead of a validate/edit/re-validate loop.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

HEADING = re.compile(r"^## (imp-\d{8}-\d{3}) — (.+)$", re.M)
GENERATED = re.compile(r"^- \*\*Generated:\*\* (.+)$", re.M)
TOTAL = re.compile(r"^- \*\*Total:\*\* (\d+)$", re.M)
FENCE = re.compile(r"^```(\w*)$", re.M)

ENUMS = {
    "Impact": {"High", "Medium"},
    "Estimated effort": {"Low", "Medium", "High"},
    "Priority": {"high", "medium", "low"},
    "Risk level": {"high", "medium", "low"},
}

CONSOLIDATION_LABELS = [
    "Duplicate type",
    "All sites",
    "Differences between copies",
    "Behavior preservation",
    "Verification plan",
]


def iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def field(block: str, label: str) -> str | None:
    m = re.search(rf"^- \*\*{re.escape(label)}:\*\* (.+)$", block, re.M)
    return m.group(1).strip() if m else None


def validate(text: str) -> list[str]:
    errors: list[str] = []

    if not text.startswith("# Improvement opportunities"):
        errors.append("header: document must start with '# Improvement opportunities'")

    gen = GENERATED.search(text)
    if not gen:
        errors.append("header: missing '- **Generated:**' line")
    else:
        try:
            stamp = dt.datetime.fromisoformat(gen.group(1).strip())
            if stamp.tzinfo is None:
                errors.append(f"header: Generated '{gen.group(1)}' has no timezone offset")
        except ValueError:
            errors.append(f"header: Generated '{gen.group(1)}' is not ISO-8601")

    headings = HEADING.findall(text)
    ids = [h[0] for h in headings]

    # Catch level-two headings that look like opportunities but break the pattern.
    for line in text.splitlines():
        if line.startswith("## imp") and not HEADING.match(line):
            errors.append(f"heading: does not match contract pattern: {line!r}")

    if not ids:
        errors.append("body: no opportunity headings found")

    seen: set[str] = set()
    for oid in ids:
        if oid in seen:
            errors.append(f"ids: duplicate opportunity id {oid}")
        seen.add(oid)
    if ids != sorted(ids):
        errors.append(f"ids: not in ascending order: {ids}")

    tot = TOTAL.search(text)
    if not tot:
        errors.append("header: missing '- **Total:**' line")
    elif int(tot.group(1)) != len(ids):
        errors.append(
            f"header: Total says {tot.group(1)} but {len(ids)} opportunity headings exist"
        )

    # Per-opportunity checks.
    positions = [m.start() for m in HEADING.finditer(text)]
    discarded = text.find("\n## Discarded candidates")
    bounds = positions + [discarded if discarded != -1 else len(text)]
    for i, oid in enumerate(ids):
        block = text[bounds[i] : bounds[i + 1]]

        for label, allowed in ENUMS.items():
            val = field(block, label)
            if val is None:
                errors.append(f"{oid}: missing '{label}'")
            elif val not in allowed:
                errors.append(f"{oid}: {label}={val!r} not in {sorted(allowed)}")

        conf = field(block, "Confidence")
        if conf is not None:
            try:
                if not 0 <= float(conf.split("/")[0].strip()) <= 10:
                    errors.append(f"{oid}: Confidence {conf!r} outside 0-10")
            except ValueError:
                errors.append(f"{oid}: Confidence {conf!r} is not a number")

        fences = FENCE.findall(block)
        if len(fences) % 2:
            errors.append(f"{oid}: unbalanced code fence")
        for lang in fences:
            if lang.lower() in {"json", "yaml", "yml"}:
                errors.append(
                    f"{oid}: {lang} block — narrative and data belong in Markdown, not blobs"
                )

        location = field(block, "Location")
        has_snippet = "```" in block
        if not has_snippet and location != "Not verified":
            errors.append(f"{oid}: no code snippet and Location is not 'Not verified'")
        if location == "Not verified" and field(block, "Uncertain") != "Yes":
            errors.append(f"{oid}: Location is 'Not verified' but Uncertain is not 'Yes'")

        for m in re.finditer(r"^```\w*$(.*?)^```$", block, re.M | re.S):
            n = len([ln for ln in m.group(1).splitlines() if ln.strip()])
            if n and not 8 <= n <= 12:
                errors.append(f"{oid}: snippet has {n} non-empty lines, contract wants 10-15")

        if "#### Consolidation details" in block:
            missing = [lb for lb in CONSOLIDATION_LABELS if f"**{lb}:**" not in block]
            if missing:
                errors.append(f"{oid}: Consolidation details missing labels: {missing}")

    # Related opportunities must be reciprocal and resolvable.
    related: dict[str, set[str]] = {}
    for i, oid in enumerate(ids):
        block = text[bounds[i] : bounds[i + 1]]
        refs = set(re.findall(r"imp-\d{8}-\d{3}", block)) - {oid}
        related[oid] = refs
        for ref in refs:
            if ref not in seen:
                errors.append(f"{oid}: references unknown opportunity {ref}")
    for oid, refs in related.items():
        for ref in refs:
            if ref in related and oid not in related[ref]:
                errors.append(f"related: {oid} -> {ref} is not reciprocal")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--now", action="store_true", help="print the ISO-8601 Generated stamp")
    args = ap.parse_args()

    if args.now:
        print(iso_now())
        return 0
    if not args.path:
        ap.error("path is required unless --now is given")

    with open(args.path, encoding="utf-8") as fh:
        text = fh.read()

    errors = validate(text)
    if not errors:
        print(f"OK {args.path}: {len(HEADING.findall(text))} opportunities, contract satisfied")
        return 0

    print(f"FAIL {args.path}: {len(errors)} violation(s)")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
