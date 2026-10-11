# Charter overrides and promote

Shipped role rules live in the plugin's `charters/`. Workspace overrides live in `.wuwei/charters/` under the same file name, such as `builder.md`. The plugin charter stays the baseline; an override adds rules for this workspace.

A seat or the steward proposes a change as a JSON file in today's `.wuwei/days/<date>/proposals/`. A proposal names:

- `target`: a charter override under `.wuwei/charters/`;
- `action`: `add` or `patch`;
- `reason`: one line;
- `evidence`: an existing file inside `.wuwei/`;
- `text` (or `delta`): the rule to add or the replacement;
- `old_text`, for a patch: the exact rule it replaces. A patch with empty `text` removes that rule.

`bin/wuwei retro --promote` lands today's proposals. It validates each one and writes accepted changes atomically. A duplicate add, an unknown `old_text` or an override over 200 lines is rejected. So is a target with uncommitted hand edits, so promotion never blesses them. Each landed change is committed with a `Promoted-by: wuwei` trailer, and each outcome goes to `.wuwei/memory/ledger.jsonl` and the changelog.

After a landing it exports the rules block into the `memory.export_to` file and rewrites `.wuwei/memory/index.md`. It exits 0 when all landed, 1 when any was rejected and 2 when the export failed.

The steward runs once at close through `bin/wuwei close`, and its proposals land the same way. `bin/wuwei init --upgrade --dry-run` flags overrides whose charter version differs from the shipped one, for you to review.
