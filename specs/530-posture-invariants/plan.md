# Implementation Plan: The autonomy principle, the posture sweep, and the invariant table with its exhaustive test

**Branch**: `530-posture-invariants` | **Spec**: `spec.md`

## Summary

One shared spot carries the runtime change: `hook.posture` decides the posture line of every
refusal. Below strict it stops printing `owner-only action; no setting lowers it` for an
owner-only check (the reason already names its card or its fix), except the #524 merge
family; in every posture it labels canary, honeytoken and owner-marker refusals as the
records floor. Four reasons drop an owner-outside alternative where a seat path exists. The
rest is text (constitution, design 9.1 and a new 9.2 invariant table, the security page and
four lines that still say owner-only actions always refuse) and one new test file,
`tests/test_invariants.py`, that walks the reason corpus and the product of the seven
dimensions against the real rules.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. In-process tests only. Fixtures and helpers to
reuse (import them, do not copy them): `tests/test_reasons.py` (`reasons`, `_sources`, the
AST corpus collector), `tests/test_posture.py` (`fixed`, `guarded`), `tests/test_grants.py`
(`CONFIG`, `DEPLOY`, `run`, the `root` setup with `fakes.integrity.seed`),
`tests/test_outward.py` (`configured`, `payload`), `tests/test_decision.py` (`planner`,
`pending_draft`, `draft_question`), `tests/test_parser_warns.py` (`workspace`, `configure`,
`hook`), `tests/test_pr_guards.py` and `tests/test_commit_push.py` (fakes for a push and a
PR create with evidence). If a helper is a pytest fixture, build the walk's own module-level
fixture on the same files (`fakes/`) rather than calling the fixture function.

## Constitution Check

- Exits stay 0/1/2; levels are unchanged, so nothing that blocked now passes and nothing that
  passed now blocks (FR-010). Pass.
- One behaviour, one function: the posture line is decided only in `hook.posture`; the
  invariants are checked only in `tests/test_invariants.py`. Pass.
- No new config key, state key, event kind or posture level. Pass.
- Security: the records floor, the grant card, the merge family and every strict refusal are
  untouched; only line text changes. Pass.
- Test first: every behaviour below has its test task before its implementation task.

## Changes

### `cli/wuwei/guards/__init__.py`

Add beside `RAISE` (`:56`), no other change (`OWNER_ONLY` and `level` stay):

```python
# #530: owner-only until #524 makes merging grantable; listed in design 9.2.
MERGE = ('merge policy', 'admin merge', 'PR approval', 'branch protection',
         'a shepherd seat never merges')
# #530: canary and honeytoken egress and owner markers are the records floor.
RECORDS_FLOOR = ('outward: security.', 'owner disposition markers must be posted by the owner')
```

The `MERGE` prefixes are the reasons of `guards/pr.py:29`, `:33`, `:280`, `:299`, `:364`,
`:372` and `:387`. `RECORDS_FLOOR` matches `security.outbound` (`security.py:122`, reached
through `outward.check_tier` and `security.gh_outbound`) and the marker refusals
(`security.py:238`, `:273`, `guards/outward.py:121`).

### `cli/wuwei/commands/hook.py`: `posture(payload, refusals, root)`

Import `MERGE` and `RECORDS_FLOOR` with `NO_REVIEWER, RAISE, level` (`:254`). Right after
`guard, area, decided, line = level(check, levels)` (`:278`), before the existing `RAISE`
branch:

```python
if reason.startswith(RECORDS_FLOOR):
    line = 'posture: records = block (floor; no setting lowers it)'
elif line.endswith('(owner-only action; no setting lowers it)') and name != 'strict' \
        and not reason.startswith(MERGE):
    line = ''  # #530: below strict an owner-only refusal names its card or its fix
```

Everything after it is unchanged: the `RAISE`/`NO_REVIEWER` relevelling to `publish` sets
its own line; `publish: ` and `NO_REVIEWER` still clear the line; the held-draft line
(`outward: draft `) still replaces it; `UNPARSED`, `WORKSPACE_ROOT`, `UNKNOWN_GIT` and the
opaque rule are untouched. `decided` is not touched, so owner-only refusals still block.

### Reason text (FR-004)

- `cli/wuwei/guards/deploy.py:369`: `f'deploy: could not inspect: {exc}; write it as plain
  literal commands; a publish step then asks the owner on a card'`.
- `cli/wuwei/grants.py:134-136`: `f'publish: {command} {tail}; name the repository with -R
  <org>/<repo> or run it from a configured repository so the owner can decide on a card'`.
- `cli/wuwei/guards/commit_push.py:411`: `'changing Git hook configuration is refused; read it
  with git config --get; WUWEI\'s hooks stay as bin/wuwei worktree add set them'`.
- `cli/wuwei/guards/commit_push.py:424`: `'unsupported GIT_* override; remove it from the
  command'`.

Each keeps a next step for `tests/test_reasons.py` (`NEXT_STEP`) and no pronoun. Grep the
tests for the old texts and update the assertions that pin them.

### Text that states the old rule

- `cli/wuwei/commands/config.py:94-95` (`config check`): `'  owner-only actions ask on a card
  below strict (deploys, releases, approve-tier messages); merges and approvals stay
  owner-only; records always block'`. Update `tests/test_posture.py:91`.
- `cli/wuwei/commands/next.py:14-20`, the `observe` and `guarded` orientation strings: replace
  "Records ... and owner-only actions ... still refuse" with "Records still refuse;
  deploys, releases and approve-tier messages ask on a card; merges and approvals stay
  owner-only". Keep each string's other sentences.
- `docs/site/concepts.md:163`, `docs/site/daily.md:186-188`: the same rule in one sentence
  each.
- `cli/wuwei/guide.py:85-87` (the `Floors in every posture` line, printed by `wuwei guide`
  and copied between the markers of `docs/site/agent.md:84`, pinned by
  `tests/test_docs.py::test_agent_guide_ships_and_is_linked`): "Floors in every posture:
  records block. Below strict an owner-only action asks the owner on a card the reason
  names; merges and approvals stay owner-only. A refusal names its reason and the accepted
  form, and a levelled one ends with a `posture:` line: use that form, never a way around
  it." Then copy the new `guide.text()` into `docs/site/agent.md` between the markers.
- `docs/site/reference.md:370`: the sentence listing the `(owner-only action; no setting
  lowers it)` line: it now appears only under strict, and for the merge family below
  strict; canary, honeytoken and owner-marker refusals carry the records line.

### `.specify/memory/constitution.md`

- Principle VII, replace the last sentence with: "Autonomy (owner, 2026-10-05, #530): under
  `observe` and `guarded` a guard is a warning or a card, never a wall, with one floor:
  records are written by the workflow and answered by the owner. A refusal that names the
  plain form the seat runs itself is coaching, not a wall. Under `strict`, refusals stay. A
  merge happens only through the merge policy, never by approval or override; an owner-only
  action runs only on the owner's recorded answer (design spec 4.6, 4.7 and 9.2)."
- Workflow, new bullet: "Any item that adds or changes a guard or decision rule adds its
  invariant to the design spec 9.2 table and to `tests/test_invariants.py`, or the review
  refuses it (#530)."
- Version 1.5.0, Last Amended 2026-10-05.

### `docs/specs/2026-09-24-wuwei-design.md`

- 9.1, the paragraph before the posture table: add the principle in two sentences (the same
  words as the constitution). In the table, the `publish` row's guarded cell stays `block`;
  add one sentence under the table: "Below strict a `block` is a card (deploy, release,
  publish, evidence; merge with #524) or a fix the seat runs; only `records` is a wall."
- Rewrite "Floors no posture and no override lowers:" as one floor: `records` (with canary,
  honeytoken and owner markers), plus "Owner-only actions ask on a card below strict" (the
  #478 grant text and the #530 PR raise text kept, shortened), plus the MCP bullet
  unchanged. Keep it short and plain.
- New `### 9.2 Safety invariants (owner, 2026-10-05, #530)`, before `## 10. Testing`: one
  sentence (the hooks are the runtime monitor; this table is the property list they are
  checked against; `tests/test_invariants.py` checks every row on every case), then the
  table: columns `Id | Invariant | Checked by | Notes`, rows I1 to I10 from spec.md. Notes
  carry: I1 the exempt rows (heartbeat probe, the owner's Keep answer, owner-written block
  rows, a broken config is records) and the owned rows (#524 merge family; #529 config and
  integrity re-confirmation through the card); I3 "#524: asserted today as gh pr merge
  refused in every posture"; I8 "#529 extends it to config set". Last line: "A later item
  that adds a rule adds its row here and its check to `tests/test_invariants.py`."

### `docs/site/security.md:42-58`

Rewrite the paragraph and the floors list from the principle, as in design 9.1 (same table
values; the floors become records, owner-only actions ask on a card below strict, MCP).
`:73` (`guarded`): "Records block; publishing asks on a card or names the fix; integrity
blocks; seat launches, outward text and MCP findings warn."

### `tests/test_invariants.py` (new)

Structure (stdlib plus pytest; no new helper module):

1. `WALL = re.compile(r'no setting lowers it|host terminal|ask the owner to|only the owner|by hand')`
   and `CARD = re.compile(r'bin/wuwei (?:decision show D-|drafts show draft-)')`.
   `wall(reason, line)` is `not CARD.search(reason) and bool(WALL.search(reason + '\n' + line))`.
2. Reason-corpus walk (I1, User Story 1). Sources and the guard check each maps to:
   every reason of `cli/wuwei/guards/<m>.py` -> module `m` (check `check`, or the function
   the reason sits in when the module has several, for example `check_tier`,
   `check_question`); and, from modules the guards call, only the reasons inside these
   functions: `grants.py` `gate`, `evidence` -> `deploy`, `commit_push`, `pr`;
   `security.py` `outbound`, `gh_outbound` -> `outward.check_tier`, `pr`; `drafts.py`
   `reason` and `outward.py` `check_tier`, `blocked` -> `outward.check_tier`; `integrity.py`
   `measure` -> `integrity`. Function ranges come from `ast` (`lineno`, `end_lineno`).
   Reasons come from `test_reasons.reasons(source, rel)` (placeholders `{}` stay). For each
   (check, reason) and posture in (observe, guarded): build a stub with
   `test_posture.fixed(module, 1, reason)` and set its `__name__` to the check name, run
   `hook.posture(payload, [(stub, reason, 1)], root)` on a workspace configured for that
   posture, and for every enforced row with `wall(reason, line)` true, require the row to
   be records-area (`level()` area `records`, or `reason` starting with a `RECORDS_FLOOR`
   prefix) or listed in `OWNED` or `EXEMPT`. Both are lists of `(file, substring, note)`
   matched with `in` on the corpus text of that file:
   - `OWNED`: the `MERGE` reasons of `guards/pr.py` -> `#524`; the config reasons
     (`guards/commit_push.py` `config add-repo`, `default_branch`, `empty configured fast
     check`; `guards/pr.py` `API repository default branch is unmeasured`) -> `#529`;
     `integrity.py` `page: plugin integrity` -> `#529` (re-confirmation is a record command
     run after a card answer).
   - `EXEMPT`: `grants.py` heartbeat (`ask the owner to run it in a host terminal`, the
     synthetic probe session), `grants.py` `permissions deny it` (Deferred), `grants.py`
     `kept it owner-only` (the owner's own answer), `guards/stop.py` `day state missing for
     registered planner` (records: state recovery), `guards/deploy.py` `if it publishes,
     run it as a plain literal command` (the unknown-git reason; the corpus text starts
     with `{}` so the stub misses the `UNKNOWN_GIT` prefix, and `hook.posture` warns on it
     below strict, #470).
   Assert the list of unlisted walls is empty and print each as `file:line module: reason |
   line`. When the builder meets a wall not listed here, fix it if a seat path exists
   (reword like FR-004), otherwise add an `OWNED`/`EXEMPT` row and the matching note in
   design 9.2.
3. Product walk (I1 to I10, User Story 2). `DIMENSIONS` is an ordered dict of the seven
   dimensions with the values of FR-006. `walk(root_for)` returns a list of failure
   strings; each invariant is a function `(case, results) -> str | None`; `results` is a
   small object with `functools.cache`d methods keyed by projection:
   - `outward(posture, audience, topic, kind, umbrella, mode)`: one real
     `outward.classify(text, root, config, context, kind=kind, port=(mode == 'adapter'),
     why=why, tool=tool)`, returning `(code, decision, why)`. Config per (posture, umbrella,
     mode) through `workspace.load_config` of a workspace whose `config.toml` sets
     `security.posture`, `outbound.default_tier`, `outward.modes.fixture = <mode>` (send,
     draft, refuse), `outbound.owner.slack = {user = "U0OWNER", dm = "D0OWNER"}`,
     `outbound.channel_classes` (`C0TEAM` team, `C0CO` company, `C0CLIENT` client, `C0PUB`
     public), `outbound.people` (`slack:p-team` team ... `slack:p-public` public),
     `docs.auto = ["report"]`, `tracker.auto` default. Context per kind: chat -> `{'channel':
     <id>}` (owner -> `D0OWNER`); tracker, docs, other -> the text mentions `@p-<class>`
     (owner -> no mention), docs adds `'kind': 'page'` (outside `docs.auto`); tool is
     `mcp__fixture__post_message` unless mode is `adapter` (tool None, port True) or
     `unlisted` (`mcp__other__post_message`). Text per topic: none -> `'Tests passed.'`,
     sensitive -> a `outbound.sensitive_keywords` default word, commitment -> a phrase the
     default `commitment_patterns` match, disagreement -> one the `disagreement_patterns`
     match, thread -> `'Tests passed.'` with `thread_ts` in the chat context. Build each
     config once and keep it in a dict; `classify` reads only its arguments and state.
   - `grant(posture, grant)`: the deploy guard via `test_grants.run(root, DEPLOY)` on a
     workspace per posture with `test_grants.CONFIG`, the state's `grants` rows seeded for
     the grant state (asked: an unanswered row; keep, once, today: an answered row; always:
     a `[grants]` standing line in config) through `state._write_state`, replacing the whole `grants` dict before each call so an earlier grant state never leaks into the next. Returns the exit,
     the reason, and the grant rows and standing lines before and after.
   - `record(posture, grant)`: `decision.record_gate` on a D-n card question from the
     planner (`test_decision.planner` setup) when the grant state is not `none`, then
     `protect_state.check` on `bin/wuwei decide D-<n> once` from the planner and from a seat
     (`agent_id` set). Returns both exits.
   - `merge(posture)`, `marker(posture)`, `evidence(posture)`, `opaque(posture)`: the real
     `pr` guard on `gh pr merge 7 -R fixture-org/app --squash` and `--admin`; the outward
     guard and `pr` guard on a `WUWEI parked ` comment; push and PR create with recorded
     evidence through the hook (530p fixtures); the three opaque read forms through the
     hook (`test_parser_warns` shapes).
   - `card_to_send(posture)`: one held chat message through `guards.outward.check_tier`, its
     draft approved by the planner card path (`draft_question` with `Send now`, then
     `drafts approve` passing `protect_state` from the planner), and the same call returns
     0.
   Invariant checks, each returning a message or None:
   - I1: below strict, `decision == 'block'` only when `mode == 'refuse'`; and below strict
     the grant result is a pass or a refusal whose reason matches `CARD` or names the
     owner's kept answer.
   - I2: `decision == 'draft'` implies `code == 1`; `card_to_send(posture)` is 0.
   - I3: `merge(posture)` refuses both forms with a `MERGE` reason (#524 owns the rest).
   - I4: chat, owner audience: `decision == 'send'`.
   - I5: grant rows' `answered` values and `grants.standing` are the same before and after
     the deploy guard and the record gate, except `spent` on a once row; the shipped
     template (`templates/config.toml` or `workspace.SCHEMA` default) has no standing grant.
   - I6: `marker(posture)` refuses both forms.
   - I7: mode adapter, kind docs or tracker, audience team, topic none: the `docs.auto`
     kind (`report`) and a `tracker.auto` category send; `page` and a category outside it
     are held. With mode `unlisted` (a connector write) and the same text, umbrella send
     sends whatever kind it names (#535).
   - I8: the planner's decide passes only when grant state is not `none` and posture is
     not strict; the seat's never passes.
   - I9: below strict `evidence(posture)` passes for the planner and the builder.
   - I10: below strict `opaque(posture)` passes all three forms.
   Grant expectation for I1/I5 is the table under spec.md "Grant expectation".
   `test_invariants_hold`: `cases = list(itertools.product(*DIMENSIONS.values()))`,
   assert `len(cases) >= 2000`, run `walk`, measure with `time.perf_counter()` around the
   walk only (fixtures built before), assert no failures (message: the first 20 failures,
   each `posture=... audience=... topic=... kind=... grant=... umbrella=... mode=...:
   I<n> <what>`) and elapsed `< 1.0` with a `ponytail:` comment (one wall sample; a
   slower CI host raises it in the latency benchmarks, not here).
   `test_broken_rule_is_caught`: parametrized over the two mutations of spec US2 scenario
   3 (`monkeypatch.setattr(outward, 'DEFAULT_TIERS', (...))`; `monkeypatch.setattr(grants,
   'active', lambda *a: ('today', 'D-1'))`), run `walk`, assert failures exist and the
   first one contains `posture=` and `mode=`.
4. `test_table_matches_the_checks`: the ids in the design 9.2 table (`| I<n> |` rows between
   `### 9.2` and `## 10.`) equal the ids of the invariant functions the walk runs, so a rule
   added to one and not the other fails; and the phrase `Owner-only actions always block`
   appears in neither the design spec nor `docs/site/security.md`.

If the timed walk is over budget on the dev host, call `commit_push.check` and `pr.check` directly for I9 and `hook.posture` with the real guard results for I10 instead of the full in-process hook; never drop a dimension value.

Per-case cost is dictionary lookups; the real calls are bounded by the projections (about
1,000 classify keys per posture, 18 grant keys, 3 per-posture checks each).

## What must not change

- `workspace.POSTURES`, `FLOORS`, `AREA_LEVELS`, `guards.OWNER_ONLY`, `guards.level`, the
  `decided` level of any refusal, the grant card options and rows, the draft queue, the
  opaque rule (#547), the PR raise relevelling (#547), the held-draft line (#526).
- No refusal is added in any posture; the heartbeat probe stays enforced.
- `cli/wuwei/interview.py` (rewritten by #530 part C).

## Files

- Change: `cli/wuwei/guards/__init__.py`, `cli/wuwei/commands/hook.py`,
  `cli/wuwei/guards/deploy.py`, `cli/wuwei/grants.py`, `cli/wuwei/guards/commit_push.py`,
  `cli/wuwei/commands/config.py`, `cli/wuwei/commands/next.py`,
  `.specify/memory/constitution.md`, `docs/specs/2026-09-24-wuwei-design.md`,
  `docs/site/security.md`, `docs/site/concepts.md`, `docs/site/daily.md`,
  `cli/wuwei/guide.py`, `docs/site/agent.md`, `docs/site/reference.md`.
- Update assertions: `tests/test_hooks.py:1267-1320`, `tests/test_posture.py:91`, `:232`,
  `:252`, and any test pinning the four reworded reasons.
- Add: `tests/test_invariants.py`.
