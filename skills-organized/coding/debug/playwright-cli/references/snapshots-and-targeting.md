# Snapshots and targeting

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
