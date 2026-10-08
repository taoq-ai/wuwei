# Feature Specification: One setup question for autonomy, the interview on upgrade, and the harness allowlist card

**Feature Branch**: `530-setup-autonomy`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #530 part C: the first setup question picks autonomous or supervised and
writes the config at once; init --upgrade and doctor report unanswered setup questions and the
planner asks them at the next plan whatever the day; init proposes the Claude Code permission
allowlist on a card (owner comment 5 and the Scope bullets "One setup question" and "The
harness classifier"). Builds on part A (`autonomy.mode`, #530 decision classes) and #529 (a card
answer is the confirmation of the config write).

## Root cause

- One answer, five keys, three questions. `cli/wuwei/interview.py:222-232` (`posture`),
  `:335-341` (`tier`, `outbound.default_tier`) and `:342-348` (`learn`, `outbound.learn`) ask
  three separate questions for keys one owner preference decides, and no row writes
  `autonomy.mode` (`cli/wuwei/workspace.py:144`, part A only reads it) or a merge default.
- No merge default the owner can set. `cli/wuwei/workspace.py:81` allows `merge.default_tier`
  only `""`, `ask` or `owner_only`, and `cli/wuwei/grants.py:99-111` (`active`) lets an action
  through only on a `[grants]` standing line or a recorded card answer. So every merge the
  merge policy does not clear writes a card (`grants.py:181-209`), and the lead's planned merge
  gets a gate card (`grants.py:251-287`), even on the owner's own repositories under
  autonomous.
- Observe is treated as a trial. `cli/wuwei/interview.py:409-410` starts
  `guards.shadow_since` on an observe answer, so after `guards.shadow_days` the status line
  (`cli/wuwei/commands/status.py:242-246`) and doctor (`cli/wuwei/commands/doctor.py:450-457`)
  nudge the owner back to guarded every day. Under the autonomous answer observe is the chosen
  posture, not a trial week.
- The interview runs only on day one. `cli/wuwei/commands/next.py:202-205` returns the
  `calibrate` card row only when no earlier day directory exists, so a workspace created before
  #412, or upgraded, is never asked. `cli/wuwei/commands/init.py:312-427` (`upgrade`) never
  reads the answers, and `cli/wuwei/commands/doctor.py:432-437` reports only today's answer
  count (`none today`), never what is unanswered.
- Nothing proposes the harness allowlist. `cli/wuwei/commands/init.py:66-71` writes only
  `permissions.deny` into `.claude/settings.json`; no command proposes the `permissions.allow`
  rules WUWEI's own commands and the configured adapters need, so Claude Code's permission
  prompt or classifier stops the planner and the seats on WUWEI's own calls.

## User Scenarios and Testing

### User Story 1: One answer sets autonomy (Priority: P1)

The owner answers the first setup question, Autonomous (recommended) or Supervised, on a card
or at setup's terminal. That one answer writes the posture, the outbound umbrella, the merge
default for the owner's own repositories, the learn mode and the autonomy mode. Nothing else
asks for these keys.

**Independent Test**: neutral workspace in `tmp_path` with one configured repository
`example/project`; `interview.settings({'autonomy': label}, config)` and `wuwei calibrate
--answer autonomy=<label>` after the card answer.

**Acceptance Scenarios**:

1. **Given** a fresh workspace and the card answered Autonomous, **When** `wuwei calibrate
   --answer autonomy=Autonomous` runs from the planner session, **Then** config holds
   `security.posture = "observe"`, `outbound.default_tier = "send"`, `merge.default_tier =
   "today"`, `outbound.learn = "auto"`, `autonomy.mode = "autonomous"`, one `config.set`
   event names those five keys and the card `autonomy`, and `guards.shadow_since` stays empty.
2. **Given** the same with Supervised, **Then** config holds `guarded`, `ask`, `ask`, `card`,
   `supervised`.
3. **Given** the interview table, **Then** `autonomy` is its first row, and no row other than
   `autonomy` writes `security.posture`, `outbound.default_tier`, `outbound.learn`,
   `merge.default_tier` or `autonomy.mode` (the `posture`, `tier` and `learn` rows are gone).
4. **Given** `bin/wuwei setup --shadow`, **Then** the autonomy question is not asked and is
   recorded as `Autonomous` (it is the observe answer), as the posture question was before.

### User Story 2: Merges on the owner's own repositories run under the autonomous answer (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `merge.default_tier = "today"`, posture observe or guarded, and a merge the merge
   policy does not clear on a configured repository (`repo:example/project` or
   `pr:example/project#7`), **When** `wuwei merge` reaches the grant gate, **Then** no card is
   written, the merge runs (its 4.6 preconditions still checked) and one `grant.used` event
   records `decision: merge.default_tier`, `scope: today`.
2. **Given** the same on a repository that is not configured (`repo:other/elsewhere`), or for
   `deploy`, `release`, `publish` or `evidence`, or under strict, or after `close_requested`,
   **Then** the behaviour is today's: the card (or the host-terminal line under strict).
3. **Given** the owner answered Keep owner-only on a card for that merge target today, **Then**
   the Keep answer wins and the default does not apply.
4. **Given** the lead lists a planned merge on a configured repository, **When** `plan
   propose` runs with `merge.default_tier = "today"`, **Then** no planned grant card is
   written and `plan.md` lists `Owner-only: merge repo:example/project (merge.default_tier)`.

### User Story 3: The interview runs on upgrade (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a workspace on day 5 (four earlier day directories) with no `interview.json`
   anywhere and one configured repository, **When** `bin/wuwei init --upgrade` runs, **Then**
   it prints `setup: N questions unanswered: bin/wuwei setup, or the planner asks them on
   cards`, where N is the real count of unanswered rows (repository rows counted once per
   configured repository).
2. **Given** the same, **When** `bin/wuwei doctor` runs, **Then** its `interview` row is
   `warn` with value `N questions unanswered` and fix `bin/wuwei setup, or the planner asks
   them on cards`; with every question answered the row is `ok` (`all setup questions
   answered`).
3. **Given** the same, **When** the planner runs `wuwei next` after the gate and the goals,
   **Then** the next row is `calibrate` (`card`, `wuwei calibrate --questions`), whose widget
   list holds the unanswered questions with `autonomy` first.
4. **Given** every question answered, **Then** the `calibrate` row's widget list is `[]`, so
   `wuwei next` passes it in the same call and returns the next row, as the telemetry row does
   today (implementation note: an empty widget list is never returned as a card).

### User Story 4: The harness allowlist card (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the `allowlist` card answered Allow, **When** `wuwei calibrate --answer
   allowlist=Allow` runs from the planner session, **Then** `.claude/settings.local.json`
   gains exactly the rules `init.allow_rules(config, executable)` returns in `permissions.allow`,
   every other key and rule is kept, and it prints each rule written.
2. **Given** the proposed rules, **Then** none matches a deploy, release, protected-branch push
   or force push: no rule pattern matches any `PERMISSIONS_DENY` command, `git push origin
   main`, `git push --force`, `git push --tags`, `gh release create v1`, `gh pr merge 1
   --admin` or `gh api repos/o/r/releases`.
3. **Given** the card answered Not now, or the answer not on the card, or the strict posture,
   **Then** `settings.local.json` is unchanged; when the answer was Allow, the command prints
   `Next: run bin/wuwei calibrate --interview allowlist in a host terminal` (a terminal answer
   there writes it).
4. **Given** the Allow choice, **Then** its description says in one line that production
   reads of the owner's projects stay the owner's decision.
5. **Given** `bin/wuwei setup` answered Allow at the terminal, **Then** setup writes the same
   rules.

### Edge Cases

- An `interview.json` of an earlier day holding `posture`, `tier` or `learn` still counts
  through `_recorded` (membership only) and never re-asks. Today's file written by an older
  table before an upgrade the same day fails `interview.load` with its usual reason naming the
  unknown id; the owner reruns the question (`bin/wuwei calibrate --interview autonomy`).
- `wuwei config set security.posture ...` (or the umbrella, the learn mode or the merge
  default) from a session names the decision-card path, not the autonomy card: `card_for`
  skips the `autonomy` row, which sets five keys at once.
- With no configured repository, repository rows count zero unanswered questions.
- A damaged `interview.json` makes the doctor row `unmeasured` (as today) and init --upgrade
  print `setup: unanswered questions unmeasured: <reason>` without failing the upgrade.
- The executable path in `.wuwei/executable` changes on a plugin upgrade; the old rule stays in
  `settings.local.json` and the new one is not added until the owner answers the card again
  (Deferred).
- A merge on a repository whose `merge_deploys` is not `false` is still refused by `wuwei
  merge` (`merge.py:212`), grant or not, so the merge default never deploys.

## Requirements

### Functional Requirements

- **FR-001**: `interview.QUESTIONS` MUST start with the workspace row `autonomy` (header
  `Autonomy`) with exactly two choices, `Autonomous` (first, recommended) with effects
  `{'security.posture': 'observe', 'outbound.default_tier': 'send', 'merge.default_tier':
  'today', 'outbound.learn': 'auto', 'autonomy.mode': 'autonomous'}` and `Supervised` with
  `{'security.posture': 'guarded', 'outbound.default_tier': 'ask', 'merge.default_tier': 'ask',
  'outbound.learn': 'card', 'autonomy.mode': 'supervised'}`. The rows `posture`, `tier` and
  `learn` MUST be removed.
- **FR-002**: `interview.settings` MUST NOT add `guards.shadow_since`; `setup --shadow` keeps
  writing it through its own `extra` settings.
- **FR-003**: `setup --shadow` MUST skip the `autonomy` row and record `autonomy =
  Autonomous`.
- **FR-004**: `interview.card_for` MUST skip the `autonomy` row.
- **FR-005**: `merge.default_tier` MUST accept `today`. `grants.active` MUST return `('today',
  'merge.default_tier')` for action `merge` when the tier is `today`, the posture is not
  strict, `close_requested` is not set, no other grant matched, no grant row for that action
  and target is answered `keep`, and the target is `repo:<name>` or `pr:<name>#<n>` for a
  configured `[[repos]]` name. Every caller (`grants.gate`, `merge.by_grant`) gets it through
  `active`; no other action and no other repository is covered.
- **FR-006**: `grants.plan` MUST NOT write a planned card for an entry `active` covers with
  `merge.default_tier`, and MUST list it as `(merge, target, 'merge.default_tier')`.
- **FR-007**: `interview.unanswered(root, repos)` MUST return the `(row, repo)` pairs no
  recorded answer covers, in table order (repository rows once per given repository, none
  when `repos` is empty); `interview.widgets` with no ids MUST use it.
- **FR-008**: `init --upgrade` MUST print `setup: N questions unanswered: bin/wuwei setup, or
  the planner asks them on cards` when N > 0 (not counted as a workspace change), and doctor's
  `interview` row MUST report the count as above. The fix text is one constant in
  `interview.py`.
- **FR-009**: `next.step` MUST return the `calibrate` card row once per day whatever the day
  number (the `earlier` condition removed), and its `then` MUST say to show the owner any
  printed `Next:` line; `next.py` still never imports `interview` or `calibrate` (hook path).
- **FR-010**: `interview.QUESTIONS` MUST end with the workspace row `allowlist` (header
  `Permissions`), choices `Allow` with effect `{'allowlist': True}` and `Not now` with `{}`.
  `allowlist` is not a config key (`_setting` excludes it) and `describe` names
  `.claude/settings.local.json`.
- **FR-011**: `init.allow_rules(config, executable)` MUST return `Bash(<executable> *)` (the path `.wuwei/executable` holds) plus
  the fixed read and commit rules of the configured `vcs = "git"` and `code_host = "github"`
  adapters, and nothing that pushes, merges, releases, deploys or calls `gh api`.
  `init.allow(root)` MUST add them to `permissions.allow` of `.claude/settings.local.json`
  (created when missing, keys and rules kept, duplicates dropped, symlinks and the home folder
  refused as `init.settings` does today) and return the rules it added.
- **FR-012**: `calibrate --answer allowlist=Allow` MUST call `init.allow` only when
  `sessions.card_answered` confirms the card answer (never under strict); `calibrate
  --interview allowlist` at a host terminal and `setup` MUST call it on an Allow answer.
  Otherwise an Allow answer prints the `Next:` line of US4 scenario 3.
- **FR-013**: No new refusal in any posture (#530 principle 1). The new paths only skip a card
  or write a file after the owner's answer.
- **FR-014**: Design spec 9.2 MUST gain row I18 and `tests/test_invariants.py` its check: the
  setup answers never allow a publish target (`merge.default_tier = today` covers only a merge
  on a configured repository below strict; no allowlist rule matches a deploy, release,
  protected-branch push or force push). I5's check MUST also assert the shipped
  `merge.default_tier` is empty.
- **FR-015**: Docs: `docs/site/configuration.md` (the `merge.default_tier` row, the calibration
  paragraph, the card keys line) says what the one answer writes, that the interview runs at
  every plan while a question is unanswered, and what the allowlist card writes. The design
  spec changes only where the constitution requires it (the 9.2 row and the I5 note), since
  it is amended only by its owner.

## Success Criteria

- **SC-001**: The three acceptance bullets of the item pass as tests on neutral fixtures.
- **SC-002**: The touched test files pass; existing tests that named the `posture`, `tier` or
  `learn` rows are ported to the `autonomy` row; no other expectation changes.

## Assumptions

- "Grants allow today for the owner's own repositories" is the merge grant only: deploys,
  releases and publish (`deploy.deny`, the owner's own "never run" list) are the publish floor
  (owner comment 4) and keep their cards. It is a config read in `grants.active` like a
  standing line, so no grant row is created by a default (I5): the shipped value stays `""`
  and only the owner's answer writes `today`.
- The key is the existing `merge.default_tier` with a new value `today`, not a new key: it
  already holds "what a merge the policy does not clear does with no grant", and supervised's
  "grants ask" is its existing `ask`.
- CAP from the host is already main's default (`cap = 0`, #528), so the autonomy answer does
  not write `cap`; the `cap` question stays for an owner who wants a fixed number.
- Learn mode autonomous is `outbound.learn = "auto"`; supervised is `card` (the shipped
  default).
- Strict is not offered by the setup question; the owner sets it with `bin/wuwei config set
  security.posture '"strict"'` in a host terminal or a posture profile.
- Under the autonomous answer observe is the steady posture, so it starts no observe clock and
  no shadow nudge.
- "init proposes on a card": the allowlist is one more setup question, so it is counted by
  init --upgrade and doctor and asked by the planner at the next plan like the others; its
  description names what the rules cover. A dynamic card listing each rule is not needed: the
  table is fixed per adapter and the answer prints each rule it writes.
- The fixed rules are the reads and local commits the planner and seats run directly
  (`git status`, `diff`, `log`, `show`, `rev-parse`, `fetch`, `add`, `commit`, `worktree
  list`; `gh pr view`, `list`, `checks`, `diff`, `status`, `gh issue view`, `list`, `gh run
  view`, `list`; `fetch` exact, and no `gh auth status`, whose `--show-token` prints the
  token). Adapters that run inside the CLI process need no rule
  beyond the executable's.
- The `calibrate` row once per day follows the telemetry row's precedent; computing the count
  in `next.py` would import `interview` and `calibrate` on the SessionStart hook path, which
  `tests/test_hooks.py` forbids.

## Deferred

- Re-proposing the allowlist when `.wuwei/executable` changes on a plugin upgrade.
