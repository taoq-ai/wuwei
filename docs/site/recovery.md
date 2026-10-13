# Recovery

The [daily path](daily.md) needs none of this page. Reach for it when evidence and records disagree, a seat is lost, or the installation changed. Before a release, the [release rehearsal](rehearsal.md) drives a real day, and its failures point back here.

## Troubleshooting

Start with `bin/wuwei doctor`. It checks the install, host, workspace, gates, PR flow, day and guards, and prints each problem with its fix. It exits 0 when all is well, 1 on a finding and 2 when something could not be measured.

- `--json` prints the rows as JSON.
- `--section pr-flow` prints one section.
- `--fix` applies the fixes it can apply safely. Today these are `init-upgrade` and `integrity-reconfirm`. It previews them, asks one Owner step card in the session, and applies them on your Yes. Then it diagnoses again.
- `--fix --apply <ids>` narrows the batch to those fix ids.
- `--fix --widget` prints the card and applies nothing.

Every other row stays printed with the command that fixes it. See [doctor](reference.md#doctor) for the full row list.

### Why did that happen

`bin/wuwei why <target>` reads the day records and explains, writing nothing. The target is `last refusal`, an event id, `adhoc`, a PR ref `owner/repo#<n>` or an item. `last refusal` prints the guard, the rule, the command and the fix. `--full` adds event ids and evidence paths.

### config.toml does not load

Every tool call is refused with the parse error. A `Read`, `Grep` or `Glob` of the config or charters still passes, and so do `bin/wuwei config check`, and `config set` and `doctor --fix` with their cards. Run `bin/wuwei config check`; it names the key, the line and the fix.

A `repos = []` line next to `[[repos]]` tables is the usual cause. `bin/wuwei doctor --fix` offers `init-upgrade`, which removes the line, on its Owner step card.

### A stuck seat

A seat whose report cannot be read or recorded is stopped as `unmeasured`, never left running. A readable report is kept in `.wuwei/days/<date>/reports/<name>.md`. `wuwei next`, the doctor `stuck seats` row and `why` name it. From the planner session:

- `bin/wuwei seat stop <name> --verdict` records the kept report, or the hand-back the seat's transcript ends with. `wuwei next` offers this first whenever the report is readable.
- `bin/wuwei seat stop <name> --verdict <file>` records the report from a file. Both run the same stop guards, and a sentinel's report must pass the verdict lint first.
- `bin/wuwei seat stop <name> --unmeasured "<reason>"` stops it so the day can move. A builder's running build parks with that reason.

An adhoc seat has no report, so only `--unmeasured` clears it. See [stuck seats](reference.md#stuck-seats).

### A damaged event log line

The day's records live in `.wuwei/days/<date>/events.jsonl`; `state.json` is only its cache. A torn cache is rebuilt from the log. A line that never finished writing recorded nothing, and the records skip it.

The doctor `state`, `day` and `drift` rows read the log strictly. A damaged line shows there as unmeasured, naming the file. Agent tools cannot edit the log. Open it in your editor and remove only the incomplete line. Do not reorder or delete other lines: an event id is the line number. Then run `bin/wuwei doctor` again.

### Branch protection reads as unmeasured

A 404 on the classic endpoint means the branch is unprotected or you lack admin. `bin/wuwei config check` prints `classic protection: none visible` and reads the rulesets as well.

## Integrity reconfirm

`bin/wuwei doctor --fix --apply integrity-reconfirm` records your confirmation of a development checkout or a changed installation. An intact signed release never needs it.

Review the files the integrity row names first. The command prints the installation fingerprint and asks its Owner step card in the session. On your Yes it measures again and records the confirmation only if nothing changed meanwhile. A later change to the installation voids it. See [integrity](integrity.md).

## Seat launch contract

`wuwei next` returns each ready launch with its prompt. Builder and gate launches come from `bin/wuwei build next` and `bin/wuwei dispatch next`. Pass the prompt to Agent unchanged, with `wuwei:<role>` as `subagent_type`, from the workspace root.

The prompt carries the line `WUWEI brief: <path>`, relative to the workspace root, such as `.wuwei/days/<date>/briefs/builder-1.md`. A note you add before or after it stays on the seat. The launch guard still needs the logged, unchanged brief, the matching role and free capacity.

A builder launch needs its build record: the guard refuses one with none and names `bin/wuwei build next <item>`, whose launch then registers. Work already done outside the record comes back with `bin/wuwei build reconcile <item> --worktree <path>`.

To brief a seat by hand, write and log the brief with `bin/wuwei seat brief <role> <item> <name> --body TEXT`, or `--file PATH` (`-` reads stdin).

A WUWEI seat type launched without the line is refused while `guards.enforce` is on, naming `seat brief`. With it off, the launch is registered as an adhoc seat with a warning, which WUWEI can trace and stop but not continue. An agent of another type is an adhoc seat once the day has records. Record it first with `bin/wuwei seat start --role <role> --adhoc "<prompt>"` to label it.
