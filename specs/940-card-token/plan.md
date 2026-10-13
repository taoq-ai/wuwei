# Implementation Plan: Owner step card token binding

## Technical Context

Python 3.11+, standard library runtime, pytest for offline development tests. Existing sessions.py owns answer lookup and refusal construction; guards/answers.py records hashed answers; dispatch.py builds cards consumed by build.step and dispatch decisions.

## Root Cause

Before changes, cli/wuwei/sessions.py:40 hashes the entire question, and cli/wuwei/guards/answers.py:45 records that identity. Appended context changes the hash. Its token hint regex at line 47 is end-anchored; sessions.step at line 82 strips only a trailing parenthesized component. Both hints disappear with appended context. cli/wuwei/dispatch.py:659 returns a card and plain blocked reason; cli/wuwei/commands/build.py:237 prints them without needs_owner's diagnostic.

## Constitution Check

Pass: one shared identity rule, one shared diagnostic, no new runtime module or dependency, no terminal reader, no raw question storage. Test first using existing fake owner hook and fake day. User limits validation to explicit test files, including every importer of changed modules. No design edits, commits, pushes, stashes, or GitHub commands. Existing worktree and branch retained.

## Design

Normalize a leading Owner step command and 12-hex token once in the answer recorder, using shlex.split to skip token-shaped text inside quoted command arguments, before hashing identity and hints. Continue looking up the reply by the complete original question. Preserve exact matching for cards without a generated token. Extract the existing mismatch detection into sessions.owner_mismatch(root, card), returning an empty string or a diagnostic naming the shared identity and expected component. needs_owner and dispatch's card refusal paths call it. No event schema changes.

Alternatives: token-only authorization would permit a different command; retaining raw question text would expose context and grow the event schema. Both are rejected.

## Implementation Sequence

1. Add field-case and negative regressions in tests/test_card_confirms.py, tests/test_one_action.py and tests/test_dispatch.py; observe expected failures.
2. Normalize the recorded card identity in cli/wuwei/guards/answers.py.
3. Share mismatch reporting in cli/wuwei/sessions.py and use it from cli/wuwei/dispatch.py for Blocked and gate escalation cards.
4. Run focused regressions, then explicitly list and run every test file importing changed modules. Review correctness, trust boundaries and diff size.

## Validation

Use the interpreter specified in the task with `-m pytest -q -p no:cacheprovider`, followed by explicit test file arguments. Discover importers with rg under tests/, including indirect test helpers. No network or real GitHub calls. Record exact red and green summaries in analysis.md.

## Review follow-up plan

Root causes: sessions.owner_answer chooses Yes first when both Yes and No occur in a row; sessions._topics yields spent history to owner_mismatch; guards.answers.record_gate derives the command hint from the entire question only.

Add failing real-hook regressions for each finding in tests/test_card_confirms.py. Require exactly one recognized reply per canonical card; scan diagnostic rows newest first only after the last approval for this command; add the first-line step hash as a diagnostic-only topic. Reuse existing functions and event schema. Run the three requested files plus every sessions/guards.answers importer and shared fake-owner consumer.
