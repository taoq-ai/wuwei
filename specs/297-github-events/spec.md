# Feature Specification: GitHub events reach the planner and the owner without the owner relaying them

**Feature Branch**: `297-github-events`
**Created**: 2026-10-01
**Status**: Ready
**Input**: GitHub issue #297, "feat(listener): GitHub events reach the planner and the owner
without the owner relaying them: faster PR polling, precise wakes, headless shepherd on change,
DM nudges". Owner request 2026-10-01: "a lot of my time goes into telling the main session that
PR X has comments or need to be worked on ... Can we listen to GitHub events?"

## Problem (reproduced)

Reproduced read-only on `main` (e1391fd) in a scratch pytest workspace built from the
`tests/test_watch.py` fixture (fake code host, no network): one `watch.poll` for a baseline,
then a new issue comment by `alice` and a failed check `test (3.11)` on the fake host, then a
second `watch.poll`. Observed:

- the `pr.changed` payload was `{"pr": "example/project#7", "fields": ["checks", "threads"]}`:
  field names only, nothing a reader can act on;
- `watch.wake` returned `planner wake (2026-09-28T12:00:00+00:00): example/project#7`: the
  PR reference only;
- `wuwei nudges` (`status.attention`) returned one row with reason `pr.changed`;
- `status --line` showed `nudges 1` with no PR part;
- after the planner consumed the wake, the same `pr.changed` nudge row was still listed.

Root causes, with file and line on `main`:

1. `watch.poll` (`cli/wuwei/watch.py` lines 355 to 361) records `pr.changed` and the wake with
   the changed snapshot keys only. The snapshot (`watch.snapshot`, lines 304 to 310) keeps
   fingerprints, so nothing downstream can say who commented, on which file, or which check
   failed.
2. `watch.wake` (`cli/wuwei/watch.py` lines 502 to 503) renders the PR references only, and
   the wake reaches the planner only through the Stop hook (`cli/wuwei/guards/lifecycle.py`
   line 104) and SessionStart (line 60). An idle interactive planner fires neither, so the
   owner becomes the messenger. Claude Code has no way to inject input into an idle
   interactive session; spec 4.2 and 15 answer this with the listener acting outside the
   model.
3. PR polling runs only in the watch tick (`cli/wuwei/watch.py` line 402) every
   `pr.poll_seconds` (default 120, `cli/wuwei/workspace.py` line 86), and every poll is a full
   read (PR, reviews, two comment surfaces, checks) that writes `pr.action` and
   `watch: observation` events even when nothing changed. The code host port has no
   conditional request (`adapters/code_host/github.py` `_run`, lines 54 to 104, allows no
   `If-None-Match`).
4. `status.scan` (`cli/wuwei/commands/status.py` lines 105 to 118) keys each `pr.changed`
   event by its line number with reason `payload.get('reason', kind)`, so the nudge reads
   `pr.changed` and never clears for the day.
5. No component acts on a changed PR outside the model: the mechanical PR actions exist
   (`cli/wuwei/pr_actions.py` `act`, lines 450 to 499: rebase and fast checks, fix-round
   brief, reviewer re-request, thread reply), but only a seat or the owner invokes them, and
   the listener (`cli/wuwei/listen.py` `tick`, lines 34 to 84) polls only the inbound chat
   source.
6. Nothing sends a PR change to the owner's DM; the listener sends only decisions
   (`remote.escalate_new`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A PR change carries a precise summary everywhere (Priority: P1)

When an owned PR changes, the system records one `pr.changed` event whose summary says what
changed (`PR owner/repo#12: 2 new review comments by alice on cli/x.py; check test (3.11)
failed`). The Stop hook message and SessionStart notice lead with that summary, `wuwei nudges`
lists it first, `status --line` shows `prs 1 changed`, and the nudge clears once the planner has
seen the wake.

**Why this priority**: every other story (DM, shepherd, planner) carries this summary; a bare
"changed" is the reason the owner relays PR news by hand today.

**Independent Test**: in-process `watch.poll` against the fake code host with a new comment and
a failed check, then `watch.wake`, `status.attention`, `status.line(status.snapshot(day))`.

**Acceptance Scenarios**:

1. **Given** an owned PR with a baseline poll, **When** the fake host adds two thread comments
   by `alice` on `cli/x.py` and check `test (3.11)` completes with `failure`, **Then** the next
   poll appends exactly one `pr.changed` whose payload carries `summary`
   `PR example/project#7: 2 new review comments by alice on cli/x.py; check test (3.11) failed`
   and the existing `fields`, and no comment body appears in the event or in state.
2. **Given** that change, **When** the registered planner's Stop hook runs, **Then** it exits 1
   and its message begins with that summary line, followed by the existing
   `planner wake (<at>): example/project#7` line.
3. **Given** that change and an older nudge, **When** `wuwei nudges` runs, **Then** the first row
   has source `pr.changed` and the summary as its reason, and `status --line` contains
   `prs 1 changed`.
4. **Given** the planner consumed the wake, **When** `wuwei nudges` runs, **Then** no
   `pr.changed` row remains and `status --line` has no `prs` part.
5. **Given** a change the summary rules do not name (for example only `updated_at` moved),
   **Then** the summary is `PR <ref>: updated (updated_at)`, never a bare "changed".

---

### User Story 2 - The listener detects PR changes within 30 seconds at no cost when idle (Priority: P1)

When `wuwei listen` runs it takes over PR polling from the watch. Every tick (at most 30 s
apart) it sends conditional requests (`If-None-Match` with the last ETag, through `gh api`) for
each owned PR's PR record, check runs and statuses. A `304 Not Modified` everywhere costs no
event, no state write and no wake. Any modified response, a failed probe, or a full read older
than `pr.poll_seconds` runs the existing full read (`watch.poll` and `merge.poll`) at once.

**Why this priority**: detection latency drops from up to 120 s to up to 30 s, and the quiet
case stops writing events every poll.

**Independent Test**: `listen.tick` with a fake inbound source and the fake code host whose
`probe` returns modified or not modified; a `subprocess.run` stub for the GitHub adapter's
`probe`.

**Acceptance Scenarios**:

1. **Given** a new review comment on an owned PR (fake host) and the listener running, **When**
   one listener tick runs, **Then** it records `pr.changed` with the summary, the Stop hook
   message names it, `nudges` lists it first, and the owner DM transport receives the summary.
2. **Given** no change on the host (every probe not modified) and a full read younger than
   `pr.poll_seconds`, **When** a listener tick runs after the clock line was written, **Then**
   `events.jsonl` and `state.json` are byte-identical before and after, the wake marker is
   unchanged, and `watch.poll` is not called.
3. **Given** a probe that fails (exit 2) or returns malformed data, **When** the tick runs,
   **Then** the full read runs (fail closed: never treated as unchanged).
4. **Given** a live listener (a `listen: clock` line within `listen.dead_seconds`), **When** the
   watch ticks with `poll_at` due, **Then** the watch does not poll PRs; **Given** no live
   listener, **Then** it polls as today.
5. **Given** the GitHub adapter with a stored ETag, **When** `gh api` answers
   `HTTP/2.0 304 Not Modified`, **Then** `probe` returns `modified: false` and keeps the
   ETag; an ETag containing anything outside the quoted-string form is refused before any
   process starts.

---

### User Story 3 - A headless shepherd seat acts on the mechanical PR actions (Priority: P2)

With `shepherd.autostart = true`, when the full read opens a new PR action episode in a state
with a mechanical action (`conflicted`, `ci_red`, `changes_requested`, `threads_unanswered`,
`review_stale`), the listener dispatches one headless shepherd seat for that episode: a logged
brief, the runtime adapter's `dispatch`, the seat launch guard (memory floor, host seat
ceiling, MCP gate, logged brief), then one headless Claude Code turn. The session is registered
with role `shepherd`, the seat reservation is released after the turn, and the planner's wake
carries the result. Off by default; with autostart off nothing is dispatched and the DM says
so.

**Why this priority**: removes the owner as the trigger for rebases, fix-round briefs,
re-requests and acknowledgement drafts; it builds on stories 1 and 2.

**Independent Test**: `listen.tick` with autostart on, a conflicted fake PR linked to an item
with a worktree, and a fake runtime recording `dispatch` and `headless` calls.

**Acceptance Scenarios**:

1. **Given** `shepherd.autostart = true` and a `conflicted` owned PR, **When** two listener
   ticks run, **Then** exactly one brief is logged for role `shepherd`, one `headless` call is
   made whose prompt starts with `WUWEI brief: ` and whose brief tells the seat to run
   `wuwei pr act <ref> --run` (rebase and fast checks in the item worktree) and, on a conflict,
   resolve in the worktree and run `wuwei pr act <ref> --complete`; the returned session is in
   the registry with role `shepherd`; the seat reservation is `stopped`; one
   `shepherd.dispatched` and one `shepherd.finished` event exist; and the next planner Stop
   message names the shepherd result.
2. **Given** `shepherd.autostart = false` (the default) and the same PR, **When** the tick runs,
   **Then** no brief, no runtime call and no `shepherd.dispatched` event exist, and the DM text
   says `Shepherd autostart is off; nothing started.`
3. **Given** free memory below `host.free_memory_mb` or running seats at `host.seats`, **When**
   the episode is dispatched, **Then** no headless turn runs, `shepherd.finished` records the
   refusal reason with exit 1, and the episode is not retried.
4. **Given** an `approved`, `waiting` or `merged` PR, **Then** no shepherd is dispatched.

---

### User Story 4 - The shepherd seat cannot merge and drafts every outward post (Priority: P1 within story 3)

The headless shepherd runs with `WUWEI_SEAT_ROLE=shepherd` in its environment. `merge.execute`
(the one function behind `wuwei merge` and `wuwei pr act` on an approved PR) refuses with exit 1
when that marker is set, and `outward.classify` (the one tier function behind every
text-bearing port, the MCP outward hook and `wuwei pr act --reply`) returns draft.

**Why this priority**: the issue's hard requirement for any autonomous shepherd.

**Independent Test**: in-process `merge.execute` and `outward.classify` with the variable set;
the Claude runtime adapter's `headless` with a `subprocess.run` stub.

**Acceptance Scenarios**:

1. **Given** `WUWEI_SEAT_ROLE=shepherd`, **When** `wuwei merge <ref>` runs on a PR the policy
   would clear, **Then** it exits 1 with `merge refused: a shepherd seat never merges`, and the
   host's `merge` is never called; `gh pr merge` stays refused by the existing PR guard.
2. **Given** `WUWEI_SEAT_ROLE=shepherd`, **When** a reply that would auto-send (`ack.` on an
   owned PR thread) goes through `outward.classify` or the code host `comment` port, **Then**
   the tier is draft, a draft is stored, and the adapter's `comment` is never called.
3. **Given** the Claude runtime adapter, **When** `headless` is called with
   `variables={'WUWEI_SEAT_ROLE': 'shepherd'}`, **Then** the child environment carries it;
   a variable name outside `WUWEI_[A-Z_]+` or a non-string value is refused before spawn.

---

### User Story 5 - The owner gets the change in the DM (Priority: P2)

When the listener runs with the owner DM configured (`SLACK_OWNER_DM_CHANNEL`), each new
`pr.changed` reaches the DM once through the control plane: the summary plus what the shepherd
will do or why it does not. `control_plane.content = "none"` sends the fixed line instead. A
summary the outward lint refuses (for example a repository or path containing a banned word)
falls back to `PR #<n> changed; details are on the host.`

**Independent Test**: `listen.tick` with the real `remote.TRANSPORT` over a recording chat
port, so the security check and the outward lint still run.

**Acceptance Scenarios**:

1. **Given** a new `pr.changed` with summary, **When** the tick runs, **Then** the transport
   receives one DM starting with the summary, one `pr.notified` event is recorded, and a second
   tick sends nothing.
2. **Given** `control_plane.content = "none"`, **Then** the DM is
   `An update is waiting in the workspace.`
3. **Given** a summary naming `cli/wuwei/guards/deploy.py`, **Then** the lint refuses it and the
   DM sent is `PR #7 changed; details are on the host.`
4. **Given** no `SLACK_OWNER_DM_CHANNEL`, **Then** nothing is sent and nothing is recorded.

---

### User Story 6 - Honest documentation of the idle planner (Priority: P3)

`docs/site/daily.md` and `docs/site/remote.md` state: an idle interactive planner learns of a PR
change at its next turn (Stop or SessionStart); the shepherd seat and the DM cover the gap; the
Claude Code desktop PR monitor is the complement for CI events in the owner's own session; no
webhooks or tunnels in this version.

**Independent Test**: `tests/test_docs.py` string checks.

### Edge Cases

- A probe answers 200 but the full read finds identical fingerprints: no `pr.changed`, no
  wake (the snapshot comparison is unchanged). An edit to the title or labels moves
  `updated_at`, so its summary is `updated (updated_at)`.
- A PR that is new to the baseline: summary `PR <ref>: now watched`; a PR no longer owned:
  `PR <ref>: no longer owned`.
- Several changes before the planner sees the wake: the marker keeps every summary in order
  (capped at the last 20 lines); `nudges` keeps one row per PR with the latest summary.
- Facts from before this feature (no `watch.facts` entry for the PR): the first change after
  upgrade summarises what the facts cannot compare as `updated (<fields>)`.
- The listener restarts: in-memory ETags are empty, so the first tick does one full read; no
  duplicate `pr.changed`, because the fingerprint baseline is in state.
- Listener and watch overlap for at most one watch tick at listener start; both use the same
  baseline in state.
- A shepherd turn blocks the listener tick for up to the adapter timeout (1800 s), like a
  remote command turn today; at most one shepherd is dispatched per tick.
- The shepherd's PR has no single linked item with a worktree: `shepherd.finished` records
  exit 2 with the reason; nothing runs; that episode is not retried.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `watch.poll` MUST record, for every changed owned PR, one `pr.changed` event whose
  payload carries `pr`, `fields` (unchanged) and `summary`; the summary MUST start with
  `PR <ref>: ` and name what changed from comment ids, authors, thread file paths, review
  states, check results, head, mergeability, requested reviewers and PR state; it MUST NOT
  contain comment or review bodies; when no rule applies it MUST be `updated (<fields>)`.
- **FR-002**: The wake marker MUST carry the summaries; `watch.wake` MUST put them first, one per
  line, before the existing `planner wake (<at>): ...` line; a marker without summaries renders
  exactly as today.
- **FR-003**: `status.scan` MUST keep one `pr.changed` nudge per PR with the latest summary as
  reason, list `pr.changed` rows before all others, and clear them at the next
  `session: wake-seen`; `status --line` MUST show `prs <n> changed` when n is at least 1.
- **FR-004**: The code host port MUST gain `probe(ref, tags)` returning
  `{'modified': bool, 'tags': {...}}` from conditional requests; the GitHub adapter MUST use
  `gh api <endpoint> --include [-H "If-None-Match: <etag>"]` within its closed allowlist and
  treat a 304 status line as not modified; `none` MUST report unmeasured.
- **FR-005**: The listener MUST probe owned PRs each tick and run the shared full read
  (`watch.poll`, then `merge.poll`, then `poll_at`) when any probe is modified, unreadable or
  malformed, or `poll_at` is older than `pr.poll_seconds`; otherwise it MUST write nothing.
  Its loop delay MUST be at most 30 s.
- **FR-006**: The watch MUST skip its PR poll while the listener is alive.
- **FR-007**: With `shepherd.autostart = true`, the listener MUST dispatch at most one headless
  shepherd seat per PR action episode (keyed by PR and episode `created_at`) for the states in
  FR-007a, at most one per tick, through `brief.write`, the runtime adapter's `dispatch`, the
  seat launch guard and the Claude adapter's `headless`, recording `shepherd.dispatched` before
  any side effect and `shepherd.finished` after, registering the session with role `shepherd`,
  releasing the seat, and marking a planner wake with the result summary.
  - **FR-007a**: states and seat instruction: `conflicted` (`wuwei pr act <ref> --run`;
    on a conflict resolve in the item worktree, then `--complete`), `ci_red`
    (`wuwei pr act <ref>`: opens the fix round brief and feedback; do not build the fix),
    `changes_requested` and `threads_unanswered` (`wuwei pr act <ref>`, then
    `wuwei pr act <ref> --reply "<short acknowledgement>"`: stored as a draft),
    `review_stale` (`wuwei pr act <ref>`: re-request and post; the post is a draft).
- **FR-008**: `shepherd.autostart` MUST default to `false`.
- **FR-009**: `merge.execute` MUST return exit 1 without any host call or event when
  `WUWEI_SEAT_ROLE` is `shepherd`.
- **FR-010**: `outward.classify` MUST return `(1, 'draft')` when `WUWEI_SEAT_ROLE` is
  `shepherd`.
- **FR-011**: The listener MUST send each new summarised `pr.changed` to the owner DM once,
  through `control_plane.notify` and `remote.TRANSPORT`, with the shepherd tail, recording
  `pr.notified`; a lint refusal falls back to the fixed line; no DM without
  `SLACK_OWNER_DM_CHANNEL`.
- **FR-012**: New event kinds `shepherd.dispatched`, `shepherd.finished`, `pr.notified` MUST be
  reserved to their producers; `shepherd.dispatched` and `pr.notified` are silent;
  `shepherd.finished` is silent on exit 0 and a nudge otherwise.
- **FR-013**: Docs (`daily.md`, `remote.md`, `configuration.md`) and the workspace template MUST
  describe the listener PR probe, `shepherd.autostart`, the DM nudge, the idle planner gap and
  the absence of webhooks.

### Key Entities

- **PR facts** (`watch.facts[ref]` in state): `head`, `mergeable`, `state`, `merged`,
  `requested` (sorted logins and team slugs), `seen` (`{"<surface>:<id>": [author, path or
  review state]}`), `checks` (`{name: conclusion or state}`). No bodies.
- **Wake marker** (`watch.wake`): existing `at`, `prs`, `inbox`, plus optional `summaries`
  (list of strings, last 20).
- **Probe tags** (listener memory only): `{ref: {pr, head, checks, statuses}}` ETags.
- **Events**: `pr.changed` (+`summary`), `pr.notified {pr, at}`,
  `shepherd.dispatched {pr, state, episode}`,
  `shepherd.finished {pr, state, episode, exit, session?, reason?}`.

## Success Criteria *(mandatory)*

- **SC-001**: With the listener running, a PR change on the host is in `events.jsonl`, the
  planner's next Stop message and the owner DM within one listener tick (at most 30 s plus the
  read time), against up to 120 s and no DM today.
- **SC-002**: An unchanged host costs zero events and zero state writes per listener tick.
- **SC-003**: Every `pr.changed` written after this feature carries a summary naming the change;
  none reads `pr.changed` or `changed` alone.
- **SC-004**: The owner does not need to tell the planner about a review comment, a red check or
  a conflict: the Stop message, `nudges`, the status line and the DM all carry it.
- **SC-005**: A shepherd seat cannot merge and sends nothing outward except drafts (tests).

## Assumptions

- **Probe cadence versus the issue's wording.** The issue says "default `pr.poll_seconds` 30
  when the listener runs and 120 otherwise". This is realised as a fixed 30 s conditional probe
  in the listener (`listen.PROBE_SECONDS = 30`), while `pr.poll_seconds` (default 120) keeps
  its meaning as the full-read cadence for whoever polls. Reason: a 304 costs no GitHub rate
  limit and no WUWEI event, while a full read writes `pr.action` and `watch: observation`
  events; so the detection latency is 30 s as asked, and the quiet case is free. No new config
  key. An owner who sets `pr.poll_seconds` below 30 gets full reads at that cadence (the
  listener delay is the minimum of the intervals).
- **gh and 304.** `gh api --include` prints the status line and headers before the body. For a
  non-2xx status `gh api` exits nonzero; the adapter therefore reads the status line from
  stdout first and treats `304` as not modified whatever the exit code, and treats any other
  nonzero exit as unreadable. Not verified against a live `gh` in this pipeline (no `gh`
  runs); the adapter test pins the parsing with a `subprocess.run` stub, and the live
  rehearsal confirms it.
- **What the ETag covers.** The PR record's ETag changes with `updated_at`, head, mergeability
  and the comment and review comment counts; check runs and statuses are separate endpoints at
  the head and are probed separately. A thread resolution or a review without comments may not
  change these ETags; the full read every `pr.poll_seconds` is the backstop.
- **ETags live in listener memory.** No new state key and no file; a restart costs one full
  read.
- **Seat role marker.** `WUWEI_SEAT_ROLE=shepherd` is set by the listener in the headless child
  environment. Under spec 9.1 the guards are cooperative mistake prevention, not an isolation
  boundary: the marker only restricts (forging it restricts more), and a seat that removes it
  could reach `wuwei merge`; the hard boundaries stay the code host's protected refs, required
  reviews and checks, and the merge policy. `gh pr merge` is already refused by the PR guard.
- **Runtime.** The headless turn uses the Claude Code runtime adapter, fixed, as remote commands
  do (`remote._turn`): only it has headless sessions. The runtime adapter's `dispatch` is still
  called first for the launch prompt with the logged brief reference, and the seat launch guard
  (`agent_launch.check`) refuses a workspace whose shepherd runtime policy is not Claude.
- **Budget.** There is no daily budget governor on `main` (`docs/site/remote.md`, Limits); the
  shepherd seat is bound by the limits that exist for any Claude seat today: the memory floor,
  `host.seats`, the MCP gate and the logged-brief check. The budget governor is out of scope.
- **Mapping of the issue's action names.** `checks_failed` is the `ci_red` state; `comments`
  is `changes_requested` and `threads_unanswered`. `approved` is never dispatched: the merge
  policy and `wuwei merge` stay with the planner and the owner.
- **Thread file path.** The review-thread GraphQL query gains the thread `path` field so a
  summary can name the file; threads without it summarise without the path.
- **Summary format.** Full references (`PR owner/repo#12`), not `PR #12`, because a workspace
  can own PRs in several repositories; the DM fallback line uses the number only.
- **Dry-run workspace.** The orchestrator notes name none; the reproduction used the existing
  watch test fixture in a scratch directory, read-only.
- **Webhooks.** None in this version (spec 15.2 keeps the option).
