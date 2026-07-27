import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent
DELETE_DONE_SCRIPT = SKILL_DIR / "delete_done_issues.py"

LIMIT_EXCEEDED_CODE = "linear_write_failed"
LIMIT_EXCEEDED_MSG = "Usage limit exceeded"


def infer_label(tags: list[str], category: str) -> str:
    tagset = {t.lower() for t in tags}
    cat_lower = category.lower()
    if {"correctness", "security", "bug"} & tagset or "error handling" in cat_lower:
        return "Bug"
    if "feature" in tagset or "features" in cat_lower:
        return "Feature"
    return "Improvement"


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
    body = json.dumps(opp, ensure_ascii=False)

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
