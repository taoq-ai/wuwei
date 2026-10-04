# Implementation Plan: the outward lint reads text and destinations from any connector payload shape

**Branch**: `501-text-fields` | **Spec**: `specs/501-text-fields/spec.md`

## Summary

One shared spot: `outward._text`, which every outward check, the draft queue and the
`outbound tier` command call. Its closed field list becomes a recursive walk over the payload
that collects text and destinations by key, while the type checks of the known policy keys
stay. Around it, small edits at the places that assumed "no text" or "unknown field" was an
error: `check_lint` treats no text as nothing to lint, `classify` accepts an empty text and
keeps its chat rules on channel ids, `check_tier` still refuses a blank text, `drafts.read`
accepts an empty draft text, and the guard names a non-object `tool_input`. No new module, no new import on the hook path
(`re` is already imported in `cli/wuwei/outward.py`).

## Build order

Build after #495 merges (notes: same file, `classify`). Start from the latest main. #495 adds
`owner_only`, which reads `_text`'s destinations plus `recipients` and `recipient`; leave it
as #495 wrote it (the wider destinations keep it correct: every target must be the owner).
#495 also rewrites the direct-message branch of `classify`; apply Design 3 to whatever line
there reads `_, destinations = _text(context)` in `classify` itself, not in `owner_only`.

## Technical Context

Python 3.11+, stdlib only.

Files changed:

- `cli/wuwei/outward.py`: `DESTINATIONS`, `NOT_TEXT`, new `_strings()`, `_text()`,
  `classify()` (two lines), `check_tier()` (one line), `check_lint()` (one line).
- `cli/wuwei/guards/outward.py`: `_check()` (non-object check added, the mode-`send`
  no-text branch removed).
- `cli/wuwei/drafts.py`: `read()` (empty `text` allowed).
- `docs/site/security.md`: one paragraph.
- Tests: `tests/test_outward.py`, `tests/test_outbound.py`, `tests/test_guard_mutation.py`.

## Constitution Check

- I stdlib only: yes; no import added on the hook path.
- II exits: an unreadable payload is exit 2 with its own reason; a known policy key with the
  wrong type stays exit 2 with today's reason; no text is clean for the lint, and the tier or
  mode still decides 0 or 1.
- III one behaviour, one function: reading a payload is `_text` (with `_strings` as its
  walk); every caller keeps calling it.
- IV test first: every behaviour has a failing test task before its implementation task.
- V ponytail: one walk, no per-connector adapters or shape tables in runtime code; the
  corpus lives in the test only.
- VII security: hidden text is now read and linted instead of refused, so a field cannot
  hide text from the lint; the audience flags, recipients and channel ids keep their type
  checks; `classify`'s DM and work-channel rules are unchanged (Design 3).

## Design

### 1. `_text` walks the payload (`cli/wuwei/outward.py`, lines 142-184)

Keep `TEXT_FIELDS`, `METADATA_FIELDS`, `BOOL_FIELDS` and `APPROVAL_REQUIRED` as they are
(`classify` and `drafts._edit` still use `TEXT_FIELDS`). Add:

```python
# #501: destination keys, in the order a draft's destination is picked from them.
DESTINATIONS = ('channel', 'channel_id', 'recipient', 'recipients', 'to', 'issue_key',
                'issue_id', 'page_id', 'database_id', 'repo', 'pull_number')
NOT_TEXT = METADATA_FIELDS | BOOL_FIELDS | {'issue_number', 'status', 'type', 'object'}
```

`_strings(value, key, texts, found, text=True, destination=None)` walks one value:

- `name` is `key` with camelCase folded to snake case
  (`re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', key).lower()`).
- `destination` becomes `name` when `name` is in `DESTINATIONS`; once set it is inherited.
- `text` becomes false, and stays false below, when a destination is set, or `key` or `name`
  is in `NOT_TEXT`, or `name` is `id` or ends with `_id` or `_ids`.
- A dict walks its items in sorted key order; a list walks its items in order with the same
  key; a string or an `int` (never a `bool`) under a destination appends
  `(DESTINATIONS.index(destination), str(value))` to `found`; any other string is appended
  to `texts` when `text` is true; everything else is ignored.

`_text(inputs)` (drop the `nested` keyword; it is internal and only `_text` passes it):

1. Not a dict: raise as today (line 154).
2. `nested = inputs.get('draft', {})`; if it is not a dict, or it has a `draft` key, raise
   `unsupported input field` as today.
3. For each `(key, value)` of `inputs` and of `nested`, run today's checks for
   `BOOL_FIELDS`, `recipients`, `issue_number`/`pull_number`/`thread` and `METADATA_FIELDS`
   (including the non-empty string check for `channel` and `channel_id`), with today's
   messages. Drop the `TEXT_FIELDS` string check and the final `unsupported input field`
   branch.
4. `_strings(inputs, '', texts, found)`; return `texts` and the values of `found` stably
   sorted by their index.

Why this keeps FR-005: a payload main accepted holds only text keys (strings), the `draft`
wrapper, audience flags, `recipients`, number keys and metadata keys. The walk reads the
same text keys in the same sorted order (the wrapper's texts at the `draft` position, as
the recursion did), and every other one of those keys is in `NOT_TEXT` or `DESTINATIONS`.

Destinations widen from `channel`/`channel_id` to the whole `DESTINATIONS` list. Callers:
`drafts.destination` takes the first (a held Jira comment now names its issue key, a GitHub
comment its repository); `check_lint` lints once per destination as it does per channel id
(harmless repeats); `classify` no longer uses them for its chat rules (Design 3);
`commands/outbound.py` and `humanize_lint` read only the texts.

### 2. No text is nothing to lint (`check_lint`, line 515; guard line 189)

In `check_lint`, after the channel-count check: `if not texts: return CLEAN, ''`. "No text"
is an empty list: `{"text": ""}` gives `['']`, so the lint still refuses an empty message
from the control-plane DM (`remote.dm`) and the ports.

Delete the guard branch `elif found == 'send' and not outward._text(inputs)[0]: result =
(CLEAN, '')` in `cli/wuwei/guards/outward.py` (lines 189-190): the lint guard now reaches
`check_lint`, which returns the same result, and `humanize_lint` is clean on no text.

### 3. `classify` (line 336)

- Line 352: `if not isinstance(text, str) or not isinstance(kind, str): return UNRUN,
  'draft'` (drop `not text.strip()`). An empty text gets the audience and destination
  rules; with no text the acknowledgement forms never match, so it drafts unless a docs,
  tracker-port or code-host rule sends it.
- `check_tier` (line 493), after the channel-count check: `if texts and not text.strip():
  return UNRUN, 'outward: nonempty text required; pass the message text'` (the lint's
  reason). Without it a port call with `text=''` (`chat.post('C2', '')`) would now be held
  as an empty draft instead of refused; `tests/test_drafts.py::
  test_invalid_call_does_not_create_draft[empty]` pins the refusal.
- Line 355: keep `_text(context)` for its checks, and read the chat channel ids as before
  the change:
  `destinations = [part[key] for part in (context, context.get('draft', {})) for key in
  ('channel', 'channel_id') if key in part]`. This is exactly the old list (sorted top-level
  keys put `channel`, `channel_id`, then the wrapper's). The DM, external-channel,
  review-channel and one-work-channel rules keep reading only channel ids.

### 4. An empty draft text is a valid record (`drafts.read`, `cli/wuwei/drafts.py` line 34)

Take `'text'` out of the non-empty field tuple and add `or not isinstance(row.get('text'),
str)`. The existing equality check (line 39) still ties `text` to the inputs. `approve`,
`spend` and the card already work with an empty text once `check_lint` is clean on it.

### 5. A non-object `tool_input` (`_check`, `cli/wuwei/guards/outward.py` line 177)

Replace `inputs = payload['tool_input']` with:

```python
inputs = payload.get('tool_input')
if not isinstance(inputs, dict):
    return UNRUN, (f'outward: tool_input is not an object; got {type(inputs).__name__}; '
                   'pass the tool arguments as a JSON object')
```

The trailing next step is required: `tests/test_reasons.py::test_every_reason_names_a_next_step`
fails on a reason without one.

It sits after the scope and channel checks, so reads, native tools and calls outside a
workspace still return 0 before the payload is looked at, and before the `is_dm` merge and
every policy.

### 6. Docs (`docs/site/security.md`)

One paragraph after the connector paragraph (line 63): the outward lint reads every string
in the tool's input, nested lists and objects included, except ids (`id`, `*_id`), flags,
numbers and structural keys (`status`, `type`, `object`, the metadata keys); the
destinations come from `channel`, `channel_id`, `recipient`, `recipients`, `to`,
`issue_key`, `issue_id`, `page_id`, `database_id`, `repo` and `pull_number`; an unknown
field is read, never a reason to refuse; a write with no text has nothing to lint and its
mode and destination decide; a `tool_input` that is not an object is refused with that
reason. Plain words, no em-dashes.

## Existing tests whose expectations change

Most are bypass rows that pinned "unknown field refuses"; the field is now read or ignored,
so the result follows what the text and the destination say. The rows in
`test_routing_and_bypass_table` replace the whole `tool_input`, so they carry no channel and
draft with `unknown destination none` once they are read.

- `tests/test_outward.py::test_routing_and_bypass_table`: `blocks: [{text: 'per Pat'}]`,
  `approved: True`, `approved_draft_id`, `attachments: []`, `title: None`,
  `text: ['fixed in abc1234']` 2 to 1 (Design 1); `{}` 2 to 1 (Design 2 to 4). Rows that
  stay 2: `channel` object, draft in draft, `draft` string, `[]`, empty and missing tool
  names.
- `tests/test_outward.py::test_humanize_lint_gates`: `{'text': 1}` 2 to 0 (a number is
  ignored; Design 1).
- `tests/test_outward.py::test_reusable_classification`: `''` `(2, 'draft')` to
  `(1, 'draft')` (Design 3).
- `tests/test_outward.py::test_hook_integration`: the code-2 case uses `tool_input = []`
  instead of `{'blocks': []}` (it still denies either way; this keeps it a refusal).
- `tests/test_outbound.py::test_acceptance_and_audience`: `approved: True` and
  `in_scope: True` `(2, 'draft')` to `(0, 'send')` (Design 1); `''` `(2, 'draft')` to
  `(1, 'draft')` (Design 3). `is_dm: 'false'` and `recipients: 'dev'` stay `(2, 'draft')`.
- `tests/test_outbound.py::test_guard_tiers_and_bypasses`: `blocks: []` and
  `approved: True` 2 to 0; `is_shared: 'false'` stays 2.
- `tests/test_outbound.py::test_cli_tier`: `{'text': 'Thanks', 'approved': True}` 2 to 1
  (same as `{'text': 'Thanks'}`).
- `tests/test_outbound.py::test_hook_translation`: the code-2 case uses
  `inputs['is_shared'] = 'false'` instead of `inputs['blocks'] = []`.
- `tests/test_guard_mutation.py` probes for `outward.PreToolUse.check_tier` and
  `check_lint`: `{}` to `[]` (an empty object is now held as a draft by the tier and clean
  for the lint; a non-object is refused by both, so disabling either guard still turns the
  probe red).

Checked before handing over: the design, with these expectation changes, was applied to a
scratch copy of the worktree outside the repository; the full suite passed there except
tests that need a git checkout, which fail the same way on an unchanged copy.

## Must not change

- `classify`'s rules and reasons for every payload main accepted (Design 3 keeps its channel
  list identical); the #493 reason shape; the #492 resolution and modes.
- The type checks and reasons for the known policy keys (spec FR-004).
- `lint()` itself, `check_send`, `humanize_lint`, the ports and `remote.dm`; `check_tier`
  gains only the blank-text line of Design 3.
- The generic `cannot read or validate policy or payload` reasons in the `except` clauses:
  they still cover config errors and known-key type errors; only the non-object payload gets
  its own reason, in the guard.
- `drafts.destination`, `create`, `spend`, `approve` and `_edit` code.

## Fixtures

Neutral only: UUID servers `00000000-0000-4000-8000-00000000000n`, channel `C1`, issue key
`DEMO-12`, page id `00000000111122223333444444444444`, repository `acme/widgets`, address
`someone@example.test`, sensitive keyword `salary` (a schema default). No client, repository
or person names, no absolute paths.

## Deferred

- A Notion `parent` object and other non-string values under metadata keys still refuse
  (spec Assumptions).
- `Send with an edit` for drafts whose text is outside the top-level text keys.
