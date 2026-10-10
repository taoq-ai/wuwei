# Implementation Plan: an empty ticket field is absent, not a rejected proposal

**Branch**: `640-empty-ticket` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Normalise the three optional candidate fields once, at the top of the per-candidate loop in
`plan._proposal`: a null or blank `ticket`, `tier` or `docs` is popped from the candidate
dict. The existing presence checks for `tier` and `ticket` then skip it, and every reader
downstream (`proposal.json`, `approve`, `add`, `tracker._candidate`) sees the key absent.
Rewrite the ticket refusal so it quotes the value and shows `TICKET` with example ids. One
sentence in the lead plan JSON reference. No new function, no new module.

## Technical Context

- Python 3.11+, stdlib only; pytest for tests.
- Touched: `cli/wuwei/plan.py`, `tests/test_plan.py`, `docs/site/reference.md`.
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I (stdlib only): no import added.
- II (fail closed): an invalid present value still raises `ValueError`, which the plan
  command maps to exit 2 as today; only an empty value stops being an error.
- III (one behaviour, one function): the normalisation lives in `_proposal`, the one
  validator `propose`, `approve` and `add` already share.
- IV (test first): tasks.md orders each test before its change.
- V (ponytail): a three-line loop at the shared spot; no helper, no config.

## Design

### cli/wuwei/plan.py, `_proposal` (line 37)

Inside `for item in data['candidates']:`, after the `name` check (line 82) and before the
`tier` check (line 89), add:

```python
for key in ('ticket', 'tier', 'docs'):  # #640: an empty optional field is absent
    if item.get(key) is None or isinstance(item[key], str) and not item[key].strip():
        item.pop(key, None)
```

`item.get(key) is None` is also true for a missing key; `pop(key, None)` makes that a no-op.
The pop is in place on purpose: `propose` writes the same candidate dicts to
`proposal.json` (line 261), and `add` passes the discovery candidate it later reads at line
445 by reference (line 439). Returning a cleaned copy instead would leave `add` reading the
empty ticket and recording id `""`. Do not change that to a copy.

Replace the ticket refusal at line 93 with:

```python
raise ValueError(f'{name}: invalid ticket {item["ticket"]!r}; ticket must match {TICKET}, '
                 f'an id such as ENG-12, PROJ-12 or owner/repo#12, or be left out; {PLAN_JSON}')
```

It keeps the `{name}: invalid ticket` prefix that `test_invalid_candidate_ticket_is_unrun`
matches. The example ids are the ones `set_ticket` already prints (line 543).

### docs/site/reference.md (Lead plan JSON, candidate paragraph, line 100)

After the sentence on `tier`, add: "An optional `ticket` names an existing tracker ticket,
an id such as `ENG-12`, `PROJ-12` or `owner/repo#12`. An empty string or `null` for
`ticket` or `tier` counts as absent."

## What must not change

- The `tier` check and message (line 89-90): it already names the item, the field and the
  accepted values.
- `TICKET`, `set_ticket` and its message: `plan set <item> ticket=` with an empty value is
  still refused.
- `approve`, `add` and `tracker.check`: they keep testing key presence; the normalisation
  makes that correct.
- `plan template` and `candidate_template`: no `ticket` field is added.
- The lead charter: the lead may keep writing `""`; it is no longer an error.

## Project Structure

```text
specs/640-empty-ticket/
  spec.md
  plan.md
  tasks.md
cli/wuwei/plan.py          # _proposal: normalise, ticket message
tests/test_plan.py         # three tests next to test_invalid_candidate_ticket_is_unrun
docs/site/reference.md     # one sentence
```

No research.md, data-model.md, contracts/ or quickstart.md: the change has no open question,
no new record shape and no new interface.
