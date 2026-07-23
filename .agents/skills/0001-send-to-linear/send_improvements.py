import json
import subprocess
import sys
from pathlib import Path


def infer_label(tags: list[str], category: str) -> str:
    tagset = {t.lower() for t in tags}
    cat_lower = category.lower()
    if {"correctness", "security", "bug"} & tagset or "error handling" in cat_lower:
        return "Bug"
    if "feature" in tagset or "features" in cat_lower:
        return "Feature"
    return "Improvement"


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <project> <improvements.json>")
        sys.exit(1)

    project = sys.argv[1]
    path = Path(sys.argv[2])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    opportunities = data if isinstance(data, list) else data.get("opportunities", [])
    total = len(opportunities)

    for i, opp in enumerate(opportunities, 1):
        short_title = opp["short_title"]
        tags = opp.get("additional_fields", {}).get("tags", [])
        category = opp.get("category", "")
        priority = opp.get("additional_fields", {}).get("priority", "none")
        label = infer_label(tags, category)
        body = json.dumps(opp, ensure_ascii=False)

        print(f"Creating issue {i} of {total}: {short_title} (priority={priority}, label={label})")

        result = subprocess.run(
            [
                "orca", "linear", "create",
                "--team", "GUI",
                "--project", project,
                "--title", short_title,
                "--body", body,
                "--assignee", "me",
                "--state", "Backlog",
                "--priority", priority,
                "--label", label,
                "--json",
            ],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode == 0:
            try:
                parsed = json.loads(result.stdout)
                issue_url = parsed.get("url", parsed.get("id", "unknown"))
                print(f"  \u2713 Created: {issue_url}")
            except json.JSONDecodeError:
                print(f"  \u2713 Created (raw): {result.stdout.strip()}")
        else:
            print(f"  \u2717 Failed: {result.stderr.strip()}", file=sys.stderr)

    print(f"\nDone! {total} issues created.")


if __name__ == "__main__":
    main()
