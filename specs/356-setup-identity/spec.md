# Feature Specification: setup fills the owner's code-host identity and bot authors, the interview chooses the adapters, and doctor warns on every empty setting that would block the PR flow

**Feature Branch**: `356-setup-identity`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #356. The planner's own report on the second first-day trial
(2026-10-03), forwarded by the owner: `owner.handles`, `shepherd.lead_login`,
`shepherd.review_channel` and `shepherd.authors` were all empty, and the tracker, chat and
review-bot adapters were `none`, so discovery had no backlog and the first `pr raise` would
have failed. Builds on #343 (setup), #279 (interview), #342 (doctor), #207 (solo owner),
#177 (shepherd actions).

## Root cause (read and reproduced on main, ed28ab4)

Reproduced in-process against the shipped template (`templates/workspace/config.toml`):
`owner.handles = []`, `shepherd.lead_login = ""`, `shepherd.review_channel = ""`,
`shepherd.authors = {}`, adapters tracker, chat and review_bot all `none`;
`obligations._owner_login` raises `owner.handles needs one unambiguous code-host login`;
`interview.question('tracker' | 'chat' | 'review_bot')` raises `unknown interview question`;
`doctor.SECTIONS` has no PR flow section.

- `cli/wuwei/commands/setup.py:118-169` (`discover`) measures `gh` auth (`:122`), each
  repository's remote, default branch and git identity, but never the authenticated login.
  `_setup` (`:187`) builds its `extra` settings at `:214-219` from the scanner and posture
  only, so nothing it measured reaches `owner.*` or `shepherd.*`.
- The code_host port has no operation for the authenticated login
  (`cli/wuwei/registry.py:34-40`; `adapters/code_host/github.py:65` allows only
  `api --include user`, used for token scopes, which reads headers, not the login).
- `adapters/code_host/github.py:26-27` (`_MERGED`) already fetches the recent merged PRs for
  the calibration baseline (`cli/wuwei/calibrate.py:593`) but reads no author, so the bot
  authors on those PRs are invisible.
- `cli/wuwei/interview.py:66-179` (`QUESTIONS`) has no tracker, chat or review-bot question,
  so `adapters.*` stays at the template's `none` unless the owner edits the file.
- `cli/wuwei/commands/doctor.py:16-17` (`SECTIONS`) and `:414-438` (`diagnose`) have no row
  for any of these keys; the planner wrote its "settings that will bite later" list by hand.
- `shepherd.authors` cannot take a setup-written entry today: `cli/wuwei/workspace.py:121`
  makes `mention` required and nonblank (reproduced: `shepherd.authors.<email>.mention:
  required`), and setup cannot measure a chat mention. `calibrate.apply`
  (`cli/wuwei/calibrate.py:499`) writes keys bare and values as JSON, which is invalid TOML
  for an email key and for an inline table.

## User Scenarios & Testing

### User Story 1 - setup fills what it can measure (Priority: P1)

The owner runs `bin/wuwei setup` with `gh` signed in. The digest proposes `owner.handles`
with the code-host login, `shepherd.lead_login` equal to it, and one `[shepherd.authors]`
line per owner git email and per bot author seen on the repositories' recent merged PRs.

**Why this priority**: without `owner.handles` every PR command (`pr raise`, obligations,
replies) exits 2 at its first step.

**Independent Test**: `python -m pytest -q tests/test_setup.py -k identity`.

**Acceptance Scenarios**:

1. **Given** setup on a host where `gh` is authenticated as a login and the repositories'
   last 50 merged PRs include `dependabot` and `renovate` bot authors, **When** the owner
   confirms the digest, **Then** `owner.handles` contains the login, `shepherd.lead_login`
   equals it, and `shepherd.authors` maps each repository identity email to the login and
   each bot's noreply email to its `<name>[bot]` login; the digest shows each as one line.
2. **Given** `owner.handles` already holds a chat ID only, **When** setup runs, **Then** the
   login is appended and the chat ID kept.
3. **Given** `owner.handles` already holds a code-host login, or `shepherd.lead_login` is
   set, or an author email is already mapped, **When** setup runs, **Then** that value is
   not proposed again or changed.
4. **Given** `gh` is not signed in (or the login read fails), **When** setup runs, **Then**
   it prints `code host login: unmeasured`, proposes no owner, lead or owner-email value,
   and still proposes the bot authors it measured.

### User Story 2 - the interview chooses the adapters (Priority: P1)

The interview asks one question each for tracker, chat (with the Slack review channel ID as
its free answer) and review bot, each with `None` as a valid answer.

**Why this priority**: discovery silently had no backlog because nothing asked.

**Independent Test**: `python -m pytest -q tests/test_interview.py -k adapters`.

**Acceptance Scenarios**:

1. **Given** the interview answered `tracker=Linear` and `chat=None`, **When** the answers
   are promoted, **Then** `adapters.tracker = "linear"`, `adapters.chat = "none"`, and
   `config check` prints `tracker.linear: LINEAR_API_KEY: missing` and exits 1 until the
   owner sets it.
2. **Given** `chat=C0123ABCD` (free text), **When** promoted, **Then**
   `adapters.chat = "slack"` and `shepherd.review_channel = "C0123ABCD"`.
3. **Given** `review_bot=Greptile`, **When** promoted, **Then**
   `adapters.review_bot = "greptile"` and `config check` names `GREPTILE_API_KEY`.
4. **Given** the morning gate, **When** the planner runs `calibrate --questions`, **Then**
   the three new questions are widgets in the existing format.

### User Story 3 - doctor has a PR flow section (Priority: P1)

`bin/wuwei doctor` prints a `PR flow` section; `bin/wuwei doctor --section pr-flow` prints
only that section, cheaply.

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k pr_flow`.

**Acceptance Scenarios**:

1. **Given** a workspace with `owner.handles`, `shepherd.lead_login` and `shepherd.authors`
   empty, `adapters.chat = "slack"` and `shepherd.review_channel` empty, **When** doctor
   runs, **Then** each of those four rows is `warn` with a value ending
   `will block: <what> at <phase>` and a `fix:` line with the exact command, and the exit
   is 1.
2. **Given** all of them filled, or the adapters deliberately `none`, **When** doctor runs,
   **Then** every PR flow row is `ok`; a `none` adapter row reads `none: <what discovery or
   the shepherd skips>`; `shepherd.review_channel` appears only when chat is not `none`.
3. **Given** `shepherd.min_reviewers = 0` (solo owner, #207), **When** doctor runs, **Then**
   the lead, authors and channel rows are `ok` with `not applicable: shepherd.min_reviewers
   = 0`; `owner.handles` still warns when empty (every PR command needs it).
4. **Given** `--section pr-flow`, **When** doctor runs, **Then** only PR flow rows print,
   no other section is measured, and the exit rule is unchanged (1 on any warn, else 0).

### User Story 4 - the planner shows the doctor rows, not a hand-written list (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_plan.py tests/test_docs.py -k pr_flow`.

**Acceptance Scenarios**:

1. **Given** a workspace with a PR flow warning, **When** `plan propose` runs, **Then**
   `plan.md`'s measured sweep has one `pr-flow:` line naming the warned keys and
   `wuwei doctor --section pr-flow`; with none it reads `measured: ok`.
2. **Given** the planner skill, **When** it starts the day, **Then** it runs
   `wuwei doctor --section pr-flow` once and, on exit 1, shows that output in its first
   message instead of writing its own list.

### Edge Cases

- `owner.handles` with two code-host logins already: setup proposes nothing for it (adding
  would keep it ambiguous); doctor warns with the `_owner_login` error.
- A PR author that is a deleted account (`author: null`) or a bot without a `databaseId`:
  skipped.
- A repository whose merged PR read fails or whose code host is `none`: no bot authors from
  it; the baseline stays `unmeasured` as today.
- An owner email with capitals: written lowercase, because `shepherd._rank` looks up
  casefolded emails (`cli/wuwei/shepherd.py:43-47`).
- `config.toml` without a `[shepherd.authors]` header: the table is appended.
- `--section pr-flow` outside a workspace or with a config that does not load: one
  `unmeasured` row, exit 2.

## Requirements

### Functional Requirements

- **FR-001**: The code_host port MUST gain a read `viewer_login()` returning
  `{'login': <login>}`; the GitHub adapter reads it with `gh api user` (one new allowlist
  entry), validates the login and fails closed (exit 2) on an error body, `null` or an
  invalid login; the `none` adapter records an unmeasured call.
- **FR-002**: The GitHub `merged_prs` read MUST also return each PR's `author` (a bot's
  login suffixed `[bot]`, `None` for a deleted account) and `author_email` (a bot's GitHub
  noreply commit email `<databaseId>+<login>[bot]@users.noreply.github.com`, else `None`),
  from the same GraphQL call, now over the last 50 merged PRs.
- **FR-003**: `calibrate.survey` MUST keep each repository's bot authors as
  `result['bots']` (`{email: login}`), `None` when unmeasured, from the one `merged_prs`
  call it already makes.
- **FR-004**: `setup` MUST print `code host login: <login>` or `unmeasured`, and add to the
  proposal, as setup defaults that an interview answer or a profile overrides: the login
  appended to `owner.handles` when it holds no code-host login; `shepherd.lead_login` when
  empty; one `shepherd.authors` entry `{login = ...}` per repository identity email and per
  bot email not already mapped.
- **FR-005**: `shepherd.authors.*.mention` MUST become optional (default `""`). The review
  ping still refuses a reviewer without a valid mention (`shepherd._mentions`, unchanged).
- **FR-006**: `calibrate.apply` MUST write a `shepherd.authors` key quoted and a dict value
  as a TOML inline table.
- **FR-007**: The interview MUST gain workspace questions `tracker` (None, Linear), `chat`
  (None, Slack, or free text: a Slack channel ID, which sets chat to slack and
  `shepherd.review_channel`) and `review_bot` (None, Greptile); each choice that needs a
  credential names its `.wuwei/env` variable in its description; `config check` reports it
  missing through the existing `requirements` table.
- **FR-008**: `doctor` MUST gain section `pr-flow` titled `PR flow` with rows
  `owner.handles`, `shepherd.lead_login`, `shepherd.authors`, `shepherd.review_channel`
  (only when chat is not `none`), `adapters.tracker`, `adapters.chat`,
  `adapters.review_bot`, built with the existing `_row`, `render` and `outcome`.
- **FR-009**: `doctor --section pr-flow` MUST compute and print only that section; it
  composes with `--json`.
- **FR-010**: `plan propose` MUST add one `pr-flow` sweep line from the same rows; the
  planner skill MUST run `wuwei doctor --section pr-flow` once at the start of the day and
  show its output when it exits 1.

## Success Criteria

- **SC-001**: After `setup` on a signed-in host, `bin/wuwei pr raise` no longer exits 2 on
  `owner.handles`.
- **SC-002**: A fresh first-day workspace shows every empty PR flow key in doctor and in the
  planner's first message, each with its fix command.
- **SC-003**: The full suite passes; the only new external call is one `gh api user` per
  setup run.

## Assumptions

- The issue asks for "the git email's local part" as a second handle "when they differ".
  Not done: `obligations._owner_login` (`cli/wuwei/obligations.py:208-213`) requires exactly
  one code-host handle, so a second one breaks every PR command (reproduced). The git
  emails go into `shepherd.authors` instead, which is where an email maps to a login.
- `shepherd.authors` is an email-keyed table of `{login, mention}`, not a list of logins.
  "Lists the login plus the bot authors" is met by mapping the owner's repository identity
  emails to the login and each bot's noreply email to its `[bot]` login. This also stops
  reviewer selection from failing on a bot commit email the code-host search cannot resolve.
- The bot noreply email is built from the GraphQL `Bot.databaseId` and the GitHub format
  `<id>+<login>[bot]@users.noreply.github.com`, inside the GitHub adapter. If the id ever
  differs, the entry never matches and reviewer selection falls back to today's per-email
  search; no regression.
- "Last 50 PRs" means the last 50 merged PRs, the list the calibration already reads. The
  calibration baseline medians are now over 50 instead of 30 PRs.
- Tracker choices are `None` and `Linear` only: there is no `adapters/tracker/github.py`,
  and `load_config` refuses an unknown adapter name. A GitHub tracker is its own issue.
- Review-bot choices are the installed adapters (`none`, `greptile`), listed statically.
- The review channel is the chat question's free answer rather than a conditional fourth
  question; choosing `Slack` without an ID leaves the channel empty and doctor warns.
- `shepherd.authors` has no `config set` form (the dotted-key grammar cannot hold an email),
  so its fix line is `bin/wuwei setup`, which now fills it, or the exact line to add under
  `[shepherd.authors]`.
- Doctor PR flow rows are offline: they read config only. Fix lines use placeholders
  (`<code-host login>`, `<channel id>`); setup is the path that fills measured values.
- With `shepherd.min_reviewers = 0` the lead, authors and channel do not block anything
  (`cli/wuwei/obligations.py:145-146` already marks reviewer and channel-post not
  applicable), so those rows are ok there.
- No dry-run workspace was named in the orchestrator notes; the failure was reproduced
  in-process against the shipped template and read in the code at the lines above.
