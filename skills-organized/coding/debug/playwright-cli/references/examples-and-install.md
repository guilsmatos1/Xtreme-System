# Examples and installation

## Installation

If global `coding--debug--playwright-cli` command is not available, try a local version via `npx playwright cli`:

```bash
npx --no-install playwright --version
```

When local version is available, use `npx playwright cli` in all commands. Otherwise, install `coding--debug--playwright-cli` as a global command:

```bash
npm install -g @playwright/cli@latest
```


## Example: Form submission

```bash
coding--debug--playwright-cli open https://example.com/form
coding--debug--playwright-cli snapshot

coding--debug--playwright-cli fill e1 "user@example.com"
coding--debug--playwright-cli fill e2 "password123"
coding--debug--playwright-cli click e3
coding--debug--playwright-cli snapshot
coding--debug--playwright-cli close
```


## Example: Multi-tab workflow

```bash
coding--debug--playwright-cli open https://example.com
coding--debug--playwright-cli tab-new https://example.com/other
coding--debug--playwright-cli tab-list
coding--debug--playwright-cli tab-select 0
coding--debug--playwright-cli snapshot
coding--debug--playwright-cli close
```


## Example: Debugging with DevTools

```bash
coding--debug--playwright-cli open https://example.com
coding--debug--playwright-cli click e4
coding--debug--playwright-cli fill e7 "test"
coding--debug--playwright-cli console
coding--debug--playwright-cli requests
coding--debug--playwright-cli close
```

```bash
coding--debug--playwright-cli open https://example.com
coding--debug--playwright-cli tracing-start
coding--debug--playwright-cli click e4
coding--debug--playwright-cli fill e7 "test"
coding--debug--playwright-cli tracing-stop
coding--debug--playwright-cli close
```


## Example: Interactive session

Ask the user for UI review or design feedback. The user draws boxes on the live page and types comments; you receive the annotated screenshot, the snapshot of the marked region, and the user's notes. Use this whenever the user asks for "UI review", "design feedback", or to "ask the user what they think / want / mean":

```bash
coding--debug--playwright-cli open https://example.com
coding--debug--playwright-cli show --annotate
```


## Named sessions (quick)

See also [session-management.md](session-management.md).


```bash
# create new browser session named "mysession" with persistent profile
coding--debug--playwright-cli -s=mysession open example.com --persistent
# same with manually specified profile directory (use when requested explicitly)
coding--debug--playwright-cli -s=mysession open example.com --profile=/path/to/profile
coding--debug--playwright-cli -s=mysession click e6
coding--debug--playwright-cli -s=mysession close  # stop a named browser
coding--debug--playwright-cli -s=mysession delete-data  # delete user data for persistent session

coding--debug--playwright-cli list
# Close all browsers
coding--debug--playwright-cli close-all
# Forcefully kill all browser processes
coding--debug--playwright-cli kill-all
```
