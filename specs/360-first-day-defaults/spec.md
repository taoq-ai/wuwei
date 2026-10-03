# Feature Specification: the first day works on defaults: default branch from git, scanner off unless asked, tests measured once, solo owner asked, one ready line

**Feature Branch**: `360-first-day-defaults`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #360, from the UX adoption sweep of 2026-10-03 (findings F1, F4, F5,
F6, F8, F24). Owner's brief: "I want the adoption to be easiest as possible. The workflow
should coach people with less experience instead of simply blocking." Coaching means: what
happened, why, and the one command with real values; do it for the owner and say so before
asking, and ask before refusing. Builds on #327 (setup), #328 (calibrate fast checks), #279
(interview), #339 (doctor), #355 (`--shadow` means observe) and #356 (setup identity, the
adapter questions, the doctor PR flow section), all on `main`. #354 (y/N confirmations) is
not on `main` yet; see Assumptions.

## Root cause (read and reproduced on main, 957b43c)

Reproduced in-process in a scratch workspace (one repository `widget` on branch `trunk`, a
`pyproject.toml` with pytest config, `setup --shadow` with the digest confirmed, a fake code
host):

- **F1, gh cannot read the default branch.** With a GitHub `origin` and the code host's
  `default_branch` failing (`github.default_branch: could not run: gh exited 1`), setup
  prints only `Still owed: bin/wuwei config add-repo --name acme/widget --path widget
  --branch '<default branch>'` and exits 1: no calibration, no interview, nothing applied.
  `cli/wuwei/commands/setup.py:158-162` (`discover`) asks only `gh` and owes the repository
  when that fails; `_setup` then returns at `:239-242` because no repository was staged.
  The same happens when `gh` is not signed in (`auth != 0` skips the read at `:158`).
- **F1, no GitHub remote at all.** A fresh `git init` repository gives `Still owed: bin/wuwei
  config add-repo --name owner/repo --path widget --branch '<default branch>'`, exit 1:
  `:148-152` derives the name only from a GitHub `origin` URL, and `:160-162` owes it.
- **F2 (setup half), scanner on without asking.** `:245-246` proposes
  `adapters.scanner = "ziran"` whenever `ziran` is on PATH.
- **F4, fast checks never filled.** `:264` calls `calibrate.survey(...)` without `measure`,
  so `calibrate.classify` (`cli/wuwei/calibrate.py:142-143`) marks every test runner
  `test runner, unmeasured; run bin/wuwei calibrate --measure` and `calibrate.proposed`
  (`:606-608`) drops it: the digest says `CI only, not proposed as a fast check: acme/widget:
  python3 -m pytest -q`. Doctor's `fast_checks` row (`cli/wuwei/commands/doctor.py:280-284`)
  then says `wuwei config promote`, which also surveys without `measure`
  (`cli/wuwei/commands/config.py:221-222`) and proposes nothing: the loop.
- **F5, the solo owner is never asked.** `interview.QUESTIONS`
  (`cli/wuwei/interview.py:73-205`) has no reviewer question, and the template keeps
  `shepherd.min_reviewers = 1` (`templates/workspace/config.toml:216`).
- **F8, a flag answered it already.** `:263` asks every question (`interview.ask([], names)`),
  including `posture`, under `--shadow`. Nothing proposes `owner.name`; `:280-281` owes
  `bin/wuwei config set owner.name '"<your name>"'` although `discover` already read each
  repository's git identity (`:164-170`).
- **F6, the end of setup.** With the default branch readable, setup applies and ends with
  `Still owed: bin/wuwei config set owner.name ...; bin/wuwei promote` / `Next: /wuwei plan`
  and exit 1 (`:274-291`, `return max(check, gate.exit)` where `check` is `config check`,
  which fails on the host-protection lines). `bin/wuwei doctor` straight after reports
  integrity fail (development checkout), `acme/widget fast_checks` warn, `config check`
  fail (four `missing` host-protection lines) and `watch` warn, none of which setup named.
  `init` prints the status line as a JSON blob to paste by hand
  (`cli/wuwei/commands/init.py:118-122`), and nothing offers `watch install`.
- **F24, host protections.** `cli/wuwei/commands/config.py:234-269` (`_protection`) prints
  `missing (require status checks on trunk)` and three more lines, with no page to open and
  no command to run.
- `bin/wuwei plan template` piped to `bin/wuwei plan propose` exits 0 on the resulting
  workspace (checked), so the first plan is not blocked once setup completes.

## User Scenarios & Testing

### User Story 1 - setup finishes when gh cannot read the repository (Priority: P1)

The owner runs `bin/wuwei setup --shadow` in a project whose repository is new, unpushed,
private without the token scope, or has no GitHub remote. Setup takes the default branch
from git, says where it came from, and finishes calibration, the interview and the one
digest.

**Why this priority**: today setup stops at the host facts and applies nothing; every later
step depends on a configured repository.

**Independent Test**: `python -m pytest -q tests/test_setup.py -k "default_branch or remote"`.

**Acceptance Scenarios**:

1. **Given** a repository with a GitHub `origin` whose default branch `gh` cannot read,
   **When** setup runs, **Then** the default branch comes from `refs/remotes/origin/HEAD`
   when that ref exists, else from the checked-out branch; setup prints
   `<path>: default branch <branch> (from <origin/HEAD | the checked-out branch>; gh could
   not read it: <reason>)`, stages the `[[repos]]` table, runs the calibration and the
   interview, and applies after the one digest.
2. **Given** `gh` is not signed in, **When** setup runs, **Then** the same git fallback
   applies to every repository with a GitHub `origin`, and the line names `gh is not
   signed in` as the reason.
3. **Given** a repository with no `origin` at all and a measured code-host login
   `pat-example`, **When** setup runs, **Then** it proposes the name
   `pat-example/<directory>` with the branch from git, and prints `<path>: no GitHub remote;
   proposed as pat-example/<directory>, default branch <branch> (from <source>)`.
4. **Given** a repository whose `origin` is another host, or no `origin` and no measured
   login, or a detached HEAD with no `origin/HEAD`, **When** setup runs, **Then** it owes
   `bin/wuwei config add-repo ...` as today, with the branch filled in when git knew it.

### User Story 2 - the interview asks who reviews, and skips what a flag answered (Priority: P1)

**Why this priority**: the solo owner is the common case and `min_reviewers = 1` refuses
their first `pr raise`; `owner.name` empty refuses every outward message.

**Independent Test**: `python -m pytest -q tests/test_interview.py tests/test_setup.py -k
"reviewers or pronoun or shadow_skips or owner_name"`.

**Acceptance Scenarios**:

1. **Given** the interview, **When** it reaches `Reviewers: Who reviews your pull
   requests?`, **Then** the choices are `Owner only` (`shepherd.min_reviewers = 0`) and
   `Code authors` (`shepherd.min_reviewers = 1`), and free text is a teammate's code-host
   login, which sets `shepherd.lead_login` to it and `shepherd.min_reviewers = 1`.
2. **Given** the answer `Owner only`, **When** the digest applies, **Then**
   `shepherd.min_reviewers = 0` and doctor's PR flow lead, authors and channel rows read
   `not applicable`.
3. **Given** a teammate login answer and the setup default `shepherd.lead_login = <owner
   login>` (#356), **When** the proposal is built, **Then** the interview answer wins.
4. **Given** `setup --shadow`, **When** the interview runs, **Then** the `posture` question
   is not asked; without `--shadow` it is.
5. **Given** an empty `owner.name` and a repository identity `Pat Example`, **When** setup
   builds its proposal, **Then** the digest has `+name = "Pat Example"` under `[owner]`; a
   set `owner.name` is never proposed again.
6. **Given** any interview question, **When** it is shown in the terminal or as an
   AskUserQuestion widget asked by Claude, **Then** no choice label uses a first-person word
   (`I`, `me`, `my`, `mine`, `myself`): labels name the role (`Owner only`, `Owner merges`)
   and questions and descriptions address the owner as `you`, so a label cannot be read as
   Claude speaking.

### User Story 3 - the scanner and the test run are asked, not assumed (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_setup.py -k "ziran or measure"`.

**Acceptance Scenarios**:

1. **Given** `ziran` on PATH and `adapters.scanner = "none"`, **When** setup asks `ZIRAN is
   installed. Turn on its security scans (adapters.scanner = "ziran")? [y/N]` and the owner
   answers `y`, **Then** the digest proposes `+scanner = "ziran"`; on Enter or `n` it does
   not.
2. **Given** a repository whose calibration finds a test runner (`python3 -m pytest -q`),
   **When** setup prints `Test runner found: acme/widget: python3 -m pytest -q` and asks
   `Run your tests once now to see if they are fast enough for every push? [Y/n]` and the
   owner presses Enter, **Then** each runner is timed once through the checks port and a
   runner that passes within `calibrate.fast_check_seconds` lands in
   `repos.<n>.fast_checks` in the same, single digest.
3. **Given** the answer `n`, or a runner that fails or is too slow, **When** the digest
   shows, **Then** the runner stays `CI only, not proposed as a fast check` with its note
   (`unmeasured` or `measured 45.0 s, threshold 30 s`), as today.
4. **Given** doctor on a repository with empty `fast_checks`, **When** it prints the row,
   **Then** the fix names `bin/wuwei config promote --measure` and the exact
   `bin/wuwei config set repos.<n>.fast_checks '["<command>"]'` form with the repository's
   real index.

### User Story 4 - setup ends ready, or with one next command (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_setup.py -k "ready or status_line or
watch or first_day"`.

**Acceptance Scenarios**:

1. **Given** the digest applied (or nothing to propose) and no `statusLine` in the
   workspace `.claude/settings.json`, **When** setup asks `Show the WUWEI status line in
   Claude Code for this project? [Y/n]` and the owner presses Enter, **Then** the
   `statusLine` key is written into that file next to the `permissions` `init` wrote, and
   `n` writes nothing. An existing `statusLine` is never replaced and the question is not
   asked.
2. **Given** no watch unit installed on macOS or Linux, **When** setup asks `Install the
   watch service, which supervises the day and your pull requests in the background?
   [y/N]` and the owner answers `y`, **Then** setup runs the same install as `bin/wuwei
   watch install`; Enter or `n` installs nothing; a failed install prints its reason and
   setup continues.
3. **Given** a setup whose doctor run has no `fail` or `unmeasured` row in the Install and
   Workspace sections, no missing credential variable for a chosen adapter and a clean MCP
   gate, **When** setup ends, **Then** its last line is `Ready: run /wuwei:wuwei-plan` and
   it exits 0, even when optional items remain.
4. **Given** optional items (another repository still to add with `config add-repo`,
   `bin/wuwei promote` for the charter proposals, an `owner.name` still empty, any other
   non-ok doctor row), **When** setup ends, **Then** one line before the last reads
   `Optional: <command>; <command>; <n> more in bin/wuwei doctor` (only the parts that
   apply).
5. **Given** one or more required items, **When** setup ends, **Then** its last line is
   exactly one `Next: <command>` naming the first required item in this order: a credential
   variable, the MCP decision, the first `fail` or `unmeasured` Install or Workspace doctor
   row's fix; the exit is 1, or 2 when any required item is unmeasured (MCP gate exit 2 or
   an `unmeasured` row). The `Still owed:` block and `Next: /wuwei plan` are gone.
6. **Given** no repository could be staged at all, **When** setup stops before the digest
   (as today, exit 1), **Then** it prints `Next: <first config add-repo command>` with the
   others, if any, on the `Optional:` line before it.
7. **Given** a fresh repository with no GitHub remote, **When** setup runs with default
   answers and then `bin/wuwei plan template` output is passed to `bin/wuwei plan propose`,
   **Then** both exit 0.

### User Story 5 - host protection lines say how to fix them (Priority: P3)

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k protection`
(the file that already covers `_protection`).

**Acceptance Scenarios**:

1. **Given** `config check` on `acme/widget` branch `main` with any protection row
   `missing`, **When** it prints the rows, **Then** one more line reads
   `  acme/widget main: fix in https://github.com/acme/widget/settings/branches`.
2. **Given** the same with no classic protection on the branch, **Then** a second line
   gives one `gh api -X PUT repos/acme/widget/branches/main/protection ...` command to run
   in the owner's own terminal that blocks force pushes and deletions, requires one
   approving review (`required_pull_request_reviews=null` when
   `shepherd.min_reviewers = 0`) and requires the repository's `review_required_checks`
   (`required_status_checks=null` when none are configured); every argument is shell-quoted.
3. **Given** classic protection already exists, **Then** only the settings URL is printed,
   never a command that would replace it.

### Edge Cases

- `origin/HEAD` missing and HEAD detached: the git read fails, the repository is owed with
  the coached `config add-repo` line.
- A directory name that is not a valid `owner/repo` part (spaces): owed, as today.
- Two repositories with no remote and the same directory name under `--repos`: the second
  is `already listed, not added`, as today.
- Stdin closes during a y/N question: the answer is `no`, whatever the default, so nothing
  runs or installs without an explicit answer.
- `.claude/settings.json` is a symlink, not a JSON object, or the workspace is the home
  directory: the status line is not written; setup prints the reason and it counts as
  optional.
- `--shadow` on a workspace already in observe: the posture question is still skipped.
- The checks port times out (300 s) on a runner: `classify` already reports it as
  `exit 2` in the note; the runner stays CI only.
- No repository identity name (identity flagged or unresolved): `owner.name` is not
  proposed and stays an optional item.

## Requirements

### Functional Requirements

- **FR-001**: The vcs port MUST gain a read `default_branch(repo)` returning
  `{'branch': <name>, 'source': 'origin/HEAD' | 'the checked-out branch'}`: the target of
  `refs/remotes/origin/HEAD` without its `origin/` prefix, else the checked-out branch;
  names are validated; any other failure is exit 2.
- **FR-002**: `setup.discover` MUST use FR-001 when the code host cannot give the default
  branch (read failed, `gh` not signed in, or no GitHub remote), print where the branch came
  from and why `gh` did not answer, and stage the repository. With no `origin` at all and a
  measured login it MUST propose `<login>/<directory>`.
- **FR-003**: Setup MUST propose `adapters.scanner = "ziran"` only after a `y` to its y/N
  question; the default is no.
- **FR-004**: When the calibration finds a test runner left unmeasured, setup MUST list the
  runners and ask `[Y/n]` once; on yes it classifies those runners through the checks port
  before building the one proposal, so a fast runner is proposed as a fast check in the same
  digest.
- **FR-005**: The interview MUST gain the workspace question `reviewers` (US2 scenario 1)
  with the effects above; `settings`, `describe`, `ask`, `parse` and `widgets` pick it up unchanged.
- **FR-006**: Under `--shadow` setup MUST NOT ask the `posture` question.
- **FR-007**: `setup.identity` MUST propose `owner.name` from the first nonblank repository
  identity name when `owner.name` is empty.
- **FR-008**: No interview choice label may contain a first-person word; a test pins it for
  the whole table.
- **FR-009**: After the digest, setup MUST offer to write the `statusLine` into the
  workspace `.claude/settings.json` (`[Y/n]`, only when absent) and to install the watch
  (`[y/N]`, only on macOS or Linux with no unit installed). `init` run by setup MUST NOT
  print the paste-it-yourself JSON; plain `bin/wuwei init` keeps printing it.
- **FR-010**: Setup MUST end by running `doctor.diagnose()` and print one `Ready: run
  /wuwei:wuwei-plan` or one `Next: <command>` as its last line, with at most one
  `Optional:` line before it; exit 0 when only optional items remain (US4 scenarios 3 to
  6).
- **FR-011**: Doctor's empty `fast_checks` row MUST name `bin/wuwei config promote
  --measure` and the `config set repos.<n>.fast_checks` form with the real index.
- **FR-012**: `config check` MUST print the settings URL for each repository branch with a
  missing protection row, and the one `gh api` command when no classic protection exists
  (US5).

## Success Criteria

- **SC-001**: On a fresh repository with no GitHub remote, setup with default answers exits
  0 and the first `plan propose` exits 0 (one in-process test).
- **SC-002**: A setup run ends with exactly one `Ready:` or `Next:` line; a solo owner
  answering `Owner only` raises the first PR without changing config by hand.
- **SC-003**: The full suite passes; no new runtime dependency; the only new external call
  is one or two local `git symbolic-ref` reads per repository that `gh` could not answer.

## Assumptions

- The relayed user question ("You/I doesn't get confusing when Claude is asking?") applies
  to the reviewer question: the sweep's label `Just me` reads as Claude speaking when Claude
  asks it through AskUserQuestion. The label is `Owner only` instead, matching the existing
  `Owner merges`, and FR-008 pins the rule for every label. Questions and descriptions keep
  addressing the owner as `you`, as the whole table already does.
- The reviewer question offers `Owner only` and `Code authors` as choices and a teammate's
  login as free text (the pattern of the `chat` question), because a choice cannot carry a
  login. `Code authors` keeps the template's `min_reviewers = 1`; #369 makes reviewer
  selection from code history work without configuration.
- A repository with no remote is named `<login>/<directory>`, where `gh repo create` would
  put it by default. It is a guess the owner sees in the digest and can change later with
  `bin/wuwei config set repos.<n>.name`; without a measured login nothing is guessed.
- "Required" for the Ready line means what blocks the first plan or every hook: the
  Install and Workspace doctor sections, missing credential variables for chosen adapters
  and the MCP gate (the last two are what setup's exit already reflected through
  `config check` and `mcp check`). Another repository still to add is optional once one
  repository is configured. Host, Gates (`config check`, including
  host protections), PR flow, Day and Guards rows are optional: they are counted in the
  `Optional:` line and listed by `bin/wuwei doctor`. An empty `fast_checks` row is a doctor
  `warn`, so optional: it blocks building, not planning.
- Default answers: scanner no, measure yes (the sweep's text), status line yes, watch no.
  The watch installs a persistent launchd or systemd unit, so it needs an explicit yes.
- #354 is not on `main`. The setup questions here are preference questions on the setup
  terminal (`input`), not the owner-confirmation boundary of `integrity._host_confirm`;
  the one config digest keeps going through `config.offer`. If #354 lands first with a
  shared y/N prompt, the builder uses it instead of the local helper.
- The `owner.name` source is the repository identity setup already read (or the identity
  already in the config), not the global git identity.
- F24's settings URL and command are GitHub's, matching the only code-host adapter that
  reads protection (`adapters/code_host/github.py`).
- Out of scope, deferred: the `build next` reason for empty fast checks and the "no setting
  lowers it" refusal text (#362, #369); doctor `fix:` lines spelled `wuwei` instead of the
  launcher path (#362); `calibrate --questions` asking the interview again on the first day
  (#365); `discovery` reading the ZIRAN findings list (#361).
- No dry-run workspace was named in the orchestrator notes; the failures were reproduced
  in a scratch workspace outside the repository with the code paths above.
