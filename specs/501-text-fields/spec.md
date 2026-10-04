# Feature Specification: the outward lint reads text and destinations from any connector payload shape instead of failing closed on unknown fields

**Feature Branch**: `501-text-fields`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #501, "fix(outward): the outward lint reads text and destinations
from any connector payload shape (nested rich text, Jira comment, Notion children, GitHub
body) instead of failing closed on unknown fields". Found by the #492 verify step and
confirmed against the owner's question about Notion, Jira, GitHub and Sentry through MCP:
even with the channel resolved (#492) and the mode `send`, real connectors rarely send.

## Root cause (read and reproduced on main, 6168be8)

Reproduced read-only: a scratch probe outside the repository imports `wuwei.outward` and
calls `_text` on recorded connector shapes, and a scratch pytest file (outside the
repository, reusing the `configured` fixture of `tests/test_outward.py` in its own temporary
workspace) drives the guard through fixture UUID connectors.

| shape | `outward._text` on main | guard outcome on main |
|---|---|---|
| Slack `{channel, text}` | text and channel read | decided by the tier |
| Jira `{issue_key, comment}` | `unsupported input field` | exit 2 with the config-check reason, under the owner's mode `send` |
| Confluence `{pageId, body: {storage: {value}}}` | `expected plain text` | exit 2, config-check reason |
| Notion `{page_id, children: [...rich_text...]}` | `unsupported input field` | exit 2, config-check reason |
| GitHub `{owner, repo, pull_number, body}` | text read, no destination | decided by the tier |
| Sentry `{issue_id, status}` | `unsupported input field` | exit 2, config-check reason, under the `other` class mode `send` |
| mail `{to, subject, body}` | `unsupported input field` | exit 2, config-check reason |
| `tool_input` is a list | `expected input object` | exit 2, config-check reason |

1. **A closed field list.** `cli/wuwei/outward.py:152-184` (`_text`) accepts only
   `TEXT_FIELDS` (line 142) as plain strings (lines 158-159 raise for a non-string, such as
   Confluence's `body` object), the `draft` wrapper, `BOOL_FIELDS`, `recipients`, three
   number keys and `METADATA_FIELDS` (line 144); every other key raises `unsupported input
   field` (line 183). `comment`, `children`, `subject`, `to`, `status`, `name` and `pageId`
   are all unknown.
2. **Every caller turns that into the wrong reason.** `check_send` (line 333), `check_tier`
   (line 512), `check_lint` (line 528), `humanize_lint` (line 77) and the guard
   (`cli/wuwei/guards/outward.py:200`) catch the `ValueError` and print `outward: cannot read
   or validate policy or payload; run bin/wuwei config check`. The config is fine; the payload
   shape is the cause.
3. **No text is "nothing to lint" only under mode send.** `lint` refuses an empty text
   (`cli/wuwei/outward.py:95-96`) and `classify` returns exit 2 for one (line 352); only the
   guard's mode-`send` branch (`cli/wuwei/guards/outward.py:189`) skips the lint for a write
   without text.
4. **A held write without text damages the draft queue.** Reproduced on main: a Sentry
   resolve `{issue_id}` under the owner's mode `draft` is held (exit 1, draft stored with
   `text = ''`), and the next `drafts.read` raises `drafts: invalid record; a WUWEI record
   failed its consistency check`, because `cli/wuwei/drafts.py:34-36` requires a non-empty
   `text`. Every later hold, spend and `drafts` command fails until state is recovered. This
   feature sends more text-less writes down that path, so it is fixed here.

## User Scenarios & Testing

### User Story 1 - A connector write is read whatever its payload shape (Priority: P1)

A seat calls a resolved connector write tool (Jira, Confluence, Notion, GitHub, Sentry, mail,
Slack) with that connector's own payload. The outward checks read every string in the
payload as text (inside nested lists and objects too), skip ids, flags, numbers and
structural keys, and collect the destinations from the known destination keys. No field is a
reason to refuse because its key is unknown.

**Why this priority**: it is the outage: with the channel resolved and mode `send`, a Jira
comment or a Notion append is still refused with a reason that blames the config.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k "corpus or text_fields"`.

**Acceptance Scenarios**:

1. **Given** a Notion append through a docs connector whose nested rich-text block carries a
   sensitive keyword, **When** the outward tier guard runs, **Then** the call is held as a
   draft and the reason names the rule in the #493 shape (`approval tier sensitive for docs:
   outbound.sensitive_keywords`, the draft id and the card command).
2. **Given** a Jira comment `{issue_key, comment}` with plain text through a connector aliased
   to the tracker with the owner's mode `send`, **When** both outward guards run, **Then**
   both return `(0, '')` and the call goes out.
3. **Given** a Sentry resolve `{issue_id, status}` with no text through an `other` connector,
   **When** both outward guards run, **Then** there is no lint finding and the mode decides:
   under the class mode `send` both return `(0, '')`; under the owner's mode `draft` the tier
   guard holds it as a draft and the draft queue stays readable.
4. **Given** the recorded corpus (Slack, Jira, Confluence, Notion, GitHub, Sentry, mail),
   **When** `_text` reads each, **Then** each is read without error, its text is found (none
   for Sentry), its destination is found, and a sensitive keyword placed in its nested text
   is caught by the topic patterns.

### User Story 2 - An unreadable payload says so (Priority: P2)

A tool call whose `tool_input` is not a JSON object (a list, a string, null) is refused with
a reason that names the shape, not the config.

**Why this priority**: the old reason sent the seat and the owner to `config check`, which
finds nothing.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k not_an_object`.

**Acceptance Scenarios**:

1. **Given** a resolved MCP write whose `tool_input` is a list, **When** either outward guard
   runs, **Then** it exits 2 with `outward: tool_input is not an object; got list; pass the
   tool arguments as a JSON object`, and the reason does not contain `config check`.

### User Story 3 - The owner can read what the lint reads (Priority: P3)

`docs/site/security.md` has one paragraph on what the outward lint reads: every string in
the payload except ids, flags, numbers and structural keys; the destination keys; and that a
write without text has nothing to lint while its mode and destination still decide.

**Independent Test**: `python -m pytest -q tests/test_docs.py`.

### Edge Cases

- A payload with no strings outside non-text keys: nothing to lint (`check_lint` is clean);
  `check_send` passes it; `classify` still applies its audience and destination rules, so a
  write that does not send becomes a draft whose text is empty.
- A text key holding an empty string (`{"text": ""}`) is an empty text, not "no text": the
  lint and the tier check still refuse it with exit 2 (`nonempty text required`), so the
  control-plane DM and the ports keep refusing an empty message and store no draft.
- Known policy keys keep their type checks and refusals: the audience flags must be
  booleans, `recipients` a list of non-empty strings, the issue and pull numbers strings or
  integers, `channel` and `channel_id` non-empty strings, the other metadata keys strings,
  null or lists of strings, and `draft` an object at the top level only.
- Hidden text cannot bypass the lint: text in an unknown field is now read, linted and
  classified like any text (the old bypass rows that refused now draft or send on what the
  text says).
- A destination key holding an integer (`pull_number: 7`) gives the destination `"7"`.
- camelCase keys match their snake form (`pageId` is `page_id`, `databaseId` is
  `database_id`).
- The chat rules of `classify` (direct message, external channel, one work channel, review
  channel) keep reading only `channel` and `channel_id`; a recipient, issue key, repository or
  address is never taken for a Slack channel id.

## Requirements

### Functional Requirements

- **FR-001**: `_text` MUST return every string in the payload as text, in sorted key order
  per object and list order per list, nested objects and lists included, except a string
  whose key path holds a non-text key: a metadata key (`METADATA_FIELDS`), an audience flag,
  an issue or pull number key, a destination key, `status`, `type`, `object`, `id`, or a key
  ending in `_id` or `_ids` (after camelCase is folded to snake case).
- **FR-002**: `_text` MUST return as destinations the string and integer values (integers as
  strings, booleans never) whose key path holds a destination key, anywhere in the payload:
  `channel`, `channel_id`, `recipient`, `recipients`, `to`, `issue_key`, `issue_id`,
  `page_id`, `database_id`, `repo`, `pull_number`, ordered by that list.
- **FR-003**: `_text` MUST NOT refuse a field because its key is unknown or because a text key
  holds a list, an object or null; booleans, numbers and null outside destination keys are
  ignored.
- **FR-004**: `_text` MUST keep the type checks of the known policy keys listed under Edge
  Cases, with their current reasons.
- **FR-005**: For a payload `_text` read on main, `_text` MUST return the same texts in the
  same order, so stored drafts keep matching their inputs.
- **FR-006**: `check_lint` MUST return `(0, '')` when the payload has no text at all; the
  guard's mode-`send` special case for that is removed.
- **FR-007**: `classify` MUST accept an empty text and apply its audience and destination
  rules; a non-string text stays exit 2. `check_tier` MUST refuse a payload whose texts are
  present but all blank with exit 2 and the lint's `nonempty text required` reason, before
  `classify`.
- **FR-008**: `classify`'s chat-channel rules MUST read only the `channel` and `channel_id`
  values of the payload and of its `draft` wrapper, in today's order.
- **FR-009**: `drafts.read` MUST accept a draft whose `text` is an empty string; it must still
  be a string equal to the joined text of its inputs.
- **FR-010**: The MCP outward guard MUST refuse a `tool_input` that is not an object with
  exit 2 and `outward: tool_input is not an object; got <type>; pass the tool arguments as
  a JSON object`, after the scope and channel checks and before any policy runs.
- **FR-011**: `docs/site/security.md` MUST say in one paragraph what the outward lint reads.

### Key Entities

- **Text**: the strings `_text` collects; joined with newlines for the lint, the topic
  patterns, the humanize pass and the draft record.
- **Destination**: the values under the destination keys; a held draft's destination is the
  first one (`drafts.destination`, unchanged).

## Success Criteria

- **SC-001**: The seven recorded connector shapes are read without error; each yields its
  text and its destination; a sensitive keyword in each one's nested text is caught.
- **SC-002**: The four acceptance scenarios of the issue pass through the guard functions.
- **SC-003**: The non-object reason does not contain `config check`, and no payload is
  refused because a key is unknown.
- **SC-004**: The full suite passes; the only changed expectations of existing tests are
  the ones the plan lists (bypass rows that pinned "unknown field refuses", the empty-text
  classify rows and the outward guard-mutation probe).

## Assumptions

- The notes name no dry-run workspace; the failure was reproduced in-process against the
  worktree code with fixture shapes and a temporary workspace, nothing written to the
  repository.
- The issue's destination key list gets `issue_id`, because the corpus requires the Sentry
  shape `{issue_id, status}` to have its destination found; `issue_number` stays a number key
  and is not a destination.
- `status`, `type` and `object` are structural (Sentry's `status`, Notion's block `type` and
  `object`), so they are not text. Other enum-like keys (`representation`, `color`) are read
  as text: extra words in the joined text can make a reply draft, never send.
- The `<payload shape>` in the new reason is `got <type>`, the Python type name of the
  decoded `tool_input` (`list`, `str`, `NoneType`); a string is not decoded as JSON, since
  Claude Code delivers `tool_input` already decoded. The reason ends with a next step
  (`pass the tool arguments as a JSON object`) because every reason must name one (#362,
  `tests/test_reasons.py`).
- A non-string scalar under a text key (`{"text": 1}`) is ignored like any number, not
  refused (FR-003); `tests/test_outward.py::test_humanize_lint_gates` changes accordingly.
- Known policy keys keep their checks (FR-004). A Notion `parent` object (create page) still
  refuses as invalid metadata; that shape is outside the issue's corpus and is left for a
  follow-up when a recorded call needs it.
- `classify`'s chat rules stay on `channel` and `channel_id` (FR-008). Widening them to every
  destination would make a recipient a second Slack channel and a repository or issue key
  that starts with `D` or `U` a direct message (`tests/test_outbound.py` pins the recipient
  case).
- `check_lint` keeps linting once per destination, as it does per channel id today; the
  extra destinations only repeat the lint.
- Editing a held draft whose text sits outside the top-level text keys (`Send with an edit`
  on a Jira comment or Notion children) is out of scope; `Send now`, `Keep as draft` and
  `Drop` work.
- Order with #495: #495 edits `classify` and adds `owner_only`, which reads `_text`'s
  destinations plus the recipients. This feature is built after #495 merges; with the wider
  destinations `owner_only` stays correct (every target must be the owner), and a mail `to`
  that is the owner now counts.
