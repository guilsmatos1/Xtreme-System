import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent
DELETE_DONE_SCRIPT = SKILL_DIR / "delete_done_issues.py"

LIMIT_EXCEEDED_CODE = "linear_write_failed"
LIMIT_EXCEEDED_MSG = "Usage limit exceeded"
OPPORTUNITY_HEADING_RE = re.compile(
    r"^##\s+(imp-\d{8}-\d{3})\s+(?:—|-)\s+(.+?)\s*$",
    re.MULTILINE,
)
# Any level-two heading that is not an opportunity, such as the trailing
# "## Discarded candidates" section required by the issues contract.
TRAILING_SECTION_RE = re.compile(
    r"^##\s+(?!imp-\d{8}-\d{3}\b)",
    re.MULTILINE,
)


def infer_label(tags: list[str], category: str) -> str:
    tagset = {t.lower() for t in tags}
    cat_lower = category.lower()
    if {"correctness", "security", "bug"} & tagset or "error handling" in cat_lower:
        return "Bug"
    if "feature" in tagset or "features" in cat_lower:
        return "Feature"
    return "Improvement"


def _markdown_field(section: str, label: str, default: str = "") -> str:
    match = re.search(
        rf"^-\s+\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$",
        section,
        re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip() if match else default


def parse_markdown_opportunities(text: str) -> list[dict]:
    """Parse the small metadata header of each Markdown opportunity.

    The complete section remains the Linear body; only routing fields are
    extracted, so narrative Markdown and code fences need no special parsing.
    """
    matches = list(OPPORTUNITY_HEADING_RE.finditer(text))
    opportunities = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        trailing = TRAILING_SECTION_RE.search(text, match.end())
        if trailing and trailing.start() < end:
            end = trailing.start()
        body = text[match.start():end].strip()
        tags = [
            tag.strip().strip("`")
            for tag in _markdown_field(body, "Tags").split(",")
            if tag.strip()
        ]
        opportunities.append({
            "id": match.group(1),
            "short_title": match.group(2).strip(),
            "category": _markdown_field(body, "Category"),
            "estimated_effort": _markdown_field(body, "Estimated effort", "Low"),
            "additional_fields": {
                "priority": _markdown_field(body, "Priority", "none").lower(),
                "tags": tags,
            },
            "_markdown_body": body,
        })
    if not opportunities:
        raise ValueError(
            "no opportunities found; expected headings like "
            "'## imp-YYYYMMDD-NNN — Short title'"
        )
    return opportunities


def _markdown_value(value, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            label = str(key).replace("_", " ").capitalize()
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- **{label}:**")
                lines.extend(_markdown_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- **{label}:** {item}")
        return lines
    if isinstance(value, list):
        return [
            f"{prefix}- {item}" if not isinstance(item, (dict, list))
            else "\n".join([f"{prefix}-", *_markdown_value(item, indent + 1)])
            for item in value
        ] or [f"{prefix}- None"]
    return [f"{prefix}{value}"]


def opportunity_to_markdown(opp: dict) -> str:
    """Render legacy JSON opportunities as Markdown before sending to Linear."""
    additional = opp.get("additional_fields", {})
    lines = [
        f"## {opp.get('id', 'imp-legacy-000')} — {opp['short_title']}",
        "",
        f"- **Impact:** {opp.get('impact', 'Medium')}",
        f"- **Category:** {opp.get('category', 'Improvement')}",
        f"- **Estimated effort:** {opp.get('estimated_effort', 'Low')}",
        f"- **Priority:** {additional.get('priority', 'none')}",
        f"- **Risk level:** {additional.get('risk_level', 'medium')}",
        f"- **Tags:** {', '.join(additional.get('tags', [])) or 'None'}",
        "",
    ]
    location = opp.get("location")
    if location:
        lines.extend([
            "### Location",
            "",
            f"`{location.get('file')}:{location.get('line_start')}`"
            f" — `{location.get('function', '')}`",
            "",
            "```",
            str(location.get("snippet", "")).rstrip(),
            "```",
            "",
        ])
    section_keys = {
        "description": "Description",
        "why_it_matters": "Why it matters",
        "concrete_fix": "Concrete fix",
        "example": "Example",
        "potential_savings": "Potential savings",
    }
    for key, heading in section_keys.items():
        if opp.get(key):
            lines.extend([f"### {heading}", "", str(opp[key]).strip(), ""])
    extras = {
        key: value
        for key, value in additional.items()
        if key not in {"priority", "risk_level", "tags"}
    }
    if extras:
        lines.extend(["### Additional details", "", *_markdown_value(extras), ""])
    if opp.get("self_critique"):
        lines.extend([
            "### Self-critique",
            "",
            *_markdown_value(opp["self_critique"]),
            "",
        ])
    return "\n".join(lines).strip()


def load_opportunities(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".md", ".markdown"}:
        return parse_markdown_opportunities(text)
    data = json.loads(text)
    opportunities = data if isinstance(data, list) else data.get("opportunities", [])
    for opportunity in opportunities:
        opportunity["_markdown_body"] = opportunity_to_markdown(opportunity)
    return opportunities


def is_limit_exceeded(result: subprocess.CompletedProcess) -> bool:
    """Detecta o erro de limite de issues do plano gratuito do Linear."""
    try:
        data = json.loads(result.stdout)
        err = data.get("error", {})
        return (
            err.get("code") == LIMIT_EXCEEDED_CODE
            and LIMIT_EXCEEDED_MSG in err.get("message", "")
        )
    except (json.JSONDecodeError, AttributeError):
        return False


def run_delete_done(team: str = "GUI") -> bool:
    """Roda o helper que cancela todas as issues Done para liberar slots."""
    print(f"\n⚠️  Limite de issues atingido. Cancelando issues concluídas do time {team}...")
    result = subprocess.run(
        [sys.executable, str(DELETE_DONE_SCRIPT), "--team", team],
        timeout=300,
    )
    return result.returncode == 0


def create_issue(project: str, opp: dict, retry: bool = False) -> tuple[bool, bool]:
    """Tenta criar uma issue. Retorna (sucesso, limite_excedido)."""
    short_title = opp["short_title"]
    tags = opp.get("additional_fields", {}).get("tags", [])
    category = opp.get("category", "")
    priority = opp.get("additional_fields", {}).get("priority", "none")
    label = infer_label(tags, category)
    body = opp["_markdown_body"]

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
            if parsed.get("ok"):
                issue_url = parsed.get("result", {}).get("issue", {}).get("url") or parsed.get("url", "unknown")
                print(f"  ✓ Created: {issue_url}")
                return True, False
            if is_limit_exceeded(result) or (
                parsed.get("error", {}).get("code") == LIMIT_EXCEEDED_CODE
            ):
                return False, True
        except json.JSONDecodeError:
            print(f"  ✓ Created (raw): {result.stdout.strip()}")
            return True, False

    # stdout com code 1 pode conter o JSON de erro
    if is_limit_exceeded(result):
        return False, True

    try:
        parsed = json.loads(result.stdout)
        if is_limit_exceeded(result) or (
            not parsed.get("ok")
            and LIMIT_EXCEEDED_MSG in parsed.get("error", {}).get("message", "")
        ):
            return False, True
    except (json.JSONDecodeError, AttributeError):
        pass

    print(f"  ✗ Failed: {result.stderr.strip()}", file=sys.stderr)
    return False, False


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <project> <issues.md|legacy.json>")
        sys.exit(1)

    project = sys.argv[1]
    path = Path(sys.argv[2])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    try:
        opportunities = load_opportunities(path)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid issues file: {exc}", file=sys.stderr)
        sys.exit(1)
    total = len(opportunities)

    freed_done = False  # garante que o cleanup roda no máximo uma vez

    for i, opp in enumerate(opportunities, 1):
        short_title = opp["short_title"]
        tags = opp.get("additional_fields", {}).get("tags", [])
        category = opp.get("category", "")
        priority = opp.get("additional_fields", {}).get("priority", "none")
        label = infer_label(tags, category)

        print(f"Creating issue {i} of {total}: {short_title} (priority={priority}, label={label})")

        success, limit_exceeded = create_issue(project, opp)

        if limit_exceeded and not freed_done:
            # Libera slots cancelando issues Done e tenta de novo
            freed_done = True
            ok = run_delete_done()
            if not ok:
                print("  ✗ Falha ao cancelar issues Done. Abortando.", file=sys.stderr)
                sys.exit(1)
            print(f"\nRetentando issue {i} of {total}: {short_title}")
            success, limit_exceeded2 = create_issue(project, opp)
            if limit_exceeded2:
                print("  ✗ Limite ainda excedido após limpeza. Verifique o plano do Linear.", file=sys.stderr)
                sys.exit(1)

    print(f"\nDone! {total} issues created.")


if __name__ == "__main__":
    main()
