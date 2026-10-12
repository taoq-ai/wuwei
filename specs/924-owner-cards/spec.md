# Feature Specification: an owner-approved Owner step applies when run again

**Feature Branch**: `924-owner-cards` (one batch with #856)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #924. `wuwei config set outward.allow '[...]' --add` asked its card; the
owner answered Yes in the session; the session's rerun was refused by the Claude Code auto-mode
classifier (outside WUWEI); the owner ran the exact command in their own terminal twice and got
the same "waits for the owner" refusal with the same card id (651cd231f38a), and nothing changed.

## Root cause (0.29.0 and 0.30.0)

The terminal run did see the session's answer; the answer did not match the card. The owner's
workspace records it: the AskUserQuestion trace of 16:49 shows the question verbatim and the Yes
option's description shortened by the planner (no `@@` hunk header, no context lines), and the
`gate.asked` row of that call holds the asked topic and the Yes topic of the shortened options.

- `cli/wuwei/guards/answers.py:45` records the Yes bound to the options as asked.
- `cli/wuwei/sessions.py:49-50` recomputes the Yes topic from the printed card, whose Yes
  description is the full diff (`cli/wuwei/commands/config.py:216`).
- `cli/wuwei/sessions.py:59-60` finds the asked topic and no reply topic: the answer is None.
- `cli/wuwei/sessions.py:67-71` prints the same refusal and card, with no hint that a card was
  answered.

Ruled out: the command text (`config.py:398` builds it from the arguments, not from argv or the
launcher), the token (the same card id both times), the day (`workspace.py:424`, the same date)
and the workspace (the same config, or the digest would differ). The binding is #856; this
feature adds the refusal line and the field replay.

## User Scenarios & Testing

### User Story 1 - the answered card applies when run again (P1)

1. **Given** the field card answered Yes in the session with a shortened option, **When** the
   same command runs again, from the session or from the owner's own shell, **Then** it applies
   and `owner.approved` records the approval.

### User Story 2 - every refusal says how the change gets applied (P2)

1. Every Owner step refusal says, on its one line, which card to ask and that once it is
   answered Yes the same command applies from the session or from the owner's own terminal; a
   config command adds that the owner may also edit `.wuwei/config.toml` by hand.

### User Story 3 - no terminal answer (P1, review F1)

1. **Given** no answered card, **When** a session wraps the command in a pseudo-terminal, strips
   its environment and types y, **Then** the command refuses and nothing is approved.

## Requirements

- **FR-001**: `needs_owner`, which every owner-only refusal goes through (plan set, plan resume,
  merge, close, integrity reconfirm, pr act, the deploy guard, config set, add-repo and promote,
  doctor fix, telemetry send), approves only on the owner's Yes on the card (#856 binding).
- **FR-002**: an approval appends `owner.approved` with the command and the token.
- **FR-003**: the refusal stays one line and says where the answered command applies.
- **FR-004**: nothing reads a terminal answer.

## Success Criteria

- **SC-001**: the field sequence (Yes on the shortened card, the same command again) applies on
  the first rerun; before, it refused twice.
- **SC-002**: a pseudo-terminal run with the session environment stripped and y typed refuses.

## Assumptions

- Design 9.1 "Nothing runs in a terminal" (#831) stays true: the owner's answer comes only from
  the card (security review F1 removed a first build's other approval path).
- The Claude Code auto-mode classifier refusing the session's rerun is outside WUWEI. After the
  owner's Yes, the owner can run the same command in their own shell.
