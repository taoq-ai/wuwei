# Implementation Plan: a held draft names its rule and id, the owner approves it on a card, and the approved draft goes out through the same MCP tool

**Branch**: `493-draft-card` | **Date**: 2026-10-04 | **Spec**: `spec.md` | **Issue**: #493

## Summary

The rule travels in the tier reason: `classify` reports it through an optional out-list,
`check_tier` appends it to `APPROVAL_REQUIRED`, and the callers that compared the reason for
equality compare by prefix. Both draft producers (the MCP guard and the port wrapper) store
the held call through one new `drafts.hold`, which returns the #362 shaped reason. The card is
`drafts show <id> --widget`, built with the #359 `decision.widget`, and the existing #357
gate mechanism (question guard, `record_gate`, `protect_state._GATE_EDITS`) is extended from
`D-n` to draft ids. `drafts approve` records an allowance (status `approved` on the draft row)
for MCP and adapter `none` drafts instead of replaying an adapter, and the MCP guard spends it
once through `drafts.spend` at the point the tier would refuse. The host confirmation runs
only under strict.

## Technical Context

Python 3.11+, stdlib only (`hashlib`, `re`, `json`, `datetime` through `workspace.now`).
Tests: pytest, in process, `tmp_path` workspaces. Fixtures to reuse: `configured` and
`payload()` in `tests/test_outward.py`; `root`, `sink`, `port`, `queued()` and `edit_to()`
in `tests/test_drafts.py`; `gated()`, `edit()` and `asked_decision()` in
`tests/test_owner_edits.py`; `gate()` and `planner` in `tests/test_decision.py`;
`test_hook_imports_no_unused_stdlib` in `tests/test_hooks.py`. Neutral channel ids (`C1`,
`C9`) and names (`dev`) only.

## Constitution Check

- I stdlib only: yes; no new dependency.
- II exits: the guard keeps 0, 1 and 2; a failed draft store or a raced allowance is exit 2
  through the guard's existing `except` and reason; `drafts show` exits 1 for an unknown or
  decided id and 2 on unreadable state.
- III one behaviour, one function: the rule in `outward.classify`; storing a held call and
  its reason in `drafts.hold`; spending an allowance in `drafts.spend`; the card in
  `drafts.widget`; the allowance record in `drafts.approve`.
- IV test first: `tasks.md` orders each test before its code.
- V ponytail: no new state key, no new module, no new event family (`draft.approved` joins
  the existing `draft.*` producer row), one config key the issue names. The rule rides the
  existing reason string instead of a new return type, so `classify`'s tests stay unchanged.
- VII security: the allowance lives in the producer-owned `drafts` key (`state set` and
  `event` already refuse it and `draft.*`); only `drafts approve` writes `approved`, and only
  the owner or the planner after a card answer reaches it (`protect_state`, records floor).
  `security.outbound` runs before classify and before the allowance, so a canary never passes.
- Hook latency (#346): `wuwei.drafts` and `hashlib` are imported only inside the held-call
  branch; a call `classify` sends imports nothing new (test T021).

## Contracts

### Reason (FR-002, FR-003)

```
outward: draft <id>: <rule>: <evidence>; the owner decides: bin/wuwei drafts show <id> --widget
posture: outward = block (owner-only action; no setting lowers it)
```

The second line is added by the hook as today. `<evidence>` never contains `; `, so
`wuwei why` (`commands/why.py:192`, unchanged) prints `rule: outward: draft <id>: <rule>:
<evidence>` and `fix: the owner decides: bin/wuwei drafts show <id> --widget`.

### Rules (FR-001), one per `classify` draft site in `cli/wuwei/outward.py`

| Line today | Condition | `why` entry |
|---|---|---|
| 301 | `WUWEI_SEAT_ROLE == 'shepherd'` | `headless seat: a headless shepherd seat posts drafts only` |
| 313 | nested `draft` field disagrees | `approval tier unclassified for <a>: nested draft fields disagree` |
| 325 | keyword or pattern hit | `approval tier sensitive|commitment|disagreement for <a>: outbound.<key>` (the key that matched; keywords and `sensitive_patterns` are `sensitive`) |
| 330 | `is_dm`, `channel_type` `im`/`mpim`, or a `D`/`U` channel | `approval tier direct message for <a>: every direct message drafts` |
| 330 | other audience flag, other `channel_type`, `external_channels` | `approval tier external for <a>: shared, connected, client or outbound.external_channels` |
| 344 | first recipient `_internal` rejects | `unknown mention @<name>: not an internal person in outbound.people` (an email stays as written, no `@` added) |
| 347 | `recipient_org` outside `code_host_orgs` | `approval tier external for <a>: recipient_org not in outbound.code_host_orgs` |
| 349 | docs kind not in `docs.auto` | `approval tier docs for <a>: kind not in docs.auto` |
| 353 | tracker write not auto | `approval tier tracker for <a>: category not in tracker.auto, or the board is outside outbound.code_host_orgs` |
| 359 | chat thread | `approval tier thread for <a>: chat threads draft until their participants are known` |
| 363 | `_pr_context` exit 1 | `approval tier external for <a>: not a measured team pull request` |
| 367 | chat or slack, destination missing or not a work channel | `unknown destination <c>: not in outbound.work_channels` (`<c>` the first destination not listed, or `none` when the call names none) |
| 367 | any other kind reaching this branch | `approval tier unclassified for <a>: no auto-send rule for channel <kind>` |
| 378 | review gate exit 1 | `approval tier review gate for <a>: <gate reason up to its first "; ">` |
| 390 | no safe form, `review_match` set | `approval tier review ping for <a>: the mentions are not the requested reviewers` |
| 390 | no safe form, chat or slack, text has `review` | `review ping without a code-host link: the review request form with the PR link goes to shepherd.review_channel` |
| 390 | no safe form otherwise | `approval tier unclassified for <a>: not an acknowledgement, status, technical or mechanical reply` |
| 404 | commit unresolved, exit 1 | `approval tier unresolved commit for <a>: <sha> is in no configured repository` |

`<a>` is `voice.audience(destinations[0] if destinations else kind, config)`, imported lazily
inside the helper. Exit 2 returns (`_pr_context`, review gate, `vcs.resolve`) add no entry.

### Card (FR-004)

`bin/wuwei drafts show <id> --widget` prints `json.dumps([widget], indent=2)` where `widget`
is `decision.widget(question, 'Draft', options, f'bin/wuwei drafts approve {id}')`:

- `question`: `f"{id}: send this to {destination} through {tool or adapter}? Rule: {rule}.\n\n{text}"`,
  `rule` being `tier_reason` with the `APPROVAL_REQUIRED + ': '` prefix removed.
- options, the recommended first with ` (Recommended)` appended to its label:
  - `Send now`: "Send the text as it is." plus, for an allowance row, "The seat repeats its
    call and it goes out once." or, for an adapter row, "It goes out through the <adapter>
    adapter." Plus, when the rule starts with `unknown destination` or `unknown mention` and
    `config['outbound'].get('learn', 'off') != 'off'`, "Then run bin/wuwei outbound learn to
    record <channel or @name> for later sends."
  - `Send with an edit`: "I ask you for the new text, write it to a file and run bin/wuwei
    drafts approve <id> --file <file>."
  - `Keep as draft`: "Nothing is sent; it stays in bin/wuwei drafts."
  - `Drop`: "Nothing is sent: bin/wuwei drafts drop <id>."
- Recommended: `Keep as draft` when the rule starts with `approval tier` and
  `workspace.posture(config)[0] == 'strict'`; otherwise `Send now`.

## Changes

### `cli/wuwei/outward.py` (FR-001, FR-002)

- `classify(text, root, config, context=None, *, kind='chat', port=False, why=None)`: a local
  `held(rule)` appends to `why` when it is a list and returns `(FINDINGS, 'draft')`; every
  draft site in the table above returns through it. Split the line 322-325 test so the
  matched key is known (loop over `sensitive_keywords`, then the three pattern keys). Find the
  first non-internal recipient with `next(...)` instead of `any(...)` at 342. Return values
  are unchanged, so every existing `classify` test stays green.
- `check_tier`: pass `why = []`; on `decision == 'draft'` return `(code, f'{APPROVAL_REQUIRED}:
  {why[0]}' if why else APPROVAL_REQUIRED)`.
- `check_call` (413): `draft = result[0] == FINDINGS and result[1].startswith(APPROVAL_REQUIRED)`.

### `cli/wuwei/drafts.py` (FR-003, FR-004, FR-007, FR-008, FR-009, FR-010)

- `TOOL = r'[A-Za-z0-9_.-]+'` and `ANSWERS = ('Send now', 'Send with an edit')`. Built: TOOL
  is wider than the `_unmatched` name rule because a configured `outward.tool_patterns`
  rule may match a tool name without the `mcp__` prefix (`test_configured_matching`).
- `destination(inputs, channel, operation)`: the expression now inline in `create`
  (lines 48-53), extracted unchanged; `create` calls it.
- `create(..., tool=None)`: a tool row has `operation == 'tool'`, `adapter == 'mcp'` and
  `tool` matching `TOOL`; other rows validate against `OPERATIONS` as today.
- `read`: accept a tool row (`operation == 'tool'`, `adapter == 'mcp'`, `tool` full-matching
  `TOOL`); add status `approved`; apply the send-record checks to `approved` too; for
  `approved` also require `answer in ANSWERS`, `text_sha256` of 64 hex and `expires` a string
  `datetime.fromisoformat` reads.
- `reason(draft_id, tier_reason)`: the contract string.
- `hold(root, config, channel, operation, adapter, inputs, tier_reason, tool=None) -> str`:
  for a tool, reuse a `pending` row with the same `tool` and the same inputs (with `is_dm`
  removed, as `create` stores them); else `create`. Return `reason(id, tier_reason)`.
- `spend(root, tool, channel, inputs) -> str | None`: the `approved` rows whose `tool` is this
  tool or absent (adapter `none`), whose destination equals `destination(inputs without
  is_dm, channel, 'tool')`, and whose `expires` is after `workspace.now()`; none, return None
  before importing `hashlib`. Otherwise hash `'\n'.join(outward._text(inputs)[0])`; on a match,
  `state._write_state(update, root, reserved=False, kind='draft.sent', payload={'id': id,
  'tool': tool})` where `update` re-reads the row, raises `ValueError(f'drafts: allowance
  changed; {RACE}')` unless it is still `approved`, and sets `status='sent'`, `closed=now`.
  Return the id.
- `widget(row, config) -> dict`: the card contract (lazy `from wuwei import decision`).
- `_edit(inputs, root, source=None)`: with `source`, read that file instead of writing a temp
  file and running the editor; the rest (single field or JSON, trailing newline, validation)
  is shared.
- `approve(root, draft_id, *, edit=False, source=None)`:
  - `allowance = row['adapter'] in ('mcp', 'none')`. The adapter-changed check runs for every
    row except `mcp`; `registry.load` and the operation lookup run only when not allowance.
  - `_edit` runs when `edit or source`.
  - Lint as today (security, `check_lint`, `humanize_lint`), with `{row['channel']}`.
  - `_host_confirm` only when `workspace.posture(config)[0] == 'strict'`, with today's
    digest, prompt and messages.
  - `answer = 'Send with an edit' if edit or source else 'Send now'`;
    `text_sha256 = sha256(text.encode()).hexdigest()`; both are added to the claim update on
    both paths.
  - Allowance: the claim sets `status='approved'`, the existing final fields, `answer`,
    `text_sha256`, `decided`, and `expires = (now + timedelta(seconds=config['outward']
    ['draft_ttl'])).isoformat()`, event `draft.approved` `{id, tool}`, and returns
    `Result(0, reason=f'drafts: {id} approved; repeat the same call to {destination} within
    {ttl} seconds; it passes once')`. Nothing is sent.
  - Adapter path: unchanged after the claim.

### `cli/wuwei/guards/outward.py` (FR-003, FR-010)

Replace the rewrite at lines 133-135 only:

```
if result[0] == FINDINGS and result[1].startswith(outward.APPROVAL_REQUIRED):
    from wuwei import drafts  # Only a held call pays for the queue (#346).
    channel = next(iter(channels))
    if drafts.spend(root, tool, channel, inputs):
        return CLEAN, ''
    return FINDINGS, drafts.hold(root, config, channel, 'tool', 'mcp', inputs, result[1], tool=tool)
```

`inputs` is the `is_dm` augmented dict already built at 129-131. Do not touch `_unmatched`,
`tool_kind`, the word lists or the channel resolution at 98-128 (#492 edits them in parallel).

### `cli/wuwei/registry.py` (FR-003)

`outward_operation` (187-192): compare by prefix and set `reason = drafts.hold(root, config,
kind, operation.__name__, operation.__module__.rsplit('.', 1)[-1], inputs, reason)`.

### Callers that read the stored draft id from a port reason

- `cli/wuwei/docs.py:199`: `result.reason.startswith('outward: draft ')`.
- `cli/wuwei/tracker.py:124` and `:265`: `re.search(r'outward: draft (draft-[0-9a-f]+)', ...)`.
- `cli/wuwei/watch.py:148`: `result.reason.startswith('outward: draft ')`.

### `cli/wuwei/commands/drafts.py` (FR-004, FR-009)

- `show` subparser: `id`, `--widget`. Without `--widget` print the row as JSON; with it, the
  widget list. An unknown or decided id prints the `_pending` message to stderr and exits 1.
- `approve`: `--file` in a mutually exclusive group with `--edit`; pass `source=args.file`.

### `cli/wuwei/commands/__init__.py`, `cli/wuwei/guide.py`

`'drafts show'` joins `READ_ONLY`; `'drafts show <id> --widget'` joins `guide.WIDGETS`.

### `cli/wuwei/guards/decision.py` (FR-005)

- `check_question`: when the text has no `D-n`/`C-n` and contains `draft-`, find the cited
  ids with `(?<![\w-])draft-[0-9a-f]{32}(?![\w-])`; if every one is a
  pending row today (lazy `from wuwei import drafts, state`), accept the question; otherwise
  `(1, 'draft <ids> not pending today; bin/wuwei drafts lists the queue')`.
- `record_gate`: when the header is `Draft`, add every cited pending draft id to `topics`.

### `cli/wuwei/guards/protect_state.py` (FR-006)

- `_GATE_EDITS` gains `('drafts', 'approve')` and `('drafts', 'drop')`.
- In `_owner_action` (231-234): the id regex becomes `D-[1-9][0-9]*|draft-[0-9a-f]{32}` and
  the group tuple `('mcp', 'decide', 'drafts')`. Strict, a seat, another session and an
  unasked id keep today's refusals.

### `cli/wuwei/workspace.py`, `cli/wuwei/commands/event.py`, template (FR-011)

- `SCHEMA['outward']['draft_ttl'] = (int, 3600, 60)`; `CONFIG_CACHE_VERSION` 6 to 7.
- `EVENT_PRODUCERS` `draft.*` actions gain `approved`.
- `templates/workspace/config.toml` `[outward]`: `# draft_ttl = 3600 # Seconds an approved
  draft's tool call may repeat, once.`

### Docs (FR-013)

- `docs/site/concepts.md`: a short "Drafts and cards" section (not glossary entries: the
  glossary terms are pinned by the term-link test) defining draft, rule, card and allowance; the owner-only paragraph (line 184) adds that outside strict the planner records
  a draft it asked you on a card with `wuwei drafts approve` or `drafts drop`.
- `docs/site/daily.md`: one paragraph near line 296: a draft is one card away from being sent.
- `docs/site/security.md:63`: replace the last sentence with the floor and the card as the way,
  and the one-use allowance for the seat's tool. Built: the page says "You decide", because
  the site pages address the reader and `test_pages_address_the_reader` (#362) refuses "the
  owner".
- `docs/site/configuration.md`: one `outward.draft_ttl` row beside `outward.humanize`.

### Tests that change with the new contract

- `tests/test_outward.py`: `test_send_or_draft` (130) and `test_recorded_server_tools` (859)
  assert `outward: draft ` and the widget command instead of the old lines; the
  `'stored draft'` assertion (555) becomes `'outward: draft '`.
- `tests/test_drafts.py`: the `'stored draft'` assertion (527) as above; tests that rely on
  the y/N prompt (`test_approve_without_terminal_is_owner_action`,
  `test_approve_declined_digest_sends_nothing`, `test_approve_digest_covers_id_and_final_text`
  and any other that monkeypatches `_host_confirm` to decline or record) set
  `[security] posture = "strict"`; tests that approve an adapter `none` row expecting a
  replay now expect `approved`.

## What must not change

- `classify`'s return values and every existing `classify` table test.
- Security before tier: `security.outbound` stays first in `check_tier`; the allowance is
  only spent where the tier would refuse.
- The adapter replay path of `drafts approve` after the claim, the drop path, and `pr act`'s
  own draft creation (`pr_actions.py:422-447`).
- `outward.check_tier` stays owner-only (`guards.OWNER_ONLY`); no posture lowers it.
- `guards/outward.py` outside lines 133-135, and the hook's posture line.
- No new import on a hook path that holds no draft.

## Project Structure

```
specs/493-draft-card/
  spec.md  plan.md  data-model.md  tasks.md
cli/wuwei/outward.py  drafts.py  registry.py  docs.py  tracker.py  watch.py  workspace.py  guide.py
cli/wuwei/guards/outward.py  decision.py  protect_state.py
cli/wuwei/commands/drafts.py  __init__.py  event.py
templates/workspace/config.toml
docs/site/concepts.md  daily.md  security.md  configuration.md
tests/test_outward.py  test_drafts.py  test_owner_edits.py  test_decision.py  test_hooks.py  test_why.py
```
