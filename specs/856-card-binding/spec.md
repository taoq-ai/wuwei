# Feature Specification: an Owner step answer binds by the card's question, not its option text

**Feature Branch**: `924-owner-cards` (one batch with #924)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #856 with its field comment. An Owner step card counted only when the
AskUserQuestion question and every option description matched the printed card byte for byte.
A paraphrased card (same token, shorter option text) answered Yes did not count, and three
adjacent `config set` calls could not be answered in one round because each card's token hashed
the rendered config.toml diff.

## Root causes (0.30.0)

1. `sessions.owner_topic` (`cli/wuwei/sessions.py:39-43`) hashes the question, every option as
   asked and the reply. The hook records that topic from the options the planner asked
   (`cli/wuwei/guards/answers.py:45`); `owner_answer` recomputes it from the printed card's options
   (`sessions.py:49-50`). Any change to an option description (the planner shortening a diff)
   leaves the asked topic matching and no reply topic matching, so the answer reads as None
   (`sessions.py:59-60`) and `needs_owner` prints the identical refusal (`sessions.py:67-71`).
2. `config.offer` (`cli/wuwei/commands/config.py:214`) makes the card token a digest of the
   rendered diff, hunk context included. Applying one key changes the context of the next key's
   hunk, so a card answered in the same round no longer matches.

## User Scenarios & Testing

### User Story 1 - a shortened option still counts (P1)

1. **Given** a printed card whose Yes option holds a config.toml diff, **When** the planner asks
   it with the same question and a shorter description and the owner answers Yes, **Then** the
   same command applies.

### User Story 2 - adjacent keys in one round (P1)

1. **Given** `codex.command`, `codex.timeout_seconds` and `gates.second_opinion` each refused with
   its card, **When** the owner answers all three Yes, **Then** the three commands apply one
   after another without another card.

### User Story 3 - a reworded question says so (P2)

1. **Given** a card asked with its token but a reworded question, **When** the command runs
   again, **Then** the refusal says a card for this step was answered but did not match, and to
   ask it verbatim. The same holds for a card without a token (review F4).

### User Story 4 - a Yes counts once (P1, review F2)

1. **Given** `config set cap 5` applied on the owner's Yes and the owner then set `cap = 6` by
   hand, **When** the planner runs `config set cap 5` again, **Then** it asks the card again.

## Requirements

- **FR-001**: the answer topic is the question plus the reply. The question is
  `Owner step: <command> (<token>)`, so it is the action identity: the exact command and the
  digest of what it changes. Option text is shown for review and binds nothing.
- **FR-002**: `config set` and `config add-repo` take their token from the command (key, value
  and `--add`), not from the rendered diff; `config promote` keeps the digest of its proposal.
- **FR-003**: the hook records the card's token beside the answer; a token answered on a question
  that does not match the card makes the refusal say `a card for this step was answered but did
  not match; ask it verbatim`.
- **FR-004**: the latest answer on the card still decides; a seat's answer and a forged note still
  count for nothing.
- **FR-005** (review F2): a Yes is spent once: an `owner.approved` row for the same command and
  token after it makes the answer None, so a later run asks again. The close hold reads the Yes
  on the day's critical findings without spending it (a check that runs on every close).
- **FR-006** (review F4): the mismatch line also fires for a card without a token: the hook records
  the command part of each answered question (prefix and trailing `(...)` removed).

## Success Criteria

- **SC-001**: the field card (question verbatim, diff shortened) answered Yes applies; before, it
  printed the same refusal.
- **SC-002**: three adjacent keys: one round of three answers, before three rounds.

## Assumptions

- The question carries the full command and the token, so binding the question is binding the
  token plus the action identity. A question that changes the command is a different action and
  does not count; it gets the mismatch line instead (the issue allows either).
- This supersedes the #831 review rule F6 (the answer binds the printed options) at the owner's
  request in #856 ("the card token is what binds the answer, with the diff shown for review").
  The owner still reads the exact command in the question.
- Review F3, accepted trade-off: only the question binds, so the planner can ask the right
  question with a misleading Yes description and the Yes still counts. For cards whose token
  hashes content the question does not show (doctor fix, plan resume, the dispatch fix round,
  the close hold, a merge at a head) the Yes text is the only plain description. The token
  pins the action, not its description. The owner asked for this binding in #856.
- With the token taken from the command, a Yes no longer goes stale when the config changes;
  FR-005 spends it once instead, so an old Yes never re-applies over a later owner change.
- Rows recorded before this change keep their asked topic; their reply topics used the old shape
  and do not count after the upgrade. Answers are day-scoped, so this costs at most one card.
