---
name: coding--debug--playwright-cli
description: Automate browser interactions, test web pages and work with Playwright tests.
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

## Quick start

```bash
# open new browser
coding--debug--playwright-cli open
# navigate to a page
coding--debug--playwright-cli goto https://playwright.dev
# interact with the page using refs from the snapshot
coding--debug--playwright-cli click e15
coding--debug--playwright-cli type "page.click"
coding--debug--playwright-cli press Enter
# take a screenshot (rarely used, as snapshot is more common)
coding--debug--playwright-cli screenshot
# close the browser
coding--debug--playwright-cli close
```

## Commands

### Core

```bash
coding--debug--playwright-cli open
# open and navigate right away
coding--debug--playwright-cli open https://example.com/
coding--debug--playwright-cli goto https://playwright.dev
coding--debug--playwright-cli type "search query"
coding--debug--playwright-cli click e3
coding--debug--playwright-cli dblclick e7
# --submit presses Enter after filling the element
coding--debug--playwright-cli fill e5 "user@example.com"  --submit
coding--debug--playwright-cli drag e2 e8
# drop files or data onto an element (from outside the page)
coding--debug--playwright-cli drop e4 --path=./image.png
coding--debug--playwright-cli drop e4 --data="text/plain=hello world"
coding--debug--playwright-cli hover e4
coding--debug--playwright-cli select e9 "option-value"
coding--debug--playwright-cli upload ./document.pdf
coding--debug--playwright-cli check e12
coding--debug--playwright-cli uncheck e12
coding--debug--playwright-cli snapshot
# search the snapshot for text or a regexp, returns matching nodes with surrounding context
coding--debug--playwright-cli find "Sign in"
coding--debug--playwright-cli find --regex "Sign (in|up)"
# wrap the regexp in slashes to add flags, e.g. /i for case-insensitive
coding--debug--playwright-cli find --regex "/sign (in|up)/i"
coding--debug--playwright-cli eval "document.title"
coding--debug--playwright-cli eval "el => el.textContent" e5
# get element id, class, or any attribute not visible in the snapshot
coding--debug--playwright-cli eval "el => el.id" e5
coding--debug--playwright-cli eval "el => el.getAttribute('data-testid')" e5
coding--debug--playwright-cli dialog-accept
coding--debug--playwright-cli dialog-accept "confirmation text"
coding--debug--playwright-cli dialog-dismiss
coding--debug--playwright-cli resize 1920 1080
coding--debug--playwright-cli close
```

### Navigation

```bash
coding--debug--playwright-cli go-back
coding--debug--playwright-cli go-forward
coding--debug--playwright-cli reload
```

### Keyboard

```bash
coding--debug--playwright-cli press Enter
coding--debug--playwright-cli press ArrowDown
coding--debug--playwright-cli keydown Shift
coding--debug--playwright-cli keyup Shift
```

### Mouse

```bash
coding--debug--playwright-cli mousemove 150 300
coding--debug--playwright-cli mousedown
coding--debug--playwright-cli mousedown right
coding--debug--playwright-cli mouseup
coding--debug--playwright-cli mouseup right
coding--debug--playwright-cli mousewheel 0 100
```

### Save as

```bash
coding--debug--playwright-cli screenshot
coding--debug--playwright-cli screenshot e5
coding--debug--playwright-cli screenshot --filename=page.png
coding--debug--playwright-cli screenshot --hires
coding--debug--playwright-cli pdf --filename=page.pdf
```

### Tabs

```bash
coding--debug--playwright-cli tab-list
coding--debug--playwright-cli tab-new
coding--debug--playwright-cli tab-new https://example.com/page
coding--debug--playwright-cli tab-close
coding--debug--playwright-cli tab-close 2
coding--debug--playwright-cli tab-select 0
```

### Storage

```bash
coding--debug--playwright-cli state-save
coding--debug--playwright-cli state-save auth.json
coding--debug--playwright-cli state-load auth.json

# Cookies
coding--debug--playwright-cli cookie-list
coding--debug--playwright-cli cookie-list --domain=example.com
coding--debug--playwright-cli cookie-get session_id
coding--debug--playwright-cli cookie-set session_id abc123
coding--debug--playwright-cli cookie-set session_id abc123 --domain=example.com --httpOnly --secure
coding--debug--playwright-cli cookie-delete session_id
coding--debug--playwright-cli cookie-clear

# LocalStorage
coding--debug--playwright-cli localstorage-list
coding--debug--playwright-cli localstorage-get theme
coding--debug--playwright-cli localstorage-set theme dark
coding--debug--playwright-cli localstorage-delete theme
coding--debug--playwright-cli localstorage-clear

# SessionStorage
coding--debug--playwright-cli sessionstorage-list
coding--debug--playwright-cli sessionstorage-get step
coding--debug--playwright-cli sessionstorage-set step 3
coding--debug--playwright-cli sessionstorage-delete step
coding--debug--playwright-cli sessionstorage-clear
```

### Network

```bash
coding--debug--playwright-cli route "**/*.jpg" --status=404
coding--debug--playwright-cli route "https://api.example.com/**" --body='{"mock": true}'
coding--debug--playwright-cli route-list
coding--debug--playwright-cli unroute "**/*.jpg"
coding--debug--playwright-cli unroute
```

### DevTools

```bash
coding--debug--playwright-cli console
coding--debug--playwright-cli console warning
coding--debug--playwright-cli requests
coding--debug--playwright-cli request 5
coding--debug--playwright-cli run-code "async page => await page.context().grantPermissions(['geolocation'])"
coding--debug--playwright-cli run-code --filename=script.js
coding--debug--playwright-cli tracing-start
coding--debug--playwright-cli tracing-stop
coding--debug--playwright-cli video-start video.webm
coding--debug--playwright-cli video-chapter "Chapter Title" --description="Details" --duration=2000
coding--debug--playwright-cli video-stop

# annotate each subsequent action (click, type, ...) with a callout naming the action and highlighting the target
coding--debug--playwright-cli video-show-actions --duration=600 --position=top-right
coding--debug--playwright-cli video-hide-actions

# launch the dashboard for UI review / design feedback — user annotates the page, you receive the annotated screenshot, snapshot, and notes
coding--debug--playwright-cli show --annotate

# generate a Playwright locator for an element from its ref or selector
coding--debug--playwright-cli generate-locator e5 --raw

# show a persistent highlight overlay for an element, optionally with a custom style
coding--debug--playwright-cli highlight e5
coding--debug--playwright-cli highlight e5 --style="outline: 3px dashed red"
# hide a single element highlight, or all page highlights when no target is given
coding--debug--playwright-cli highlight e5 --hide
coding--debug--playwright-cli highlight --hide
```

## Raw output

The global `--raw` option strips page status, generated code, and snapshot sections from the output, returning only the result value. Use it to pipe command output into other tools. Commands that don't produce output return nothing.

```bash
coding--debug--playwright-cli --raw eval "JSON.stringify(performance.timing)" | jq '.loadEventEnd - .navigationStart'
coding--debug--playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('a')].map(a => a.href))" > links.json
coding--debug--playwright-cli --raw snapshot > before.yml
coding--debug--playwright-cli click e5
coding--debug--playwright-cli --raw snapshot > after.yml
diff before.yml after.yml
TOKEN=$(coding--debug--playwright-cli --raw cookie-get session_id)
coding--debug--playwright-cli --raw localstorage-get theme
```

For structured output wrapping every reply as JSON, pass --json
```bash
coding--debug--playwright-cli list --json
```

## Open parameters
```bash
# Use specific browser when creating session
coding--debug--playwright-cli open --browser=chrome
coding--debug--playwright-cli open --browser=firefox
coding--debug--playwright-cli open --browser=webkit
coding--debug--playwright-cli open --browser=msedge

# Emulate a generic mobile device (Pixel 10 for Chromium, iPhone 17 for WebKit).
# Prefer this when a mobile layout is acceptable: mobile pages are usually
# lighter, so snapshots are smaller and cheaper.
coding--debug--playwright-cli open --mobile
coding--debug--playwright-cli open --device="iPhone 15"

# Use persistent profile (by default profile is in-memory)
coding--debug--playwright-cli open --persistent
# Use persistent profile with custom directory
coding--debug--playwright-cli open --profile=/path/to/profile

# Connect to browser via Playwright Extension
coding--debug--playwright-cli attach --extension=chrome

# Connect to a running Chrome or Edge by channel name
coding--debug--playwright-cli attach --cdp=chrome
coding--debug--playwright-cli attach --cdp=msedge

# Connect to a running browser via CDP endpoint
coding--debug--playwright-cli attach --cdp=http://localhost:9222

# Start with config file
coding--debug--playwright-cli open --config=my-config.json

# Close the browser
coding--debug--playwright-cli close
# Detach from an attached browser (leaves the external browser running)
coding--debug--playwright-cli -s=msedge detach
# Delete user data for the default session
coding--debug--playwright-cli delete-data
```

## URLs with `&` on Windows

On Windows, `cmd.exe` and PowerShell treat `&` as a command separator, so URLs with multiple query parameters get truncated before `coding--debug--playwright-cli` runs. Escape `&` with `^&` in `cmd.exe`, or use `--%` in PowerShell:

```batch
coding--debug--playwright-cli goto "https://example.com/?a=1^&b=2"
```

```powershell
coding--debug--playwright-cli --% goto "https://example.com/?a=1&b=2"
```

## Snapshots

After each command, coding--debug--playwright-cli provides a snapshot of the current browser state.

```bash
> coding--debug--playwright-cli goto https://example.com
### Page
- Page URL: https://example.com/
- Page Title: Example Domain
### Snapshot
[Snapshot](.coding--debug--playwright-cli/page-2026-02-14T19-22-42-679Z.yml)
```

You can also take a snapshot on demand using `coding--debug--playwright-cli snapshot` command. All the options below can be combined as needed.

```bash
# default - save to a file with timestamp-based name
coding--debug--playwright-cli snapshot

# save to file, use when snapshot is a part of the workflow result
coding--debug--playwright-cli snapshot --filename=after-click.yaml

# snapshot an element instead of the whole page
coding--debug--playwright-cli snapshot "#main"

# limit snapshot depth for efficiency, take a partial snapshot afterwards
coding--debug--playwright-cli snapshot --depth=4
coding--debug--playwright-cli snapshot e34

# include each element's bounding box as [box=x,y,width,height]
coding--debug--playwright-cli snapshot --boxes

# search a large snapshot instead of capturing it all — returns matching nodes
# with 3 lines of context around each match (like grep -C)
coding--debug--playwright-cli find "Add to cart"
coding--debug--playwright-cli find --regex "\\$[0-9]+\\.[0-9]{2}"
```

## Targeting elements

By default, use refs from the snapshot to interact with page elements.

```bash
# get snapshot with refs
coding--debug--playwright-cli snapshot

# interact using a ref
coding--debug--playwright-cli click e15
```

You can also use css selectors or Playwright locators.

```bash
# css selector
coding--debug--playwright-cli click "#main > button.submit"

# role locator
coding--debug--playwright-cli click "getByRole('button', { name: 'Submit' })"

# test id
coding--debug--playwright-cli click "getByTestId('submit-button')"
```

## Browser Sessions

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

## Specific tasks

* **Running and Debugging Playwright tests** [references/playwright-tests.md](references/playwright-tests.md)
* **Request mocking** [references/request-mocking.md](references/request-mocking.md)
* **Running Playwright code** [references/running-code.md](references/running-code.md)
* **Browser session management** [references/session-management.md](references/session-management.md)
* **Storage state (cookies, localStorage)** [references/storage-state.md](references/storage-state.md)
* **Test generation (plan / generate / heal)** [references/test-generation.md](references/test-generation.md)
* **Tracing** [references/tracing.md](references/tracing.md)
* **Video recording** [references/video-recording.md](references/video-recording.md)
* **Inspecting element attributes** [references/element-attributes.md](references/element-attributes.md)
