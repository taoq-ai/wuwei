# Implementation Plan: Owner draft queue

## Summary

Add a producer-owned `drafts` mapping in day state. The existing outward adapter decorator stores approve-tier calls and returns a finding containing the draft ID. Approval uses the same adapter implementation after mandatory lint, without a reusable approval token. The existing state writer atomically claims a pending draft before the external operation; racing approvals cannot both claim it.

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests. Reuse `state._write_state`, `workspace.atomic_write`, `registry.outward_operation`, `outward.check_tier`, `outward.check_lint`, `security.outbound`, the editor adapter, shell relevance helpers, and `protect_state` host-action enforcement. No new configuration keys or dependencies.

## Constitution Check

- Stdlib and ports: core adds no subprocess import; editing uses the existing editor port.
- Three-state exits: queueing/refusal is 1; errors are 2; successful host decisions are 0.
- Single writer: all trusted draft transitions use the shared locked writer and reserved event kinds.
- Test first: tests for each story run red before its implementation.
- Security: no body in events; no stored approval token consulted by normal outward sends; host actions blocked in agent hooks with relevance checked before parsing.
- Simplicity: one core draft module and one CLI command module; extend existing metrics and cockpit.
- Conflict: spec 5.9's future cockpit mutation is intentionally excluded by issue #174.

## Design

`drafts.py` holds queue validation, creation, edit preparation, approve and drop. Store adapter name and operation with JSON-safe original inputs. The queue records the selected voice audience. Successful approval records final inputs and final text, unedited status and character edit size. Character size uses SequenceMatcher changed spans, counting replacement as the larger of removed and inserted spans.

A locked pending-to-sending transition wins the right to send. The lock is released before transport, since adapters can append events. Success closes as sent; failure closes as failed. A crash leaves sending, which cannot be retried. Pre-send lint/editor failure leaves pending. A changed adapter configuration refuses approval rather than redirecting a stored draft.

`protect_state.check_bash` extends its host-only action handling to drafts approve/drop, using shared relevance and normalization. The queue is never a source of authorization for a seat's adapter call.

`metrics.collect` reads the trusted queue and emits per-audience sent count, unedited share and edited character sizes. `cockpit_snapshot` and dashboard HTML show pending drafts and escaped CLI instructions without mutation endpoints.

## Files and Validation

- Core: `cli/wuwei/drafts.py`, `registry.py`, `state.py`, `voice.py`.
- CLI and guards: `cli/wuwei/commands/drafts.py`, `commands/event.py`, `guards/protect_state.py`.
- Views: `metrics.py`, `commands/dashboard.py`, `templates/dashboard.html`.
- Tests: `tests/test_drafts.py`, `tests/test_dashboard.py`, `tests/test_state_allowlist.py`.
- Operator documentation: `docs/site/reference.md`.

Run focused in-process tests with fake transports and editor first, then the full requested interpreter's `-m pytest -q`. Check git diff whitespace and authored text hygiene. Leave changes uncommitted.
