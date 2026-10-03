# Implementation Plan: Every external write goes through the humanizer pass by default

**Branch**: `420-outward-humanize` | **Spec**: [spec.md](spec.md) | **Issue**: #420

## Summary

Add one function, `outward.humanize_lint`, next to the existing `TELLS` table and `tells()` in
`cli/wuwei/outward.py`. It maps the write to one of five kinds, runs `tells()` on the text, and
either does nothing (off, out of kind, clean), refuses (strict) or warns and records an
`outward.ai_tells` event (default). Call it at the shared spots every outward write already
passes: `outward.check_call` (all adapter ports, through `registry.outward_operation`), the hook's
outward lint guard (MCP writes), and the two writes that do not use the port wrapper
(`pr_actions` reply drafts, `shepherd.raise_pr`), plus `drafts.approve`. Three config keys, one
`dash` row change, a walk test over the port contract, the charter sentence, and docs.

No new module, no second checker, no change to `check_call`'s or `outward_operation`'s signature
(#417 and #419 call them).

## Technical Context

- Python 3.11+ stdlib only; pytest for tests. Run `python -m pytest -q` from the repo root.
- `co_qualname` (3.11+) identifies the port wrapper in the walk test without a marker attribute.
- Hook latency (#346): `humanize_lint` lives in `outward.py`, already imported by the outward
  guard; `wuwei.state` is imported only when there is a finding to record.

## Constitution Check

- I stdlib only: yes. II three-state exits: `humanize_lint` returns 0, 1 or 2; read and validation
  errors are exit 2 with the existing outward reason; an append failure is exit 2.
- III one behaviour, one function: `humanize_lint` is the only place that decides kind, gating,
  strict and the event; every caller is one call.
- IV test first: every behaviour below has a test task before its implementation task.
- V ponytail: reuses `TELLS`, `tells`, `_text`, `profile_result`, `drafts` `style`,
  `workspace.verbosity`; one `ponytail:` comment for the hook-path double count.
- VII security: the event carries tell names only, never message text; strict refusal fails
  closed before any draft or send.

## Changes

### `cli/wuwei/workspace.py` (config)

In `SCHEMA['outward']` (after `max_length`):

```python
"humanize": (bool, True),
"humanize_kinds": [(str, None, ("dm", "tracker", "docs", "pr", "review")),
                   ["dm", "tracker", "docs", "pr", "review"]],
"humanize_strict": (bool, False),
```

The list-with-choices form is the one `scanner.mcp.block` uses, so an unknown kind is a
`ConfigError`.

### `cli/wuwei/outward.py` (the one function)

1. `TELLS` `dash` row: a character class of the escapes for U+2013 and U+2014, or ` -- ` (adds
   the em dash; write the escapes, never the literal characters). Update the comment above the
   table: a hit is a style finding; `outward.humanize_strict` turns it into a refusal for outward
   text.
2. Next to `tells()`:

```python
# Humanize kinds by port or tool channel; a DM is 'dm' whatever the channel.
KINDS = {'chat': 'review', 'slack': 'review', 'tracker': 'tracker',
         'code_host': 'pr', 'docs': 'docs'}
HUMANIZE = 'rewrite it with the humanizer skill in embedded mode, or the checklist in charters/_common-authoring.md'


def humanize_lint(inputs, root, config, channels, *, draft=False):
    """The humanizer pass on outward text: (0, '') off or clean, (1, reason) strict,
    else warn, record outward.ai_tells and return (0, reason)."""
```

Body, in order:
- `texts, _ = _text(inputs)`; `channel = next(iter(channels))` (callers pass one channel;
  `len(channels) != 1` returns the existing `(UNRUN, 'outward: ambiguous tool channel
  configuration')`).
- `kind = 'dm' if inputs.get('is_dm') is True else KINDS.get(channel)`.
- `rules = config['outward']`; return `(CLEAN, '')` when `not rules['humanize']` or
  `kind not in rules['humanize_kinds']`.
- `found = tells('\n'.join(texts))`; `(CLEAN, '')` when empty.
- `reason = f"outward: ai tells {', '.join(found)}; {HUMANIZE}"`.
- strict: `return FINDINGS, reason` (no event: nothing is drafted or sent).
- else: `from wuwei import state`; `state.append_event('outward.ai_tells', {'kind': kind,
  'tells': found, 'draft': draft}, root)`; `print(f'warning: {reason}', file=sys.stderr)`;
  `return CLEAN, reason`.
- Wrap in `try` with the same `except (OSError, ValueError, TypeError, KeyError,
  AttributeError, re.error): return UNRUN, 'outward: cannot read or validate policy or payload'`
  as `check_lint`.

Add `import sys` at the top.

3. `check_call` (same signature):

```python
def check_call(inputs, root, config, channels):
    from wuwei.guards import profile_result
    result = check_tier(inputs, root, config, channels)
    draft = result == (FINDINGS, APPROVAL_REQUIRED)
    if result[0] and not draft:
        return result
    try:
        lint = (CLEAN, '') if draft else check_lint(inputs, root, config, channels)
        if not lint[0]:
            lint = humanize_lint(inputs, root, config, channels, draft=draft)
        lint = profile_result(lint, config['profile'], root, next(iter(channels)))
    except KeyError:
        return UNRUN, 'outward: cannot read profile'
    return lint if lint[0] else (result if draft else (CLEAN, ''))
```

A draft gets the humanize pass only (the outward lint still runs at approval, unchanged); a send
gets the outward lint, then humanize. Strict findings go through `profile_result` like the lint.
`registry.outward_operation` is unchanged: a strict refusal is not `APPROVAL_REQUIRED`, so no
draft is stored.

### `cli/wuwei/guards/outward.py` (MCP writes)

```python
def check_lint(payload):
    return _check(payload, _lint)


def _lint(inputs, root, config, channels):
    # ponytail: runs even when check_tier refuses the same call, so a retried write records its
    # tells twice; pass the tier result between guards if the metric needs exact counts.
    result = outward.check_lint(inputs, root, config, channels)
    return result if result[0] else outward.humanize_lint(inputs, root, config, channels)
```

Keep the guard name `check_lint` (posture `AREAS` and `profile_relaxable` key on it). `_check`
compares `policy is outward.check_tier` only, so `_lint` passes through unchanged.

### `cli/wuwei/pr_actions.py` (PR reply draft)

Before `drafts.create` (line 434), after the `existing` short-circuit:

```python
code, reason = outward.humanize_lint(inputs, root, config, {channel_kind}, draft=True)
if code:
    print(reason)
    return code
```

The send branch already goes through `obligations.reply` and the `code_host.comment` port.

### `cli/wuwei/shepherd.py` (`raise_pr`, PR title and body)

After the `outward.lint` call (line 267):

```python
code, reason = outward.humanize_lint({'title': title, 'body': body}, root, config, {'code_host'})
if code:
    print(reason)
    return code
```

### `cli/wuwei/drafts.py` (`approve`)

After the outward lint passes (line 138 block), before the confirmation:

```python
code, style = outward.humanize_lint({**inputs, 'is_dm': row['operation'] == 'dm'}, root, config,
                                    {row['channel']}, draft=True)
if code:
    return registry.Result(code, reason=style)
```

and the prompt becomes `f"Send this draft to {row['destination']}:\n{text}" + (f'\n{style}' if
style else '')`. `_text` accepts `is_dm` as a boolean field; `inputs` sent to the adapter stay
unchanged (`is_dm` is only in the lint copy). `drafts.create` and its `style` field are unchanged.

### `cli/wuwei/metrics.py` (`collect`)

After the decision-record loop:

```python
for index, row in enumerate(events or []):
    if row['kind'] == 'outward.ai_tells' and row['payload'].get('draft') is False:
        ai_tells[f'outward-{index}'] = len(row['payload']['tells'])
```

Drafts stay counted from their rows; `draft=True` events are not counted again.

### `cli/wuwei/signal.py` and `cli/wuwei/commands/event.py`

- Add `'outward.ai_tells'` to `SILENT` (a style warning never nudges; `status.SKIP` derives from it).
- Add `'outward.ai_tells': 'the outward port and hook (wuwei.outward.humanize_lint)'` to
  `EVENT_PRODUCERS`. It is not in `FREE_KINDS`, so `wuwei event outward.ai_tells` is already
  refused.

### `cli/wuwei/remote.py` (DM `status`)

In `handle`, `verb == 'status'`:

```python
if control_plane._level(root) == 'full':
    count = sum(len(row.get('style') or []) for row in drafts.read(state.read_state(root)).values()
                if row['status'] == 'pending')
    if count:
        text += f' | ai tells {count}'
```

### `charters/_common-authoring.md`, `agents/*.md`, `skills/wuwei-plan/SKILL.md`

Replace the paragraph under "## Writing for a person" (line 17) with:

> Text written for a person (decision records, PR bodies, drafts, retro summaries, digests and
> briefing packs) and every outward text (tracker comments, docs pages, DMs, PR comments and
> review pings) is rewritten with the `humanizer` skill in embedded mode before it is saved,
> drafted or posted, when the skill is installed. Without it, check the text against this list.
> The CLI lint flags the mechanical tells: a `style` finding on drafts and decision records and,
> on outward text, a warning and an `outward.ai_tells` event, or a refusal when
> `outward.humanize_strict` is on. An em dash or an emoji is always refused.

(One paragraph, the checklist below unchanged; check it with `outward.tells` before saving.)
Rebuild the agents with `bin/wuwei agents build`; `bin/wuwei agents check` must be clean.

In `skills/wuwei-plan/SKILL.md` line 10, change the humanizer sentence to: "Rewrite any text
written for a person, outward text included (tracker comments, docs pages, DMs, PR comments,
review pings), with the `humanizer` skill in embedded mode when it is installed; otherwise apply
the checklist in `charters/_common-authoring.md` under Writing for a person." Keep the word
`humanizer` once in the file.

### `templates/workspace/config.toml`

Under `[outward]`, before `[outward.max_length]`:

```toml
# humanize = true # AI-tell lint on outward text (charters/_common-authoring.md).
# humanize_kinds = ["dm", "tracker", "docs", "pr", "review"] # Kinds the lint checks.
# humanize_strict = false # true refuses a text with a tell instead of warning.
```

### Docs

- `docs/site/configuration.md`, "Outward text and outbound tiers" table: rows for
  `outward.humanize`, `outward.humanize_kinds`, `outward.humanize_strict` (default and meaning).
- `docs/site/concepts.md`, "## Writing for the owner": fix "a tell never blocks a send" and add
  one paragraph: every outward write (the five kinds) gets the humanize lint before it is drafted
  or sent; default warns and records `outward.ai_tells`; `humanize_strict` refuses with the
  findings; drafts show them in `bin/wuwei drafts` and the approval prompt; the DM status shows
  the count at full verbosity. No tells, no em dash.
- Glossary: `### Humanizer` as the last entry, two lines; add `('Humanizer', r'humanizer')` to
  `GLOSSARY` in `tests/test_docs.py`; in `README.md` credits, link the word to
  `docs/site/concepts.md#humanizer` and keep the source as a second link, so the first-use test
  passes.
- `docs/site/reference.md`, `drafts approve` row: "Run security, outward, voice and humanize lint
  (the findings show in the prompt), then send ...".

## Test plumbing (existing tests that move with the change)

- `tests/test_docs.py` `GLOSSARY` gains `Humanizer`; the concepts assertion at line 738 still holds.
- `tests/test_charters.py` humanizer test keeps passing with the new paragraph; extend it (T017).
- `tests/test_outward.py` `test_tells_table` `dash` row: add an em dash hit.
- Existing port and draft tests use texts without tells, so the new warning does not reach them;
  `test_draft_style_finding_is_recorded_and_never_blocks` still passes at the default (warn).

## What must not change

- `outward.check_call(inputs, root, config, channels)` and `registry.outward_operation(kind)`
  signatures and their draft flow (#417 and #419 build on them).
- `outward.lint`, `classify`, `check_tier` and the approval tiers; tier refusals stay owner-only.
- `drafts.create` and the draft record schema (`style` stays as #303 wrote it).
- `remote.dm` (control plane) and its fixed lines.
- The `TELLS` table stays the only list of tells; no triad pattern.
