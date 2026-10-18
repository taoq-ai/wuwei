# Feature Specification: the runtime budget is 3,400 lines and config holds six keys

**Feature branch**: `docs/budget-3400`
**Item**: budget-3400, tier standard, goal G-4
**Input**: The owner asked on 2026-10-18 to revise the runtime budget. The runtime is at 2,976 of
3,000 lines, and the approved backlog needs more than the 24 lines left.

## The promise in my words

This changes documents and one test assertion, and no runtime line. Every place that states the
runtime budget says 3,400 lines instead of 3,000: constitution principle VI, AGENTS.md,
CONTRIBUTING.md, design section 11 and the philosophy page. The size test asserts 3400 and its
message names 3400. The config budget grows from five keys to six, and the sixth is `models`,
which the models-record item adds. The constitution keeps "a change that breaks a budget deletes
something first" and adds one rule: an item that adds more than 10 runtime lines names the lines
it removes where it can, and no item waits on a free-lines round. The constitution goes from
3.1.0 to 3.2.0 with a new amendment date.

The acceptance scenarios, restated:

1. At the branch head the size test passes, and its assertion reads 3400.
2. A scratch copy of the head padded to 3,401 runtime lines fails the size test, and the failure
   names the budget 3400.
3. The five documents hold no runtime budget line saying 3,000, and each states 3,400.

## Requirements

- FR-001: `test_the_runtime_holds_its_size_budget` asserts at most 3400 lines and names 3400.
- FR-002: The constitution, AGENTS.md, CONTRIBUTING.md, design section 11 and philosophy.md state
  a runtime budget of 3,400 lines.
- FR-003: Constitution VI and design section 11 name six config keys, the sixth `models`.
- FR-004: Constitution VI adds the more-than-10-lines rule and keeps the delete-first rule.
- FR-005: The constitution version is 3.2.0, last amended 2026-10-18.
- FR-006: No runtime line changes.

## Reasoning for 3,400

The 2026-10-18 backlog estimates +274 runtime lines in total: +9 for the approved push-door items,
+10 for the bug sweep, +121 for the features planned now and +134 for the GitLab, Gemini CLI and
sandbox builds that follow their spikes. At each item's own budget that is +408, so
2,976 + 408 = 3,384. 3,400 covers it with 16 lines to spare. The GitLab build (+90, budget 130) is
the least certain estimate; it is expected to justify its own lines or wait, and stays a design
pressure.

## Assumptions

- The owner's "revise the budget" means raise it to fit the backlog. Overturned if the owner names
  another number.
- 3,400 rather than 3,500, because the GitLab estimate should earn its lines.
- Six keys, because a machine-read model override needs a key; a seventh would need its own case.
- Design section 2 (principle 8) and philosophy.md also said "five keys". They now say six, so the
  documents agree with constitution VI and section 11. Overturned if the owner wants the key count
  changed only where the item names it.
- `tests/test_ledger.py` (`test_config_keeps_only_the_five_keys`) and the runtime help text and
  docs/site/reference.md that say "five keys" change with models-record, which adds the key in
  `ws.DEFAULTS`. Until it merges the documents name a key the runtime does not read yet.
