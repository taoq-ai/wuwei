# Feature Specification: every refusal says what happened, why, and the one command to run, with real values and one reason per refusal

**Feature Branch**: `362-refusals-coach`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #362, "feat(cli): every refusal says what happened, why, and the one
command to run, with real values and one reason per refusal". From the UX adoption sweep of
2026-10-03, findings F12, F14, F15, F16, F17, F18 and catalogue (d). Owner's brief: "I want
the adoption to be easiest as possible. The workflow should coach people with less
experience instead of simply blocking." Coaching means: what happened, why, and the one
command with real values; never a bare refusal. Prefer doing it for the owner and saying so
over asking, and asking over refusing. Depends on #347, #348 and #349, all on main (#389,
#397, #409). The catalogue (section d of the sweep: 524 drafted rewrites and 307 internal
invariants by family) is pasted in [research.md](research.md).

## Findings (from the sweep)

| Id | Step | What happens now | Coaching version |
|---|---|---|---|
| F12 | before or outside a plan | Commands answer state with errors: `close` and `report` give `day state missing; close cannot infer empty ownership` (2); `plan approve` gives `today's plan.md is missing`; `build check` gives `build is not awaiting checks`; `dispatch next` gives `item phase implement is not dispatchable`; `decision show D-1` prints an Errno and an absolute path; bare `goals` is an argparse error although the docs say it shows goals. | Each one says the state and the next command: `Nothing to close today`; `DIV-1 is still building; run wuwei build next DIV-1`; `No D-1 today; bin/wuwei nudges lists open decisions`; `goals` prints the goals. Exit 0 with a state line where nothing is wrong. |
| F14 | any tool call | When Claude Code runs a different plugin copy from the one confirmed for this workspace, every tool call is refused: `plugin integrity: checkout HEAD or tree changed; restore a clean commit and run wuwei integrity reconfirm on the host`. The checkout was clean. | Name both: `confirmed <path A>, running <path B>`. Say which action fits: reconfirm B, or start Claude Code with A. |
| F15 | doctor | A raw adapter line (`git.identity: could not run: git exited 1`) prints above the table. Before a workspace exists, git identity is `fail` with a `--global` fix although each repository sets its own. Without a workspace it suggests `wuwei init --shadow`, while every page says `setup --shadow`. Fix lines say `wuwei ...`, which is not on PATH. | No stray stderr; identity is `ok` when repositories set their own; suggest `setup --shadow`; print fixes with the real launcher. |
| F16 | adapters | Failures arrive as exit codes only: `git exited 128`, `gh exited 1`, `git.push_commits: could not run: git exited 128`. | Add the first stderr line and the ref or repository, plus one hint: `git fetch origin`, `gh auth login`. |
| F17 | builder push | `git push` gets `use an explicit remote and branch refspec: git push origin <branch>` and a second `deploy: could not inspect: push destination is unresolved`. `fast check has not passed for current HEAD: true` does not name the command. `commit && push` gets `run push separately after commit creation and fresh fast checks`. | One reason per refusal, with the guard's own values: `run: git push origin HEAD:refs/heads/div-1`; `run bin/wuwei build check DIV-1 first`. |
| F18 | reads | `git config --get-all core.hooksPath` and `ls ~/` were refused as writes. | Reads pass. Fixed on main by #389 and #409; this feature pins it with a regression test. |

## Root cause (read and reproduced on main, e0c32d1)

Reproduced read-only in a scratch workspace outside the repository (`bin/wuwei init` in an
empty directory, development checkout not reconfirmed) and by piping PreToolUse payloads
through `bin/wuwei hook PreToolUse`. `<scratch>` stands for the scratch directory:

```
$ bin/wuwei doctor                     (no workspace)
git.identity: could not run: git exited 1          <- stray adapter line above the table
  fail       git identity: git.identity: could not run: git exited 1
      fix: git config --global user.name "<name>" and git config --global user.email "<email>"
  fail       workspace: no .wuwei/ found from <scratch>
      fix: wuwei init --shadow in the directory that holds your repositories
$ bin/wuwei goals                      exit 2: wuwei goals: error: the following arguments are required: action
$ bin/wuwei decision show D-1          exit 2: decision show: could not read <scratch>/.wuwei/days/2026-10-03/decisions/D-1.md: [Errno 2] No such file or directory: '<scratch>/...'
$ bin/wuwei close                      exit 2: wuwei close: day state missing; close cannot infer empty ownership
$ bin/wuwei report                     exit 2: wuwei report: day state missing; report cannot infer open work
$ bin/wuwei build check DIV-1          exit 2: build: build is not awaiting checks
$ bin/wuwei dispatch next DIV-1        exit 1: wuwei dispatch: item is not approved at the morning gate
$ bin/wuwei plan approve --items DIV-1 --goals-confirmed   exit 1: wuwei plan: today's plan.md is missing
$ bin/wuwei plan template              exit 0 (fixed by #391; pinned here)
hook PreToolUse `git push`             exit 2, stderr:
  git.commit_context: could not run: not a git repository
  commit/push guard could not run: git.commit_context: could not run: not a git repository
  posture: publish = block (set security.areas.publish)
  deploy: could not inspect: push destination is unresolved
  posture: publish = block (owner-only action; no setting lowers it)
  page: plugin integrity: development checkout requires host reconfirmation; run wuwei integrity reconfirm on the host
  posture: integrity = block (set security.areas.integrity)
hook PreToolUse `git config --get-all core.hooksPath` and `ls ~/`: refused only by the
  integrity gate; with integrity clean they pass (F18 holds)
```

An AST pass over `cli/wuwei` (the sweep's collector, with pass-through wrappers such as
`f'build: {exc}'` excluded) finds 1194 reason strings, of which about 940 name no next step.

- `cli/wuwei/commands/hook.py:98-115` (`run`): every enforced refusal becomes its own
  `reason\nposture line` and all of them are joined (`:102`), so one call prints up to
  three reasons and three posture lines. This is the one place every guard's refusal is
  printed.
- `cli/wuwei/guards/commit_push.py:259` (`push_options`) raises `use an explicit remote and
  branch refspec: git push origin <branch>`, which the outer handler (`:434-438`) turns
  into exit 2 `commit/push guard could not run: ...`; `:140` and `:145` say `fast check has
  not passed for current HEAD: <check>`; `:374` says `run push separately after commit
  creation and fresh fast checks`; `:117` says `push to the default branch is refused`.
  None uses the item or branch the guard can see: the repository path `actual['path']` is
  `<root>/worktrees/<ITEM>` on branch `<item lowercased>` (`commands/worktree.py:34`).
- `cli/wuwei/guards/deploy.py:115` and `:317`: `deploy: could not inspect: push destination
  is unresolved`, a second refusal of the same bare push.
- `adapters/vcs/git.py:183` raises `git exited <code>` and `adapters/code_host/github.py:110`
  raises `gh exited <code>`, both dropping stderr. `_operation` (`git.py:42-46`,
  `github.py:38-42`) also prints the reason to stderr, which is the stray doctor line.
- `cli/wuwei/integrity.py:253-269` (`cached`) compares the recorded checkout with the
  running plugin's checkout, but no record holds a plugin path (`check`, `:231-250`;
  `reconfirm`, `:333-334`), so it cannot say which copy was confirmed and which one runs.
- `cli/wuwei/commands/doctor.py:218` suggests `wuwei init --shadow`; `:171-177` fails the
  global identity when no repository is configured yet (no workspace); every `fix` says
  `wuwei ...` (`_row`, `:33-42`); `run` (`:759`) calls `diagnose` while the adapters print
  to the real stderr.
- `cli/wuwei/commands/close.py:45`, `cli/wuwei/report.py:59` (through
  `commands/report.py:15`), `cli/wuwei/commands/decision.py:79`,
  `cli/wuwei/commands/goals.py:8` (`required=True`), `cli/wuwei/commands/build.py:373`,
  `cli/wuwei/dispatch.py:140` and `:161`, `cli/wuwei/plan.py:172`: the F12 lines.
- `cli/wuwei/guards/protect_state.py:45-66` (`_OWNER_ACTIONS`), `:171` and `:190`: owner
  action reasons that name no command (`Opaque owner action; use the host terminal.`).
- Catalogue (d): every other wall, with a drafted rewrite each, in research.md.

## User Scenarios & Testing

### User Story 1 - One refusal prints one reason and one posture line (Priority: P1)

A call that several guards refuse gets the most specific reason only, with that reason's
posture line. The event keeps every refusal for `wuwei why`.

**Why this priority**: three stacked reasons, two of them generic, is the F17 wall a builder
hits on its first push.

**Independent Test**: `python -m pytest -q tests/test_posture.py -k one_reason`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace and three stub guards refusing one PreToolUse call with
   `(2, 'deploy generic')` from module `deploy`, `(1, 'commit_push specific')` from
   module `commit_push` and `(2, 'integrity gate')` from module `integrity`, **When** the
   hook runs, **Then** it exits 2, stderr and `permissionDecisionReason` are exactly
   `commit_push specific` and one `posture: publish = block (set security.areas.publish)`
   line, and the `hook.refusal` event lists all three refusals with `reason` equal to the
   printed text.
2. **Given** refusals from `deploy` (2) and `integrity` (2) only, **Then** the deploy reason
   and its owner-only posture line print; the integrity reason prints only when it is the
   only enforced refusal.
3. **Given** `observe` posture, where the commit_push refusal relaxes to a warning and the
   owner-only deploy refusal blocks, **Then** the deploy reason prints with its own posture
   line and a `guard.would_refuse` event records the relaxed one (unchanged).
4. **Given** SessionStart, **Then** output is unchanged (every reason in the context).

### User Story 2 - Guard reasons carry the guard's own values (Priority: P1)

**Why this priority**: a reason with `<branch>` or `true` in it still leaves the reader to
find a value the guard already has.

**Independent Test**: `python -m pytest -q tests/test_commit_push.py -k real_values`.

**Acceptance Scenarios**:

1. **Given** the repository path `<root>/worktrees/DIV-1`, **When** `git push` runs there,
   **Then** commit_push returns exit 1 with a reason containing `git push origin
   HEAD:refs/heads/div-1`; outside an item worktree the reason contains
   `HEAD:refs/heads/<branch>`.
2. **Given** the fast check `unit` has no passing record for HEAD, **When** `git push origin
   HEAD:refs/heads/div-1` runs in that worktree, **Then** the reason names `unit`, the first
   12 characters of the HEAD sha and `bin/wuwei build check DIV-1`; outside an item
   worktree it names `bin/wuwei fast-checks`.
3. **Given** `git commit -m x && git push origin HEAD:refs/heads/div-1` in that worktree,
   **Then** the reason names the commit alone, then `bin/wuwei build check DIV-1`, then `git
   push origin HEAD:refs/heads/div-1`, as separate steps.
4. **Given** a push to the default branch `main` from that worktree, **Then** the reason
   names `main` and `git push origin HEAD:refs/heads/div-1`.
5. **Given** each `_OWNER_ACTIONS` pair in `guards/protect_state.py`, **Then** its reason
   names its `bin/wuwei` command and that the owner runs it in a host terminal; the opaque
   owner-action reason names the literal form (`bin/wuwei <group> <verb>` as a plain
   command).
6. **Given** `git push` from `<root>/worktrees/DIV-1` through `hook.run` in a seeded, clean
   workspace, **Then** stderr holds one reason with `HEAD:refs/heads/div-1`, one posture
   line, and no `deploy: could not inspect` line.

### User Story 3 - Adapter failures carry the first stderr line and the repository (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_vcs.py tests/test_code_host.py -k stderr_line`.

**Acceptance Scenarios**:

1. **Given** git exits 128 with stderr `fatal: Not a valid object name origin/main\nmore`,
   **When** `merge_base('/repo', 'origin/main')` runs, **Then** the result is exit 2 and its
   reason contains `git exited 128`, `merge-base`, `/repo`, `fatal: Not a valid object name
   origin/main` and the hint `run git -C /repo fetch origin`, and not `more`.
2. **Given** gh exits 1 with stderr `To get started with GitHub CLI, please run:  gh auth
   login`, **When** `pr('acme/widget#7')` runs, **Then** the reason contains `gh exited 1`,
   `acme/widget`, the stderr line and the hint `run gh auth login`.
3. **Given** a stderr line that `wuwei.redact.redact` changes (a token in a URL), **Then**
   the reason holds the redacted form; a line longer than 200 characters is cut to 200.
4. **Given** gh writes an error JSON body on stdout (`{"message": "secret", ...}`), **Then**
   the body is still never in the reason (unchanged).
5. **Given** a gh `search/commits` call whose endpoint carries an email, **Then** the reason
   says `search` and holds no email.

### User Story 4 - Commands run before a plan answer with the state and the next command (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_reasons.py -k before_plan`.

**Acceptance Scenarios** (a fresh workspace with no day state unless stated):

1. `bin/wuwei close` exits 0 and prints `Nothing to close today: no day has started. Start
   one with /wuwei:wuwei-plan.`; no state file or event is written.
2. `bin/wuwei report` exits 0 and prints `No report today: no day has started. Start one
   with /wuwei:wuwei-plan.`
3. `bin/wuwei decision show D-1` exits 0 and prints `No D-1 today; bin/wuwei nudges lists
   open decisions.`; the output holds no `Errno` and no path.
4. `bin/wuwei goals` with no goal heading in `memory/goals.md` exits 0 and prints `No goals
   yet: run /wuwei:wuwei-plan and approve the proposed goals, or bin/wuwei goals edit.`;
   with goals `G-1` and `G-2` it exits 0 and prints one line per goal with its id,
   priority, outcome, measure, target and date. `bin/wuwei goals edit` is unchanged.
5. `bin/wuwei plan template` exits 0 (regression).
6. `bin/wuwei build check DIV-1` with no build record keeps exit 2; its reason names
   `DIV-1`, that no build is waiting for checks, and `bin/wuwei build next DIV-1`. With a
   build in status `ready` the reason names `ready`.
7. `bin/wuwei dispatch next DIV-1` before the gate keeps exit 1 and names
   `/wuwei:wuwei-plan`; with `DIV-1` approved in phase `implement` it names `implement` and
   `bin/wuwei build next DIV-1`.
8. `bin/wuwei plan approve --items DIV-1 --goals-confirmed` with no `plan.md` keeps exit 1
   and names `/wuwei:wuwei-plan`.

### User Story 5 - The integrity refusal names both plugin paths when they differ (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_integrity.py -k both_paths`.

**Acceptance Scenarios**:

1. **Given** a cached verdict written while `integrity.PLUGIN` was copy A, **When**
   `cached(root)` runs with `integrity.PLUGIN` set to copy B, **Then** it is exit 2 and the
   reason names A as confirmed and B as running, and both fixes: start Claude Code with A
   (`claude --plugin-dir A`) or run `bin/wuwei integrity reconfirm` in a host terminal to
   confirm B.
2. **Given** a confirmation recorded for A and `check(root)` run by B, unconfirmed, **Then**
   the reason names A and B the same way.
3. **Given** records without a plugin path (written before this change) or with the same
   resolved path, **Then** behaviour and text are unchanged.

### User Story 6 - Doctor speaks to the person, with the real launcher (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k "launcher or stray or setup_shadow"`.

**Acceptance Scenarios**:

1. **Given** the vcs adapter prints `git.identity: could not run: git exited 1` to stderr
   during the diagnosis, **When** `doctor.run` runs, **Then** stderr is empty and the row
   still carries the reason.
2. **Given** no workspace, **Then** the workspace row's fix is `<launcher> setup --shadow in
   the directory that holds your repositories`, where `<launcher>` is
   `integrity.PLUGIN / 'bin/wuwei'`, and a missing global identity gives the row `ok` with
   `not set globally; setup reads each repository's own identity`.
3. **Given** any row whose fix names a command, **Then** `render`, `--json` and the setup
   `Next:` line show it with the real launcher path, never a bare `wuwei ` or `bin/wuwei `;
   `/plugin install wuwei@wuwei` and `/wuwei:wuwei-plan` are untouched.

### User Story 7 - Every reason names a next step, in the voice of its reader (Priority: P1)

Seat-facing text (hook reasons, exit 1 and 2 lines, anything a seat or the planner reads
from the CLI) is imperative with no pronoun; "owner" stays there. Person-facing text
(doctor, setup, the `next` step rows, nudges, widget questions and descriptions, the DM
text, the docs pages) says "you" and "your" and never "the owner".

**Why this priority**: it is the issue's first acceptance line and the guard against the
next bare wall.

**Independent Test**: `python -m pytest -q tests/test_reasons.py tests/test_docs.py -k "next_step or voice or reader"`.

**Acceptance Scenarios**:

1. **Given** every reason site under `cli/wuwei` (plan.md, "Collector"), **Then** each
   string names a next step or carries a d2 family constant; a pass-through wrapper
   (`f'build: {exc}'`) is exempt. The failure message lists `file:line: text` per wall.
2. **Given** a synthetic module with `raise ValueError('invalid thing')`, **Then** the
   collector reports it; with `raise ValueError(f'invalid thing; {DAMAGED}')` or
   `print(f'wuwei x: {exc}', file=sys.stderr)` it reports nothing.
3. **Given** every seat-facing reason string, **Then** none contains `you` or `your` as a
   word.
4. **Given** the person-facing strings, **Then** none contains `the owner` (any case).
5. **Given** `docs/site/*.md` except `agent.md` and `charter-overrides.md`, with the
   Glossary section of `concepts.md` removed, **Then** none contains `the owner` (any case).
6. **Given** the three research.md rows marked KEEP, **Then** those strings are unchanged.

### User Story 8 - Reads pass (F18 regression) (Priority: P3)

**Independent Test**: `python -m pytest -q tests/test_posture.py -k reads_pass`.

**Acceptance Scenarios**:

1. **Given** a seeded guarded workspace, **When** the hook sees `git config --get-all
   core.hooksPath` or `ls ~/` with cwd at its root, **Then** it exits 0 with no refusal and
   no `guard.would_refuse` event.

### Edge Cases

- A reason built in a variable (`raise ValueError(reason)`) is checked where the text is
  made, not where it is raised.
- An internal invariant caught for control flow (`except ValueError: early = ...`) keeps
  working: the family text is appended after the existing text, so `pytest.raises(match=)`
  and `in` checks on the old text still hold.
- `decision show` of a missing id names no path at all; other reasons that need a path name
  it relative to the workspace where the code has the root.
- Outside a workspace every hook still returns 0, and `close` and `report` still return 0
  silently (`guard_scope`), unchanged.
- The first stderr line can be empty: the reason keeps `git exited <code>` and the
  repository and adds no hint.
- An adapter failure inside a guard is still exit 2 and blocks; only its text grows.
- Two plugin copies are compared by resolved path.

## Requirements

### Functional Requirements

- **FR-001**: The hook prints exactly one reason and at most one posture line per refused
  call for every event except SessionStart: the enforced refusal with the lowest exit code,
  an integrity refusal after any other, ties in guard discovery order. `hook.refusal` still
  records every enforced refusal.
- **FR-002**: commit_push names the worktree's item and branch, the check name and HEAD
  prefix, and `bin/wuwei build check <ITEM>` in its push refusals; a bare push or a push
  without a refspec is a finding (exit 1), not "could not run".
- **FR-003**: The owner-action table and the opaque owner-action reasons name the command
  and where it runs.
- **FR-004**: `git` and `gh` adapter failures carry the subcommand, the repository (path for
  git; `owner/name` for gh when the endpoint or URL names one), the first non-empty stderr
  line (redacted, at most 200 characters) and one hint where the line matches a known case
  (missing remote ref: `run git -C <repo> fetch origin`; gh not signed in: `run gh auth
  login`). The substrings `git exited <code>` and `gh exited <code>` stay.
- **FR-005**: `close`, `report`, `decision show <missing id>` and bare `goals` answer the
  state with exit 0; `build check`, `dispatch next` and `plan approve` keep their exit codes
  and name the state and the next command.
- **FR-006**: The integrity verdict and confirmation records carry the plugin path, and the
  refusal names the confirmed and the running path when they differ.
- **FR-007**: Doctor captures adapter stderr while it diagnoses, suggests `setup --shadow`
  without a workspace, treats a missing global identity as `ok` when there is no workspace
  or every repository sets its own, and writes every `fix` with the real launcher path.
- **FR-008**: Every reason string under `cli/wuwei` names a next step or carries one of the
  six d2 family constants from `cli/wuwei/exits.py`; `tests/test_reasons.py` enforces it.
- **FR-009**: Seat-facing reasons never say "you" or "your"; person-facing text and the docs
  pages never say "the owner". Records keep `Decided-by: owner`; config keys (`[owner]`,
  `owner.handles`) stay.
- **FR-010**: The d1 rewrites in research.md are the starting text; KEEP rows stay.

### Key Entities

- **Reason string**: a string literal at a reason site (raise, stderr print, `Result(1|2,
  ...)`, guard `return 1|2, ...`, the owner-action table).
- **Family constant**: one of six shared texts for internal invariants (damaged records,
  plan and rank JSON, adapter and runtime results, hook payloads, races, symlinked records).

## Success Criteria

- **SC-001**: `tests/test_reasons.py` reports zero walls over `cli/wuwei`.
- **SC-002**: A guarded `git push` from an item worktree with a missing fast check prints
  one reason a builder can run as written.
- **SC-003**: Each command line reproduced under "Root cause" now exits as FR-005 says and
  prints a next command.
- **SC-004**: The full suite passes.

## Assumptions

- The d2 family text is appended to the existing message (`invalid decision ledger; ` plus
  the shared text), not substituted for it: the specific text is what doctor, `wuwei why`,
  existing tests and a maintainer need, and the shared text gives the next step.
- "Most specific" means a finding (exit 1) before a could-not-run (exit 2), with the
  integrity gate last: it refuses every call in the workspace and SessionStart already
  reports it, so a call-specific reason is more useful. Ties keep discovery order
  (alphabetical module names). One posture line means the chosen refusal's line.
- `build check`, `dispatch next` and `plan approve` keep non-zero exits: their 0 means
  "checks passed", "next step returned" or "approved", and the planner loop reads the code.
  Only commands whose question a state answers (`close`, `report`, `decision show`, `goals`)
  exit 0 before a plan.
- `decision show` of a missing id exits 0 (it answers "is there a D-1 today"); other read
  errors keep exit 2.
- The existing assertion that git stderr never reaches the reason
  (`tests/test_vcs.py::test_git_exit_is_explained`) is reversed on purpose by FR-004. The
  line goes through `wuwei.redact.redact` and a 200-character cap; gh error bodies on stdout
  stay out.
- The item worktree is `<root>/worktrees/<ITEM>` on branch `<item lowercased>`
  (`commands/worktree.py`). A repository outside that layout gets `<branch>` and
  `bin/wuwei fast-checks`.
- Person-facing scope for the voice test: `commands/doctor.py`, `commands/setup.py` and
  `commands/nudges.py` (whole modules, docstrings excluded), `commands/next.py` `step`,
  `control_plane.py` `HELP`, `render`, `escalate` and `notify`, and the question and option
  descriptions of every `decision.widget` call. Every other reason string is seat-facing.
  `next.orientation` and `next.POSTURES` are SessionStart context for the session, not
  reason sites, and stay as they are. Interview texts (`interview.py`) are out of scope.
- Docs scope: `docs/site/*.md`. `agent.md` (agent-facing) and `charter-overrides.md` (the
  charter page) are exempt, as is the Glossary section of `concepts.md`. `README.md`,
  `SECURITY.md` and the skills are out of scope; SECURITY.md keeps the threat-model
  sentence a test pins.
- The launcher in doctor fixes is `integrity.PLUGIN / 'bin/wuwei'`, the path doctor already
  shows in its `launcher` row. No `wuwei` shim is installed on PATH.
- Line numbers in research.md are stale (0.12.0); rows are matched by file and text.
- Seat-facing reasons name `bin/wuwei <command>`, as the issue's examples do; seats resolve
  it through `.wuwei/executable` (unchanged guidance in `next.orientation`).
- F18 needs no code change on main; this feature only pins it.
- Built differently from the first draft of this spec (decided while building):
  - `decision show <missing id> --widget` exits 1 with the same line: `--widget` callers read
    JSON, so a non-JSON answer is a finding there. Without `--widget` it exits 0 as above.
  - The integrity cache names both plugin paths only for a development checkout or a failed
    verdict. A signed release verifies wherever it runs, so two sessions on two signed copies
    of the same release keep passing.
  - The catalogue rewrite keeps each message's leading text and appends the next step drawn
    from its d1 row (`<what happened>; <command>`), so `wuwei why`, doctor rows and
    existing `match=` tests keep their anchors. Wholesale rewrites were used where the text
    was itself the wall (F12, commit_push, the owner-action table, integrity, doctor).
  - The collector skips one-word strings (outward's `draft` tier is a token, not a reason)
    and `raise AttributeError` (the module `__getattr__` protocol).
