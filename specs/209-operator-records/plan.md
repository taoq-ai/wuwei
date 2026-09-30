# Implementation Plan: Records the operator reads are correct

**Branch**: `209-operator-records` | **Date**: 2026-09-30 | **Spec**: `specs/209-operator-records/spec.md`

## Summary

Six small fixes, each at the one function every caller routes through. The reply draft goes
through the existing owner queue producer, briefs stop creating items, the status snapshot
counts real phases, nudges are keyed by their cause so the cause can clear them, the pack
reads state instead of event prose, and discovery intake stops proposing ids nobody can
admit. No new module, no new config key, no new state key.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in-process through `wuwei.__main__.main` and module calls, fake ports from `tests/fakes`
**Constraints**: three-state exits unchanged; no guard, reservation or producer allowlist loosened; no network

## Constitution Check

- One behaviour, one function: every change is inside the existing producer or reader (`drafts.create`, `brief.write`, `status.snapshot`, `status.attention`, `signal.classify`, `brief_pack._evidence`, `discovery.intake`, `report.build`).
- Test first: each behaviour below has a failing test task before its code task.
- Fail closed: the shared decision helper keeps the report's symlink and duplicate-outcome `ValueError`s, so the pack fails closed the same way.
- Ponytail: reuse `drafts.create`, `drafts.read`, `steward.SAFE_ID`, `state.PHASES`; one new helper only because two readers need the same decision outcomes.

## Changes by file

### 1. `cli/wuwei/pr_actions.py` (rows 32 and nudge clearing)

- `_thread` (lines 393-405): replace the `pr_reply_drafts` read and write with the owner queue.
  - `inputs = {'ref': ref, 'text': reply, 'thread': thread['comments'][0]['id'] if thread else None}` (the same target the send path passes to `obligations.reply`, and the exact signature of the `code_host.comment` port that `drafts.approve` replays).
  - Duplicate check: an existing row in `drafts.read(state.read_state(root))` with `status == 'pending'` and `inputs == inputs` keeps the current `pending ... continue` flow; do not create another.
  - Otherwise `draft_id = drafts.create(root, config, 'code_host', 'comment', config['adapters']['code_host'], inputs, reason)` with `reason = outward.APPROVAL_REQUIRED` for code 1 and `'outward tier unmeasured; reply kept as a draft'` for code 2. Do not put `item` in `inputs` (the port has no such parameter); `drafts.create` links the item from the PR.
  - The printed `draft_reply` action keeps its keys and adds `'draft': draft_id`. Exit codes stay 1 (draft) and 2 (unmeasured tier).
  - Import `drafts` alongside the existing lazy `from wuwei import outward, registry`.
- `observe` (line 138): `event = {'pr': ref, 'tier': 'silent', 'state': current}`. The existing `event.update(tier=..., state=row['state'], ...)` on a tier change still overrides it.

### 2. `cli/wuwei/brief.py` (row 9)

- `write`, inner `update` (lines 238-241): `if role != 'steward' and item in fresh['items']:` then set `fresh['items'][item]['track']` and the worktree. Drop the `setdefault`. The brief file, header and `brief written` event are unchanged. A full-suite probe of this change on a scratch copy passed (only the two tests that need a real git checkout failed, as they do on any non-git copy).

### 3. `cli/wuwei/report.py` (report part of the acceptance)

- New module function `decisions(day, data)`: moves the existing loop from `build` (lines 38-48) verbatim, but keeps pending records too: returns `{id: outcome}` for every `D-*.md` with an `Outcome:` line, then `.update()` from `data['decision_outcomes']`. Keeps the symlink and duplicate-outcome `ValueError`s.
- `build`: answered = the entries whose outcome is not `pending` (case-insensitive), printed exactly as today. Add a `## Merged` section right after `## Outcome`: one line per item with phase `merged`, `- NAME (PR)` or `- NAME` without a PR, `none` when empty. "Open at close", "Parked" and "Carry" logic is unchanged.

### 4. `cli/wuwei/commands/status.py` (row 38 and nudges)

- `snapshot` (lines 103-108): `phases` becomes `{phase: count for phase in state.PHASES if (count := sum(item['phase'] == phase for item in data['items'].values()))}`; delete the counting loop. `run` already prints every entry as `phase count/cap`, so the line needs no change.
- `attention`, before the `if kind in SILENT: continue` check:
  - a `draft.sending`, `draft.sent`, `draft.failed` or `draft.dropped` event pops `('draft.created', payload.get('id'))` (then `draft.failed` goes on to be classified as its own nudge, as today);
  - a `pr.action` event whose `payload.get('state')` is `merged` or `closed` pops `('merge.policy_blocked', payload.get('pr'))`.
- `attention` key selection (lines 77-83): `merge.policy_blocked` joins the `pr.action` branch (key by `payload.get('pr')`); `draft.created` joins the `decision.one_way` branch (key by `payload.get('id', number)`).

### 5. `cli/wuwei/signal.py` (routine events)

- Add to `SILENT`: `plan.approved`, `state.import`, `build.started`, `build.launched`, `build.checked`, `verdict.rejected`.
- `tracker.call` (line 41): silent when `payload.get('exit') == 0 or payload.get('reason') == 'tracker adapter is none'` (the literal `registry.record_none` produces for the tracker); every other tracker failure still nudges.

### 6. `cli/wuwei/brief_pack.py` (row 48)

- Rewrite `_evidence(root, secret)` to read `state.read_state(root)` and `report.decisions(directory, data)`; delete the event loop and the now unused `watch` import.
  - changed: items not in phase `planned`, merged first then by name, as `NAME: phase` plus ` (PR)` when linked;
  - decided: `ID: outcome` for answered decisions;
  - risk: items in `parked` or `escalated` as `NAME: phase`; pending decisions as `ID: pending owner decision`; each owned PR (`raised_prs + claimed_prs`) with an episode in `data['watch']['actions']` as `REF: state: action`;
  - every value goes through `_clean(value, secret)` so escaping and redaction stay.
- `pack` is unchanged: headline stays first risk, else first change; transcripts and metric lines stay.

### 7. `cli/wuwei/discovery.py` (row 45)

- `intake` loop (line 233): also `continue` when `not SAFE_ID.fullmatch(item)`, with `from wuwei.steward import SAFE_ID` imported inside `intake` (`watch` imports `discovery` and `steward` imports `watch`, so a module-level import would cycle). `SAFE_ID` is the same rule `plan._proposal` enforces. The candidate stays in `discovery_candidates` and the `discovery.intake` event; it just never becomes an owner proposal. Safe but incomplete candidates keep the existing owner route.
- `steward.decision_queue` is not changed: its only input of unlintable rows was this producer.

### 8. `docs/site/configuration.md`

- Pack paragraph (around line 114): one sentence that the sections come from the day's items, decision records and owned PRs.
- Nudges paragraph (around line 251): one sentence that routine progress is silent and a nudge clears when its cause clears (draft decided, PR merged).

## Must not change

- `state.STATE_PRODUCERS['pr_reply_drafts']`, the `pr.reply.drafted` entries in `commands/event.py` and `signal.SILENT`: legacy days load and the kinds stay reserved.
- `drafts.create`, `drafts.approve`, `outward.classify`, `obligations.reply` and the send path in `_thread`.
- Exit codes of `pr act`, `status`, `nudges`, `report`, `brief pack`.
- `state.BUILD_PHASES` and the dashboard board (`commands/dashboard.py`, `templates/dashboard.html`).
- Discovery id formats and `plan._proposal` lint.
- Pages: no page kind changes tier.

## Test impact on existing tests (update in the matching test task)

- `tests/test_pr_actions.py`: lines 86, 157, 169 assert `pr_reply_drafts`; switch them to the drafts queue.
- `tests/test_signal_status.py`: the tier table expects `'verdict.rejected': 'nudge'`; it becomes `silent`. `'tracker.call': 'nudge'` with an empty payload stays.
- `tests/test_brief_pack.py`: the fixture feeds the pack through `note` and `decision.decided` events; rebuild it from state items and a decision record so the answer, streak, escaping and metric tests keep their intent.

## Deferred

- Moving an item to `merged` when its PR merges outside WUWEI.
- Admissible ids for PR follow-up discovery sources.
- Reply acknowledgement for unthreaded review or comment drafts sent through `wuwei drafts approve`.
