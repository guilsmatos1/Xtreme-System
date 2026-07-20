import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ALEMBIC_INI = Path("alembic.ini")


def _down_revs(revision_str: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if revision_str is None:
        return []
    if isinstance(revision_str, (list, tuple)):
        return list(revision_str)
    return [revision_str]


def _check_chain() -> None:
    if not _ALEMBIC_INI.exists():
        print("alembic.ini not found — skipping migration chain check")
        return

    cfg = Config(str(_ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)

    revisions_map = {r.revision: r for r in script.walk_revisions()}

    for rev in script.walk_revisions():
        for dr_id in _down_revs(rev.down_revision):
            if dr_id is not None and dr_id not in revisions_map:
                print(
                    f"ERROR: revision {rev.revision} references "
                    f"non-existent down_revision {dr_id}"
                )
                sys.exit(1)

    heads = script.get_heads()
    if len(heads) > 1:
        unmerged = [h for h in heads if not revisions_map[h].is_merge_point]
        if unmerged:
            print(
                f"ERROR: {len(heads)} heads detected but branch heads "
                f"are not merged: {unmerged}"
            )
            sys.exit(1)

    print(f"alembic chain OK ({len(heads)} head(s), {len(revisions_map)} revision(s))")


if __name__ == "__main__":
    _check_chain()
