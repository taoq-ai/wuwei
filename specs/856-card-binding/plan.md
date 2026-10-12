# Implementation Plan: an Owner step answer binds by the card's question, not its option text

**Branch**: `924-owner-cards` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Built with [../924-owner-cards/plan.md](../924-owner-cards/plan.md): both change
`sessions.needs_owner` and share its tests.

## Summary

`owner_topic(question, reply='')` hashes the question and the reply, never the options. The hook
also records the command part and the token of an answered question; `needs_owner` names the
mismatch when either was answered on another question. A Yes is spent by the `owner.approved`
row its command appends. `config set` and `add-repo` pass the command as the
identity their token hashes.

## Technical Context

Stdlib Python 3.11+. The `gate.asked` row shape is unchanged (a list of hashed topics); the asked
topic is unchanged, so old rows still read.

## Constitution Check

- III: one binding (`owner_topic`), one reader (`owner_answer`), one recorder (`record_gate`).
- IV: tests first, each seen red.
- V: shorter: `owner_answer` and `owner_topic` lose their options and detail parameters.
- VII: the question still names the exact command and token; seat answers and notes still count
  for nothing.

## Files to edit

- `cli/wuwei/sessions.py`: `owner_topic`, `owner_answer(root, command, token='')`, the mismatch
  line in `needs_owner`.
- `cli/wuwei/guards/answers.py`: record the question-and-reply topic and the token topic.
- `cli/wuwei/commands/config.py`: `offer(identity=)`; `_edit` passes the command.
- `cli/wuwei/closing.py`: the close hold reads `owner_answer` and never spends the Yes.
- Callers of `owner_answer`: `dispatch.py`, `pr_actions.py`, `derive.py`.
- Tests: `test_card_confirms.py`, `test_sessions.py`, `test_config_set.py`.
- Docs: design 9.1, `docs/site/concepts.md` "Owner step card".
