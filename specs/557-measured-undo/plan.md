# Implementation Plan: Measured reversibility

**Branch**: `557-measured-undo` | **Spec**: `spec.md`

## Summary

One new module, `cli/wuwei/undo.py`, holds the undo registry, the class-to-kind map and the
rehearsal ledger (`memory/rehearsals.json`). The decision record's door is measured at the
two places that already read it first: `decision.lint` reports the correction, and
`decide()` in the `decision route` command (the one routing point) writes it into the
record before external, mandate, cruise, seat or owner routing, so every later reader of the
field (`cisr`, `route`, `mandate`, `owner_outcome`, `waits`, the DM listener, metrics) sees
the measured value without its own check. `wuwei undo` is one command: a D-n goes to #283's
`commands.decision.undo` (the one undo function), a merge event id to the revert-PR call the
merge watch already makes, and `rehearse <kind>` exercises an undo on a scratch target.
`next` returns the rehearsals as run rows; `init --upgrade` and `doctor` list what is
unrehearsed; the report gains two sections.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures in
`tmp_path`, reusing `record()`, `ws` and `route()` from `tests/test_decision_classes.py`
(records and routing), the fake code host and merge entries of `tests/test_merge.py`, and
`tests/test_protect_state.py` payloads. One real smoke test runs `git` for the commit
rehearsal (the external boundary); everything else is in process.

Base check before building: run `git fetch -q origin main` and, when `origin/main` carries
#283 (cruise mode), `git merge --ff-only origin/main` in the worktree (a fast-forward: the
worktree holds only untracked spec files, so no commit is written). Then
`cli/wuwei/commands/decision.py` has `undo(args, *, root=None, where=None)` and
`cli/wuwei/cruise.py` exists. If `origin/main` still lacks #283, stop and report the
dependency (spec Assumptions); build nothing.
If `tests/test_invariants.py` exists, the invariant rows go there and in
design 9.2.

## Constitution Check

- III one behaviour one function: the measured door lives only in `undo.measured`; lint and
  route call it; nothing else re-derives reversibility. The undo of a decision is #283's
  function, called by `wuwei undo D-n`, `decision undo` and the DM; the merge revert is one
  function shared with the watch. Pass.
- II exits: undo and rehearse exit 0, 1 (no undo, declined, window closed, no scratch
  target), 2 (adapter or git failure, unreadable record). A damaged ledger is unmeasured and
  counts as nothing rehearsed: the safe side is one-way (a card), never clean. Pass.
- No forgeable trust: the ledger is a file only `wuwei undo` and `wuwei undo rehearse` write
  (protect_state refuses seat writes, the records floor); `undo.rehearsed` and `undo.done`
  are reserved event kinds. A seat can only lower a door (write one-way), never raise one.
  A seat running `undo rehearse` really exercises the undo on scratch, so its row is true.
  Pass.
- #530: no new refusal under observe or guarded. The correction is a card; the lint exit
  code never changes. Pass.
- #551: the planner's next step is a command: `next` returns `wuwei undo rehearse <kind>`;
  the route's second line names the command; no skill or charter prose is added. Pass.
- Ports: `undo.py` never imports subprocess; the scratch git work is one git adapter
  operation with a closed allowlist; the revert PR is the existing code-host
  `revert_pr`. Pass.
- Ponytail: no new record field, no config key, no new class; registered kinds are only
  those with an undo the CLI already has. Pass.

## Changes

### New: `cli/wuwei/undo.py`

```python
"""#557: measured reversibility (design 5.8): a record is two-way only when the CLI knows the
undo for its action and that undo ran once here."""

NAME = 'memory/rehearsals.json'
# kind -> (the undo, the proof event). A kind not here has no undo: one-way.
REGISTRY = {'commit': ('git revert on the item branch, or delete the unmerged branch', 'undo.rehearsed'),
            'decision': ('wuwei undo D-n', 'decision.reversed'),
            'merge': ('wuwei undo <event id> (a revert PR), only while the base does not deploy', 'undo.done')}
SCRATCH = ('commit', 'decision')   # kinds `undo rehearse` can exercise on a scratch target
KIND = {**dict.fromkeys(('approach', 'retry', 'accept-residual', 'scope-cut', 'design',
                         'boundary', 'refactor', 'dependency-bump'), 'commit'),
        **dict.fromkeys(('park', 'defer', 're-plan'), 'decision'),
        'merge': 'merge', 'message': 'message'}
```

Module-level imports: `json`, `re`, `pathlib`, and `wuwei.state`, `wuwei.workspace` only;
`tempfile`, `shutil`, `registry`, `merge`, `novelty` and `commands.decision` are imported
inside the functions that use them, because `next` (a hook path, #562 budget) imports the
ledger reader.

Functions (each one behaviour):

- `ledger(root) -> dict`: the `kinds` table of `memory/rehearsals.json`; `{}` when missing;
  `ValueError` naming the fix when it is a symlink, not JSON, or not
  `{"kinds": {<registry kind>: {"at": <iso>, "by": "rehearsal"|"undo"}}}`. Same shape of
  reader as `novelty._read`.
- `measured(fields, root, config) -> (kind, reason)`: `kind = KIND.get(fields.get('Class'))`.
  `reason` is None when the written door may stand; otherwise one string ending in a next
  step (#362, `tests/test_reasons.py`):
  - `message`: `a message has no undo (4.9); ask the owner: wuwei decision route sends the card`;
  - no kind: `<class or "no class"> has no registered undo; ask the owner: wuwei decision route sends the card`;
  - `merge` naming no `repo:` key (`novelty.record_keys`, reused): `a merge record names no
    repository; add repo:<org>/<name> to Context`;
  - `merge` naming a repository not configured with `merge_deploys is False`: `a merge to
    <key> deploys (merge_deploys is not false, 4.6); ask the owner: wuwei decision route sends the card`;
  - kind not in `ledger(root)`: `the <kind> undo was never rehearsed in this workspace; run
    wuwei undo rehearse <kind>` (for merge: `...; it counts after the first wuwei undo of a
    merge here`);
  - `ledger` raised: `memory/rehearsals.json is damaged (<why>); move it aside, then run
    wuwei undo rehearse <kind>`.
- `line(written, reason)`: `Reversibility: one-way, not <written>: <reason>`.
- `correct(ident, path, text, fields, root) -> (text, fields, said)`: only on a first route
  (`ident` in neither `decision_routes` nor `decision_outcomes` of today's state), when
  `fields['Reversibility']` is not `one-way` and `measured` gives a reason, rewrite the first active
  `Reversibility:` line to `Reversibility: one-way` (the `set_outcome` regex form), append
  `Notes: Reversibility corrected at <stamp>: <reason>.`, `workspace.atomic_write` the
  record, set `fields['Reversibility'] = 'one-way'` and return `said = line(...)`; else
  return the inputs and `''`.
- `record(root, kind, by)`: read-modify-write of the ledger under a lock file next to it
  (the `novelty` locked-write pattern), `workspace.atomic_write`; keeps the first `at`.
- `missing(root) -> list[str]`: registry kinds not in the ledger (damaged: all of them).
- `rehearse(root, kind) -> (code, message)`:
  - `commit`: `tempfile.TemporaryDirectory()`; `brief.read(vcs.rehearse_revert, path,
    root=root)` style call through `registry.load('vcs', config)`; result must say the
    reverted tree equals the original; on success `state.append_event('undo.rehearsed',
    {'kind': 'commit'}, root)` then `record(root, 'commit', 'rehearsal')`.
  - `decision`: scratch root in a temporary directory with `.wuwei/config.toml` empty (the
    CLI defaults: autonomous, cruise on, `park` at L2) and a scratch ledger marking
    `decision`; write the `decision template` record with `Class: park`, `Blast radius: own
    branch`, `Reversibility: two-way` as the scratch day's `D-1`. `decide` and `undo` resolve
    their root through `workspace.find_workspace`, which honours `WUWEI_WORKSPACE` first, so
    the rehearsal sets `os.environ['WUWEI_WORKSPACE']` to the scratch root and restores the
    previous value (or removes it) in a `finally`; the real root is captured before. Call
    `commands.decision.decide(Namespace(id='D-1', external=None))`; it must
    print `mandate` with an open window; then `commands.decision.undo(Namespace(id='D-1',
    answer='Undo'), root=scratch, where='in an undo rehearsal')` must exit 0 and leave no
    `decision_outcomes['D-1']` in the scratch state; then event and ledger row in the real
    workspace.
  - `merge`: exit 1, `merge: its undo is a revert PR on the code host, which has no scratch
    target; it counts after the first wuwei undo <event id> of a merge here`.
  - anything else: exit 1 `<kind> has no scratch rehearsal; run wuwei undo rehearse commit
    or wuwei undo rehearse decision`.
  - any exception inside a scratch step: exit 2 with the reason; no event, no row.
- `run(root, target, answer) -> (code, message)`:
  - `D-n`: `commands.decision.undo(Namespace(id=target, answer=answer), root=root)`; an
    `OSError` from the host confirmation (no terminal) is exit 1 `run wuwei undo <id> in a
    host terminal and answer y`. The ledger row for `decision` is written inside #283's
    `undo` (below), so the DM and alias paths count too.
  - `EVENT_ID` (reuse `commands.why.EVENT_ID`): read that day's `events.jsonl` line; only
    `merge.completed` has an undo here, else exit 1 `<kind> has no registered undo, so it
    cannot be undone here; run wuwei why <event id> to see what it changed`. Load the merge entry from that day's state (`merges[pr]`); confirm
    with `integrity._host_confirm(digest, prompt=...)` (`OSError` is exit 1 as above, a no
    is exit 1); under `merge.locked(root)` call `merge.revert(root, directory, ref, entry,
    host)`; append `undo.done` `{'target': event id, 'kind': 'merge', 'pr': ref,
    'revert_pr': url}`; `record(root, 'merge', 'undo')`.
- `report_lines(day, data) -> (undone, one_way)`: from the day's events
  (`decision.reversed` with `undo: true`, `undo.done`, `draft.sent`) and
  `data['decision_outcomes']` rows with `reversibility == 'one-way'`; `['none']` when empty.

### New: `cli/wuwei/commands/undo.py`

`register`: parser `undo` with `target` (`D-n`, an event id, or `rehearse`), optional `kind`
(`nargs='?'`, only with `rehearse`) and `--answer`. `run`: `rehearse` with a kind goes to
`undo.rehearse`; otherwise `undo.run`. Prints the message (stderr when nonzero), returns the
code. Add `'undo'` to `WRITES` in `cli/wuwei/commands/__init__.py`.

### `cli/wuwei/decision.py`

- `lint(text, lenses=LENSES, root=None)`: after `evaluate`, when `root` is given,
  `kind, reason = undo.measured(fields, root, workspace.load_config(root))`; if `reason` and
  `fields['Reversibility'] != 'one-way'`, add `'\n' + undo.line(...)` to the OK message.
  Exit code unchanged.
- `lint_file`: pass `root` to `lint` (it already resolves it).
- Nothing else here changes: `evaluate`, `cisr`, `route`, `route_owner`, `waits` keep reading
  `fields['Reversibility']`, which the route has already corrected.

### `cli/wuwei/commands/decision.py`

- `decide(args)` (signature unchanged): right after `evaluate(text)`:
  `text, fields, said = undo.correct(args.id, path, text, fields, root)`. A corrected record
  is one-way, so every route it can take prints `owner` (external, novel, mandate declining a
  one-way door, `route`); each of those returns appends `'\n' + said` when `said`. The
  `--external` branch comes after the correction.
- `undo(...)` (#283): one added line after its state write:
  `undo_ledger.record(root, 'decision', 'undo')` (import `wuwei.undo` locally). `decision
  undo` stays registered as it is: it is the alias.

### `cli/wuwei/merge.py`

Extract the revert block of `monitor` (`if not entry.get('revert_pr'): ...
save_entry(..., 'merge.revert')`) into `revert(root, directory, ref, entry, host) -> str`
returning `entry['revert_pr']`; `monitor` calls it. No other merge change.

### `adapters/vcs/git.py` and `cli/wuwei/registry.py`

- `@_operation def rehearse_revert(path, root=None)`: `path` must be an empty directory;
  `git init --quiet`, write `rehearsal.txt` with `before`, add, commit with the fixed
  message `WUWEI undo rehearsal`, write `after`, commit, `git revert --no-edit HEAD`, read
  `HEAD^{tree}` and `HEAD~2^{tree}`; returns `{'reverted': <bool>, 'tree': <sha>}`. Every
  call passes `local=True` and a fixed identity through `-c user.name=wuwei -c
  user.email=wuwei@localhost` or the env the adapter already uses for workspace commits;
  new allowlist cases match only these exact argv shapes and only for a `path` under the
  system temporary directory.
- `registry.py`: add `'rehearse_revert': ('path',)` to the `vcs` contract.

### `cli/wuwei/commands/next.py`

In `step`, after the `telemetry` row and before the `decision_routes` loop:

```python
for kind in ('commit', 'decision'):   # undo.SCRATCH, inline: keep the hook path light
    if ('rehearse', kind) not in returned and kind in undo.missing(root):
        return _row('rehearse', f'The {kind} undo was never rehearsed here, so two-way {kind} '
                    'records go to the owner until it runs; rehearse it on a scratch target.',
                    f'wuwei undo rehearse {kind}', item=kind)
```

`missing` reads the ledger only while a pair is not yet returned; after both are done the
loop costs two set lookups. `_record` keys the done pair by `item` as for other rows; check
how `_seen` keys `(state, item)` and pass the kind as `item` so the pair is `('rehearse',
kind)`.

### `cli/wuwei/commands/init.py`

In `upgrade`, after the novelty seed: `unrehearsed = undo.missing(destination.parent)`;
print `Undo not rehearsed: <kinds>; run wuwei undo rehearse <kind> (a merge counts after its
first wuwei undo)` when nonempty (dry run too). Not an `Upgraded`/`Would upgrade` line and not counted in the `No workspace changes
needed` condition.

### `cli/wuwei/commands/doctor.py`

In `_workspace`, one row: `_row('workspace', 'undo rehearsals', 'ok', 'rehearsed: <kinds or
none>; not rehearsed: <kinds or none> (wuwei undo rehearse <kind>)')`; on `ValueError` from
`undo.ledger`, status `fail` with the fix `move .wuwei/memory/rehearsals.json aside, then run
wuwei undo rehearse commit and wuwei undo rehearse decision`.

### `cli/wuwei/report.py`

In `build`, after `## First time today`: `undone, one_way = undo.report_lines(day, data)`;
`lines += ['', '## Undone today', *undone, '', '## Cannot be undone', *one_way]`.

### `cli/wuwei/guards/protect_state.py` and `cli/wuwei/commands/event.py`

- `_protected_name`: add `('memory', 'rehearsals.json')` to the tuple with `ledger.jsonl` and
  `targets.json`. `_hint`: `rehearsals.json is the undo rehearsal ledger (design 5.8
  Measured reversibility): only wuwei undo rehearse and wuwei undo write it.`
- `EVENT_PRODUCERS`: `'undo.rehearsed': 'wuwei undo rehearse'`, `'undo.done': 'wuwei undo'`.

### Tests

- `tests/conftest.py`: autouse fixture `rehearsed_undo(monkeypatch)` that patches
  `wuwei.undo.ledger` to return `commit` and `decision` as rehearsed and returns the real
  reader (the `quiet_heartbeat` pattern). Tests in `tests/test_undo.py` restore it.
- `tests/test_undo.py` (new): every scenario in spec User Stories 1 to 5 and the edge cases;
  invariants (a) to (d) when `tests/test_invariants.py` is absent.
- Extend `tests/test_protect_state.py` (ledger write refused), `tests/test_next.py`
  (rehearse rows), `tests/test_doctor.py` (row), `tests/test_report_retro.py` (sections),
  `tests/test_merge.py` (monitor still opens the revert PR through `revert`), `tests/test_vcs.py`
  (the adapter smoke test).

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 5.8: after the Decision classes paragraph, a short
  paragraph `Measured reversibility (owner, 2026-10-08, #557).` stating the rule, the
  registry kinds, rehearsal on a scratch target, message never two-way, `wuwei undo`, and
  the two report sections. 9.2 rows if the table exists.
- `docs/site/concepts.md`, `docs/site/reference.md`, `docs/site/daily.md` per FR-014.

## What must not change

- The merge policy (`merge.check`, `merge.execute`), its eligibility and the deploy ban;
  `monitor` behaves the same after the extraction.
- `decide`'s signature and every route of a record already routed or decided.
- `route_owner` and the CLI-written records routed through it (grants, remote denial, pr
  disposition, outbound learn, MCP): not corrected.
- The novelty gate, the cruise conditions and levels (#283), `owner_outcome`, the DM
  vocabulary, `decision undo`'s behaviour and messages, and every lint exit code.
- No new config key, record field, decision class or skill or charter text.

## Builder notes

- #283 landed as #566; the worktree was fast-forwarded to origin/main before building.
- The adapter contract table in `tests/test_adapters.py` gains the `rehearse_revert` row.
- The agent guide block in `docs/site/agent.md` is regenerated for the new `undo` command.
- Existing tests that routed a `merge` record naming no repository, a record without a class or
  a `Class: other` record now expect `owner` plus the correction line (`tests/test_cruise.py`,
  `tests/test_decision_classes.py`): that is the behaviour this item adds.
- `wuwei undo` with a target that is neither D-n nor an event id exits 1 naming both forms.
