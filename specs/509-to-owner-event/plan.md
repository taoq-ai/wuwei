# Implementation Plan: a message to the owner records outward.to_owner under every connector mode

**Branch**: `509-to-owner-event` | **Spec**: `spec.md`

## Summary

The shared owner-identity check (`outward.check_tier`, `cli/wuwei/outward.py:760-763`)
already records `outward.to_owner` for every connector mode, because #496 routed every MCP
write through `check_tier` and `classify` passes a message to the owner before the mode row
(`outward.py:600-601`). The fix is a regression test per mode at the guard; no production
code changes.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. In-process guard calls with the existing
`configured` fixture of `tests/test_outward.py`; no subprocess, no network.

## Constitution Check

I stdlib: no code. II exits: unchanged. III one behaviour, one function, one test: the
behaviour stays in `check_tier`; the item adds the test the `send` mode was missing. IV test
first: the test is written and run first; it passes on the base as a regression guard,
which is the expected result here (see Root cause in spec.md). V ponytail: no production
diff. VII: the event stays reserved to its producer. Pass.

## Changes

### `tests/test_outward.py`

Add, next to `test_guard_to_owner_floor` (line 1641), reusing the helpers already in the
file (`with_owner`, `write_config`, `payload`, `opaque`, `UUID`, `owner_events`):

```python
@pytest.mark.parametrize('mode', ['send', 'draft', 'refuse'])
def test_guard_to_owner_every_mode(configured, mode):
    # #509: the connector mode never decides a message to the owner; each mode records the event.
    from wuwei import state
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    with_owner(root)
    write_config(root, f'\n[outward.modes]\n"{UUID}" = "{mode}"\n')
    call = payload(root, 'Your build is green', tool=opaque('slack_send_message'), channel='D01')
    assert check_tier(call) == check_lint(call) == (0, '')
    assert [row['payload'] for row in owner_events(root)] == [{'channel': 'slack'}]
    assert not state.read_state(root).get('drafts')
```

### Shared helper reused

`outward.check_tier` and `outward.owner_only` (the owner-identity check). No new helper.

## What must not change

- `cli/wuwei/outward.py`: `check_tier`, `classify`, `owner_only`, `table`, `MODE_TIERS`.
- `cli/wuwei/guards/outward.py` `_check`: the single `check_tier` call for every mode.
- `test_guard_to_owner_floor` and `test_guard_to_owner_every_posture`: kept as they are;
  the new test adds the missing `send` case and pins one event per call per mode.
- Docs, event reservation (`cli/wuwei/commands/event.py`) and signal class
  (`cli/wuwei/signal.py`).

## Contingency

If the test fails on the builder's base (another item reintroduced a mode fast path), the
fix is in the shared spot: make that path reach `outward.check_tier`, or move the
`owner_only` check with its `state.append_event('outward.to_owner', ...)` ahead of it in
`guards/outward._check`, one call, not a copy per mode.

## Verification

`python -m pytest -q tests/test_outward.py -k to_owner` then `python -m pytest -q`.
