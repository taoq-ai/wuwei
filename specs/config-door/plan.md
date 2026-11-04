# Implementation plan: config-door

**Spec**: `specs/config-door/spec.md`
**Item**: config-door, tier full, goal G-2

## Technical context

- `cli/wuwei/guards.py`: `records(path, below)` matches `.wuwei` and the names below it in the spellings sh
  expands. `bash()` calls it with `CACHE` for redirect targets and writer arguments (`LEDGER` for `rm`), and
  refuses any writer after `cd .wuwei` or with `-C`/`-D .wuwei`. `pre_tool()` calls it with `CACHE` for edit
  paths. The unreadable rule matches `DOOR_WORDS` in the raw text. The literal `wuwei hook` check reads the
  segment's argv joined by NUL.
- `hook.pre_tool` hands the whole payload to `guards.pre_tool`, so `agent_type` is there already; hook.py needs
  no change.
- `wuwei plan` actions (cli/wuwei/__main__.py): show, add, park, drop, done, restore, run, pass, view, session.
  `wuwei config <key> [<value>]` calls `ws.set_config`, which writes even with no value.
- Runtime at the base: 3,904 lines (`wc -l cli/wuwei/*.py`); item budget 8.

## Design

1. `OWNED = ('config.toml', 'plan.json')` beside `LEDGER` and `CACHE`. `bash()` takes `seat`; `own = OWNED * seat`
   joins `CACHE` (and `LEDGER` for `rm`) in the existing records calls. `pre_tool()` does the same for edits.
2. `SEAT_WORDS`: two door words read only for a seat in the unreadable rule (the paths, and `wuwei config|plan`).
3. `SEAT_CLI`: one regex on the NUL-joined argv, built on the `wuwei hook` check's prefix, plus `executable)` and
   a bare segment starting with `config` or `plan` (the unquoted `$(cat .wuwei/executable)` shape).
4. `OWNER_ONLY`: the refusal line naming the owner, added to a seat's records refusal and its unreadable refusal.
5. The sed writer test reads `-i` in any spelling (`-[^-]*i|--i`).
6. Route corpus: eight routes from the acceptance, four with `"seat": true`; the corpus test passes the field.
7. SECURITY.md paragraph; docs/site/reference.md lines; `.claude/wuwei/cli/wuwei/guards.py` copied.

## Verification

- Tests red on main, green at the head; tests/test_guards.py and tests/test_hook.py, then the full suite.
- `route_diff.py`: every corpus route as owner and as seat through `guards.pre_tool`, main against head.
- `probe.py`: 928 cases (864 Bash, 64 edit tools) through `guards.pre_tool` and `hook.handle`, as seat and owner,
  main and head; it writes `cases.tsv` for `run.sh`.
- `mutants.py`: 31 mutants, one at a time, on both copies.

## Constitution check

Stdlib only, test first, no new config key, no new dependency, runtime within the 4,000 cap and the item budget.
The door reuses the records rule rather than a second matcher.
