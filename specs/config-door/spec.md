# Feature Specification: a seat's write to .wuwei/config.toml or .wuwei/plan.json meets a door

**Feature branch**: `fix/config-door`
**Item**: config-door, tier full, goal G-2
**Input**: the security gate on models-record (#1146, security-e0351a1.md) found that `.wuwei/config.toml` takes
Edit, Write, a Bash redirect and `wuwei config` from builder and sentinel seats, so a seat can rewrite
`owner_paths` or a `models` row. The owner answered `trust:` "Yes, owner only" on 2026-10-19. On 2026-11-04 the
gates on #1282 and #1281 found the same for `.wuwei/plan.json`, whose `tier`, `domain` and `in_doubt` fields set
the gates evidence owes, so a seat can lower its own gate set.

## The promise in my words

A seat is a tool call whose hook payload carries an `agent_type`. The owner's own session carries none.

1. From a seat, the guard treats `.wuwei/config.toml` and `.wuwei/plan.json` as it treats the ledger and the
   cache: Edit, Write, MultiEdit and NotebookEdit on either path are refused, and so is every Bash route the
   records rule reads (a redirect target, a writer argument, `rm`, `find -delete`, a `python -c` path, a writer
   after `cd .wuwei`, `env -C .wuwei`, `sudo -D .wuwei`), in the spellings sh expands (`//`, `/./`, `..`, globs,
   braces, case).
2. From a seat, `wuwei config <key> [<value>]` and the `wuwei plan` actions that write the plan (`add`, `park`,
   `drop`, `done`, `restore`, `run`, `session`, and the names the item lists, `tier` and `approve`) are refused,
   whether called as `wuwei`, by a path, through `python -m wuwei`, or through `$(cat .wuwei/executable)`.
3. Reads stay open to a seat: `wuwei plan show`, `wuwei plan view`, `wuwei plan` alone, `wuwei config` alone,
   `wuwei status`, `cat` and the Read tool.
4. The owner's session keeps every one of these writes, as on main.
5. The refusal text names the owner. SECURITY.md and docs/site/reference.md say config and plan are owner-session only.

The acceptance scenarios, restated:

1. A builder or sentinel seat runs Edit or Write on either file, `echo x >> .wuwei/plan.json`,
   `wuwei config owner_paths x`, `wuwei config models 'builder=haiku low'` or `wuwei plan tier I-1 light`: each
   is refused.
2. The owner's session runs `wuwei config models 'builder light=opus medium'` or `wuwei plan add`: it passes and
   writes as on main.
3. A seat runs `wuwei plan show I-1` or `cat .wuwei/plan.json`: it passes.
4. A generated probe of path spellings (`//`, `%xx`, `/./`, `/../`, `cd`, `env -C`, `sudo -D`) x write routes
   under real bash: every seat write that changed either file is refused (holes 0). By the owner's choice the
   probe is split: the verdicts are read in-process at main and head, and `run.sh` runs each case under real
   bash by hand.

## How this fails

1. A spelling the guard does not read writes the file. The records rule is reused, so its known shapes carry
   over; the new shapes are the CLI's own spellings (`$(cat .wuwei/executable)`, unquoted, which sh splits into
   its own segment, and in backticks) and `$'...'` quoting of the path or the program. Each has a test. A
   `sed -i.bak` was not a writer at all, for the ledger too; the probe's sed class found it and the writer test
   now reads `-i` in any spelling.
2. A false refusal stops a seat's normal work. Ways in: `git config user.name` in a checkout named `wuwei`, a
   commit message naming `wuwei plan done`, `cp a .wuwei-plan.json`, a literal `.wuwei/%70lan.json`, and every
   read. Each has a test that expects a pass. A seat's multi-line command that names `wuwei plan` is refused
   with the one-line hint, as `wuwei hook` is today.
3. The owner is caught by the seat rule. The rule keys on `agent_type` alone, and every owner verdict in the
   route corpus and the probe is compared main against head: none moves except the `sed -i.bak` class inside
   `.wuwei`, which the existing inside rule now refuses for everyone (as it refuses `sed -i` there on main).

## Clarifications

### Session 2026-11-04

- Q: What marks a seat? A: `agent_type` in the hook payload, as the item says. hook.py already reads the role
  from it ("the harness's, never the message's"). A session the owner starts with `claude --agent` would carry
  one too; recorded under Assumptions.
- Q: `tier` and `approve` are not `wuwei plan` actions on main (argparse refuses them). Are they in the refused
  set? A: Yes. The item names them; listing them costs two words and holds if they are added later.
- Q: Is `wuwei plan pass` a plan write? A: No. It writes a ledger record, not plan.json, and the item does not
  list it. It stays open.
- Q: Does `wuwei config <key>` with no value write? A: Yes. On main `ws.set_config(root, key, None)` writes the
  key as null for a string key, so any word after `config` is refused from a seat.
- Q: A seat's `cp .wuwei/plan.json /tmp/p.json` is refused, as `cp` of a ledger file is on main. Is that a read
  that should pass? A: The records rule reads a writer's every argument, source or target; the item asks for
  the same routes as the ledger. Reads use `cat`, the Read tool or `wuwei plan show`. Recorded under Assumptions.
- Q: Does a seat's refusal of a ledger write gain the owner line? A: Yes, a seat's records refusal carries both
  rules in one text. 29 seat routes in the corpus change reason only.

## Requirements

- FR-001: From a seat, `records` covers `config.toml` and `plan.json` below `.wuwei` for redirect targets,
  writer arguments (`rm` too) and edit paths.
- FR-002: From a seat, the literal CLI spellings of `wuwei config <key>` and the writing `wuwei plan` actions
  are refused; the read actions pass.
- FR-003: From a seat, an unreadable or multi-line command naming either file or `wuwei config` or `wuwei plan`
  is refused with the one-line hint and the owner line.
- FR-004: `sed` with `-i` in any spelling is a writer.
- FR-005: The owner's session verdicts do not move, apart from FR-004 inside `.wuwei`.
- FR-006: SECURITY.md and docs/site/reference.md state the rule; the vendored copy matches.

## Success criteria

- SC-001: The new tests fail on main (129 failed) and pass at the head.
- SC-002: Route differential over the corpus: no owner verdict moves; the seat moves are the six new seat
  routes, pass to refusal.
- SC-003: In-process probe at the head: every seat case that names the real file is refused; the 38 seat
  passes are the `%xx` class, which sh does not decode. `run.sh` reports holes 0 when the owner runs it.
- SC-004: Runtime within budget: +7 lines (3,904 to 3,911), budget 8.

## Assumptions

- A seat is `agent_type` set. Why: the item and hook.py both read it as the harness's own field. Overturn: an
  owner session that carries `agent_type` (`claude --agent`) and needs to write the config; the rule would
  then key on `agent_id`.
- `executable` as a program word, and a segment that starts with `config` or `plan`, read as the WUWEI CLI from
  a seat. Why: `$(cat .wuwei/executable)` is the spelling the charters teach, and sh leaves an unquoted one as
  its own segment. Overturn: a real program named `config` or `plan` a seat must run with arguments.
- The guard is cooperative mistake prevention (SECURITY.md). A seat running Python that imports `wuwei.ws` and
  calls `set_config`, or a path built in a variable (`D=.wuwei; echo x > $D/plan.json`), is not read, as for
  the ledger.

Rollback: revert the commits; no data or config migrates.
