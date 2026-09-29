# Workspace canary and honeytoken

Initialize a workspace using the repository CLI:

```sh
bin/wuwei init workspace --honeytoken-path credentials/backup.env
```

The optional path is relative to `.wuwei` and must name a new file in a private
subdirectory. Init creates independent random canary and honeytoken values,
private instruction copies and ignore rules. Values are never printed.

For an existing workspace:

```sh
bin/wuwei init workspace --upgrade --dry-run
bin/wuwei init workspace --upgrade
```

From within the workspace, regenerate after changing a charter override:

```sh
python3 -P -m wuwei agents build
python3 -P -m wuwei agents check
```

Generated instructions live in `.wuwei/generated/agents`, `charters` and `skills`.
Briefs and runtime dispatch point seats at these private copies. Shipped source
agents remain reproducible and contain no workspace tokens. This branch has no
shipped runtime skills; skill Markdown is included when available.

Outbound marker matches refuse in both profiles. Security pages are reserved
`security.canary` and `security.honeytoken` events. Honeytoken hits also emit
`scanner.finding`. Traces contain redacted arguments and `security.findings`
labels, never marker values or fetched response bodies. Exact reads of generated
instructions are expected loads, not alerts; changed or unrelated content still
pages. Security material failures return exit 2 with a redacted reason.

Legacy workspaces keep prior behavior until upgraded. Missing material in an
already enabled workspace must be restored; silently rotating it would leave
active seats holding stale markers. Full ZIRAN scanning and arbitrary-program
read analysis remain scanner-integration work.
