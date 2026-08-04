---
name: coding--debug--playwright-cli
description: Drive a browser with the Playwright CLI (snapshots, clicks, HTMX UI debug). Use when automating or debugging pages in the browser.
allowed-tools: Bash(coding--debug--playwright-cli:*) Bash(npx:*) Bash(npm:*)
metadata:
    skill-organizer:
        original-name: coding--debug--playwright-cli
        source-relative-path: coding/debug/playwright-cli
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Browser Automation with coding--debug--playwright-cli

CLI binary: `coding--debug--playwright-cli`. If missing, try `npx playwright cli` (see [examples-and-install.md](references/examples-and-install.md)).

## Quick start

```bash
coding--debug--playwright-cli open
coding--debug--playwright-cli goto https://playwright.dev
coding--debug--playwright-cli click e15
coding--debug--playwright-cli type "page.click"
coding--debug--playwright-cli press Enter
coding--debug--playwright-cli screenshot
coding--debug--playwright-cli close
```

Prefer `--mobile` on `open` when a phone layout is OK — smaller snapshots, fewer tokens.

## Core loop (every interaction)

1. Act (`goto` / `click` / `fill` / …).
2. Read the snapshot (auto after each command, or `snapshot` / `find`).
3. Target with **refs** from the snapshot (`e15`), not guessed selectors — unless the ref is gone, then CSS / `getByRole` / `getByTestId`.

Efficiency:

- Large page → `find "text"` or `find --regex "..."` instead of a full snapshot
- Partial page → `snapshot --depth=4` then `snapshot e34`
- Pipe only values → `--raw` (see [commands.md](references/commands.md))

## Load references when needed

| Need | Read |
|------|------|
| Any command beyond Quick start (tabs, keyboard, network, DevTools, open/attach flags) | [commands.md](references/commands.md) |
| Snapshot options, boxes, depth, targeting details | [snapshots-and-targeting.md](references/snapshots-and-targeting.md) |
| Named/multi sessions, profiles | [session-management.md](references/session-management.md) |
| Cookies / localStorage | [storage-state.md](references/storage-state.md) |
| Request mocking | [request-mocking.md](references/request-mocking.md) |
| `run-code` / Playwright JS | [running-code.md](references/running-code.md) |
| Element id/class/`data-*` via eval | [element-attributes.md](references/element-attributes.md) |
| Run/debug Playwright test files | [playwright-tests.md](references/playwright-tests.md) |
| Plan / generate / heal tests | [test-generation.md](references/test-generation.md) |
| Tracing | [tracing.md](references/tracing.md) |
| Video | [video-recording.md](references/video-recording.md) |
| Form/multi-tab/UI-annotate examples, install | [examples-and-install.md](references/examples-and-install.md) |

UI review / design feedback from the user → `show --annotate` (details in examples-and-install).
