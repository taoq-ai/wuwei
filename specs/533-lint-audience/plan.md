# Implementation Plan: the internal-state lint applies by kind and audience

**Branch**: `533-lint-audience` | **Date**: 2026-10-05 | **Spec**: `spec.md`

## Summary

Move the `outward.patterns` check out of `lint()` (which knows neither kind nor audience)
into one helper, `internal_word`, called from the two places that do know: `classify` (the
tier decision, where every chat or mail call's parties and their audience classes are
already computed) holds a client or public reader with a card naming the word, and
`check_lint` (the lint for everything that sends) warns, stays silent, or refuses under
strict, for chat and mail only. Tracker, docs, code-host and `other` writes never read the
list. About 30 lines of runtime change in one module plus one event registration.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Files: `cli/wuwei/outward.py`,
`cli/wuwei/commands/event.py`, `cli/wuwei/signal.py`, docs. No new module, no new config key,
no schema change (no `CONFIG_CACHE_VERSION` bump).

## Constitution Check

- I stdlib only: yes. II three-state exits: an invalid pattern raises `re.error` or
  `TypeError` inside the existing `try` blocks of `classify` and `check_lint`, so it is exit 2.
- III one behaviour one function: `internal_word` matches, `classify` holds, `check_lint`
  warns. IV test first: every task pair below. V ponytail: no new layer, the helper replaces
  four lines in `lint()`. VII security: no new trust; the event is reserved to its producer.
- Program (#530): no new refusal under observe or guarded; strict keeps its refusal.

## Design

### 1. `internal_word(text, config)` in `cli/wuwei/outward.py` (new, near `lint`)

```python
def internal_word(text, config):
    """#533: the first outward.patterns match in text, over lint's normalized views, or None."""
    normalized = _normalize(text)
    for pattern in config['outward']['patterns']:
        for view in (normalized, normalized.replace('_', ' ')):
            found = re.search(pattern, view, re.IGNORECASE | re.DOTALL)
            if found:
                return found.group(0)
    return None
```

A non-string pattern raises `TypeError`, a bad regex `re.error`; callers already catch both.

### 2. `lint()` (`cli/wuwei/outward.py:90-143`)

Delete the `patterns = [...]` compile (`:110-111`) and the pattern loop (`:126-130`). Nothing
else in `lint()` changes. Effect: `shepherd.raise` (code host), `digest._clean` (owner) and
every other direct caller stop applying the patterns.

### 3. `classify` (`cli/wuwei/outward.py:572`), the client and public hold

Hoist the parties out of the `decide` call and add one check right after it:

```python
parties = _parties(context, destinations, mention_text, kind, tool, config, code, thread)
found = decide(parties, topics, [name for name in (tool, kind) if name], config, trace)
# #533: an internal-state word to a client or public reader is a card naming both; a block row wins.
outside = next((party for party in parties if party['class'] in ('client', 'public')), None)
if outside and kind in OWNER and not (found and found[0] == 'block'):
    word = internal_word(text, config)
    if word:
        return held(f'internal state word "{word}" for the {outside["class"]} audience of '
                    f'{outside["id"]} (outward.patterns), rewrite that line')
```

`OWNER` is the existing `{'chat', 'slack', 'mail'}` table of #495 (kinds with a private
audience); reuse it, do not add a kind list. The fragment has no `'; '` (the `why` contract).
`owner_only` returns before this, so the owner never gets it. The patterns are compiled only
when a client or public party exists.

### 4. `check_lint` (`cli/wuwei/outward.py:758-774`), the warning

After the existing per-channel `lint()` loop, before `return CLEAN, ''`:

```python
kind = next(iter(channels))
word = internal_word(text, config) if kind in OWNER and not to_owner else None
if word:
    from wuwei import workspace
    reason = (f'outward: internal state word "{word}" in a {kind} message (outward.patterns); '
              'remove it or change the list')
    if workspace.posture(config)[0] == 'strict':
        return FINDINGS, reason
    if config['autonomy']['mode'] == 'supervised':
        from wuwei import state
        state.append_event('outward.lint', {'kind': kind, 'word': word}, root)
        print(f'warning: {reason}', file=sys.stderr)
```

`to_owner` is already widened by `owner_only` at the top of `check_lint`. Callers unchanged:
the hook guard (`guards/outward._lint`), the port (`check_call`), `drafts.approve`
(`drafts.py:300`) and `remote.dm`. Add a `ponytail:` note that the hook runs this even when
`check_tier` held the call (spec A5).

### 5. Event registration

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'outward.lint': 'the outward port and
  hook (wuwei.outward.check_lint)'` (reserved: `wuwei event outward.lint` exits 1).
- `cli/wuwei/signal.py` `SILENT`: add `'outward.lint'` next to `'outward.ai_tells'`.

### 6. Docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.3: one paragraph: the patterns apply to chat and
  mail only, never to tracker, docs and code-host writes; a client or public reader gets a
  card naming the audience and word; team and company get a warning (`outward.lint`) under
  `autonomy.mode = "supervised"`, nothing under autonomous; strict refuses.
- `docs/site/configuration.md`: the `outward.patterns` row (line 385) states the same in one
  sentence; the `autonomy.mode` row (line 177) adds that autonomous drops the
  internal-state warning.
- `CHANGELOG.md` is release tooling's; do not edit.

## Tests (all in `tests/test_outward.py` unless named)

Fixtures to reuse: `configured` (profile strict, posture guarded, `default_tier = "ask"`,
`work_channels = ["chat", "C1"]`), `payload()`, `outbound_line()`, `write_config()`,
`set_posture()`, `run_hook()`, `events_of()`, `opaque()`, `UUID`. Neutral text:
`'Notes for I-12 in src/app/main.py'`, patterns `[r'\bI-[0-9]+\b', r'[a-z_]+/[a-z_/]+\.py']`.
Set patterns and autonomy through `write_config(root, '\n[outward]\npatterns = [...]\n')`
and `'\n[autonomy]\nmode = "supervised"\n'`; the `[outward]` table is not in the fixture yet.

Tests to change: `test_configured_lint` loses its four `patterns` rows (they move to the
`internal_word` test); `test_owner_internal_state_pattern_names_the_word` asserts through
`check_lint` under strict instead of `lint()`; `tests/test_signal_status.py` expected map gains
`'outward.lint': 'silent'`.
Found in implementation: the owner-only paths lose the list (A6), so `tests/test_remote.py`,
`tests/test_digest.py` and `tests/test_listen.py` stop expecting a word-list refusal there
(the listen fallback tests use a banned character instead). `check_lint` matches the word
before the lint loop, so an invalid list fails closed (exit 2) on chat and mail even when an
earlier lint finding is relaxed by the standard profile (`tests/test_profiles.py`).

## What must not change

- `lint()`'s other rules (owner name, pronouns, banned characters, emoji, length, voice) and
  every existing reason text.
- The tier table, `decide`, the umbrella, `tracker.auto`, `docs.auto` and every existing
  hold reason for calls with no matched word.
- `check_call`'s rule that a draft skips the lint until approval.
- `drafts.approve`: no change; the client hold is the tier's, which approval answers.
- Strict posture: the team and company refusal stays.

## Project Structure

```
specs/533-lint-audience/   spec.md plan.md tasks.md analysis.md
cli/wuwei/outward.py       internal_word, lint, classify, check_lint
cli/wuwei/commands/event.py, cli/wuwei/signal.py
tests/test_outward.py, tests/test_signal_status.py
docs/specs/2026-09-24-wuwei-design.md, docs/site/configuration.md
```
