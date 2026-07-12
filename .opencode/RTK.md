# RTK — Rust Token Killer

Token-optimized CLI proxy. Every shell command is auto-rewritten by the openrtk plugin (e.g. `git status` → `rtk git status`), producing compressed output. No manual prefixing needed.

## Commands

```bash
rtk gain              # Token savings summary
rtk gain --history    # Command usage history with savings
rtk discover          # Find missed optimization opportunities
rtk proxy <cmd>       # Raw passthrough without filtering (debug only)
rtk session           # RTK adoption across recent sessions
```

## Key filters for this project

```bash
rtk pytest            # Python tests (failures only, -90%)
rtk ruff check        # Python linting (JSON, -80%)
rtk git status        # Compact status (-80%)
rtk git diff          # Condensed diff (-75%)
rtk git log -n 10     # One-line commits (-80%)
rtk uv run pytest     # Preserve uv env, errors only
rtk ls                # Token-optimized directory tree
```
