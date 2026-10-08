# Feature Specification: the internal-state lint applies by kind and audience

**Feature Branch**: `533-lint-audience`

**Created**: 2026-10-05

**Status**: Draft

**Input**: GitHub issue #533 (remainder after PR #540), "the internal-state lint applies by
kind and audience: never on tracker, docs and code-host writes; a warning on team and company
chat; a hold with a card for client and public". Owner, 2026-10-05, on 0.17.x: a tracker
ticket was refused with `outward: internal state pattern; remove the internal state words
(item ids, phases, file paths) from the message`. A ticket is where item ids, phases and file
paths belong; the rule was written for chat to people outside the team (design 4.3).

PR #540 already shipped: `outward.patterns` is empty by default, the reason names the matched
word and the setting, and a connector learned as draft follows the send umbrella. This
feature is the audience and kind scoping of an owner-configured list.

## Root cause (reproduced on the worktree base, e447ef8, read-only)

Reproduction: a scratch workspace with `outward.patterns = ['\bI-[0-9]+\b',
'[a-z_]+/[a-z_]+\.py']`, `work_channels = ["C1"]`, `external_channels = ["C2"]` and every
other key at its default (profile `strict`, posture `guarded`, autonomy `autonomous`):

- `outward.check_call({'title': ..., 'body': 'Follow-up for I-12 in src/app.py', 'category':
  'progress'}, root, config, {'tracker'}, port=True)` returns `(1, 'outward: internal state
  pattern; remove "i-12" from the message ...')`: the tracker write is refused.
- The same text to `C1` (team) through the chat port is refused the same way.
- The same text to `C2` (client) is held by the tier table with a commitment rule; the reason
  does not name the word.

1. **The pattern check knows no kind or audience.** `lint()` (`cli/wuwei/outward.py:90-143`)
   compiles `outward.patterns` (`:110-111`) and refuses on the first match (`:126-130`).
   `lint()` takes only the text and a channel string, and `check_lint`
   (`cli/wuwei/outward.py:758-774`) calls it for every write: tracker, docs, code host, chat
   and mail alike. `shepherd.raise` calls `lint()` on a PR title and body
   (`cli/wuwei/shepherd.py:314`), and `digest._clean` on owner-only text
   (`cli/wuwei/digest.py:31`).
2. **The port path keeps it a refusal outside strict.** WUWEI's own adapter writes go through
   `registry` (`cli/wuwei/registry.py:186`, `outward.check_call(..., port=True)`), where the
   lint finding passes through `profile_result` (`cli/wuwei/guards/__init__.py:98-106`), which
   relaxes only `profile = "standard"`; the default profile is `strict`
   (`cli/wuwei/workspace.py:155`). So under the default `guarded` posture a tracker ticket is
   refused, which the autonomy program (#530) forbids outside strict. The hook path relaxes
   the same finding to a `guard.would_refuse` warning under guarded (`commands/hook.py:249`),
   but still applies it to tracker, docs and code-host connector writes.

## User Scenarios and Testing

### User Story 1 - Team records are never linted for internal state (Priority: P1)

The owner keeps an `outward.patterns` list for chat. A seat creates a tracker ticket, writes
a docs page or comments on a PR with item ids and file paths in the body. It goes through:
the patterns never apply to tracker, docs and code-host writes, through WUWEI's adapters or a
connector, in every posture.

**Why this priority**: the owner's report; a ticket was refused.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k internal_state`.

**Acceptance Scenarios**:

1. **Given** `outward.patterns` set and `tracker.auto` holding the category, **When**
   `tracker create` (the port, `check_call(..., {'tracker'}, port=True)`) carries an item id
   and a file path in the body, **Then** it returns `(0, '')` under the default profile
   `strict` and every posture, and no `outward.lint` event is written.
2. **Given** the same, **When** a connector tracker write (`createJiraIssue`), a docs write
   (`create_page`) or a code-host comment goes through the outward hook's `check_lint`,
   **Then** it returns `(0, '')`.
3. **Given** the same patterns, **When** `shepherd` lints a PR title and body that hold an item
   id, **Then** the lint is clean on the patterns (other lint rules unchanged).

### User Story 2 - Team and company chat warns, client and public holds (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outward.py -k internal_state`.

**Acceptance Scenarios**:

1. **Given** `outward.patterns` set, the send umbrella (`default_tier = "send"`) and
   `autonomy.mode = "supervised"`, **When** a seat sends the same text to a team channel
   (`C1` in `work_channels`), **Then** it sends (`check_call` and the hook both pass) and one
   `outward.lint` event is written with the kind and the matched word, and a `warning:` line
   naming the word goes to stderr.
2. **Given** the same, **When** the destination is a client channel (`C2` in
   `external_channels`), **Then** the call is held as a draft (the card) and the reason names
   the audience and the matched word:
   `internal state word "i-12" for the client audience of C2 (outward.patterns), rewrite that line`.
3. **Given** a public channel (`outbound.channel_classes`) or an owner tier row that sends to
   the client channel, **Then** the same hold applies. A `block` row for that party still
   blocks.
4. **Given** the client draft, **When** the owner approves it on the card, **Then** it sends
   (the approval answers the hold) outside strict.
5. **Given** a company audience (an unknown channel) and supervised, **Then** it is a warning
   like the team case, never a refusal or a hold from the lint.

### User Story 3 - Autonomous drops the chat warning (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `autonomy.mode = "autonomous"` (the default), **When** the team chat of Story 2
   runs, **Then** it sends with no `outward.lint` event and no warning line.
2. **Given** autonomous, **When** the destination is a client channel, **Then** it is still
   held with the word named.

### User Story 4 - Strict keeps its refusal (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `security.posture = "strict"`, **When** a team chat carries a matched word,
   **Then** `check_lint` returns exit 1 with
   `outward: internal state word "i-12" in a slack message (outward.patterns); remove it or change the list`.
2. **Given** strict, **When** a tracker write carries the word, **Then** it goes through.

### Edge Cases

- A message only the owner reads (owner DM, mail to the owner only, `remote.dm`, the digest):
  the patterns never apply.
- An invalid pattern in a programmatic config (`patterns = [1]` or `['[']`): a chat or mail
  call fails closed with exit 2 from `check_lint` or `classify`; a tracker, docs or code-host
  write never reads the list.
- A chat call held by the tier for another reason with no client or public reader: the hold
  stands; the lint does not change it.

## Requirements

### Functional Requirements

- **FR-001**: `lint()` no longer checks `outward.patterns`. A shared helper
  `outward.internal_word(text, config)` returns the first matched word (over the same
  normalized views `lint()` uses) or `None`.
- **FR-002**: The patterns apply only to chat and mail kinds (`slack`, `chat`, `mail`, the
  keys of `outward.OWNER`) and never when the owner alone is addressed. Tracker, docs,
  code-host and `other` writes never read them.
- **FR-003**: In `classify` (the tier decision, `check_tier`), a chat or mail call with a
  client or public party and a matched word is held as a draft whose rule names the audience,
  the party and the word, unless the table decided `block`.
- **FR-004**: In `check_lint`, a chat or mail call with a matched word: under posture
  `strict` returns exit 1 with the word named; else under `autonomy.mode = "supervised"`
  records one `outward.lint` event `{kind, word}`, prints a warning line and returns
  `(0, '')`; else (autonomous) returns `(0, '')` silently.
- **FR-005**: `outward.lint` is a reserved event kind (producer `wuwei.outward.check_lint`)
  and a silent signal.
- **FR-006**: Design 4.3 and `docs/site/configuration.md` (`outward.patterns`) state the
  scoping.

### Key Entities

- `outward.lint` event: `{'kind': <slack|chat|mail>, 'word': <matched text>}`, written only
  by `check_lint`.

## Success Criteria

- **SC-001**: The owner's report does not reproduce: a tracker ticket with item ids and file
  paths goes through under every posture and profile.
- **SC-002**: No new refusal under observe or guarded; a client or public reader still gets a
  card naming the word.
- **SC-003**: The full suite passes.

## Assumptions

- A1: "Supervised" (the warning) and "autonomous" (silent) are read from the existing
  `autonomy.mode` key (#530 part A, on main). The acceptance warning event is tested under
  `supervised`; the default `autonomous` drops it, as the item's point 4 says.
- A2: The client and public hold lives in the tier decision (`classify`), not in the lint, so
  one call makes one card, an approved MCP call spends one allowance, and `drafts approve`
  (which re-runs only `check_lint`) sends. "As the tier table decides" is read as: the hold is
  a tier hold, and a table `block` row still wins.
- A3: Under strict posture the team and company finding stays a refusal from `check_lint` (the
  program keeps refusals under strict). A strict client draft approved on the card is then
  refused at send by the lint, as today.
- A4: The audience of the warning is not computed in `check_lint`: client and public readers
  were held by the tier first, so any chat or mail call reaching a send there is team,
  company, or a client message the owner approved.
- A5: In the hook path `check_lint` runs even when `check_tier` held the call, so a held
  supervised call can record an `outward.lint` event; same accepted ceiling as the
  `outward.ai_tells` note in `guards/outward._lint`.
- A6: The digest (`digest._clean`) and `remote.dm` address the owner, so they lose the
  pattern check; internal state is fine for the owner.
- A7: The setup interview question for the umbrella (#527, #530) is not on main; the
  `autonomy.mode` documentation row names the effect instead. Deferred.
- A8: `tests/test_invariants.py` does not exist on the base, so no invariant row is added.

## Deferred

- The setup interview wording for the umbrella and autonomy question (A7).
