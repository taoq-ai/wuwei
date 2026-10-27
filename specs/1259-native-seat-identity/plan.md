# Implementation plan

Python 3.11 stdlib only. Change hook.codex and its post-tool consumer, preserving Agent semantics for supported launches.

## Research and data model

The 2026-10-27 sanitized native probe found agent_type input and a JSON task_name output. Legacy tests use agent_id. Decode an object structurally instead of searching serialized text. Normalize message to prompt and reasoning_effort to effort. Requested model remains asked; resolvedModel is not synthesized. Existing agents.TABLE validates explicit role names. No alternative native role field has evidence.

A successful known-role response becomes Agent with agentId. Missing role becomes an unconfirmed dispatch carrying agentId and a precise role-capability diagnostic. Invalid identity raises a diagnostic caught by the existing hook.error path. Neither path attests work.

## Constitution check

Stdlib only; no new dependencies, config, doors or attestation. Tests precede runtime edits. Runtime delta stays within the approved ten lines. Vendor copies remain identical. No shell command parser changes.

## Phases

1. Add a sanitized native payload and consumer tests, run red (FR-001 through FR-005).
2. Replace regex parsing and preserve requested settings, run green.
3. Update schema-sensitive guidance and vendor copies (FR-006).
4. Run focused checks and the main/head route differential in archived trees, then request the serialized full suite.

## Validation quickstart

Run uv run --no-project --with pytest python -m pytest -q tests/test_codex.py tests/test_hook.py tests/test_setup.py.
Run specs/gates-at-push/route_diff.py against baseline 3feedf5c and the head with the same tests, using builder-1259 scratch case roots.
Run bin/wuwei agents check. Record corpus hash and every moved result. No parser combinatorial probe applies because shell parsing is unchanged.

## Scope

Only hook.py, Codex tests and payloads, wuwei-run guidance, Codex documentation and vendor copies change. This plan embeds research, data model and quickstart to keep the required full-tier artifacts small. No new public interface contract is introduced.

## Validation evidence

The initial Codex regression run was 21 failed and 14 passed. The direct-normalization check then reproduced three failures for blank identities; all 38 Codex cases pass after the adapter change.
The route differential uses archives of 3feedf5c and the implementation head, with the same tests folder. Corpus sha256: de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1. There are 288 routes and 1,152 host cases. No verdict or reason moved. Shell parser combinatorial probes are N.A.; shell parsing is unchanged.

Existing Codex launches remain outside Claude model-table advice. Preserving their message must not change that policy; native model policy belongs to the separate approved item. The first full suite exposed that regression and a fixture prefix rejected by sanitization. Both were corrected, then 103 targeted checks passed with exit 0.

Final verification: `uv run --no-project --with pytest python -m pytest -q` passed with 3,789 tests and seven skips in 244.66 seconds, exit 0. Runtime is 3,754 lines, net +9. `bin/wuwei agents check`, vendor parity and `git diff --check` passed. The final source route differential at fa46883c again had zero moved verdicts or reasons across 1,152 cases.

## Combined native review correction

The review found a credential copied from Model reason into synchronized seat metadata and native paths closed by other sessions. Consumer tests reproduced eight failures, with 39 passes. A further boundary case reproduced one failure when clipping left a credential/canary prefix.

The shared accepted-response branch now redacts recognized credentials and the workspace canary before asked() clips the reason or description is clipped. A local final string-field sanitizer also covers model, effort, session, identity and future string metadata. The requested message remains intact in normalization. Unsupported-role metadata uses the same persistence boundary. Normalization still claims no resolved provider model.

board.running matches stops and unconfirmed rows by session and raw identity. For historical sessionless stops, only non-path legacy ids keep the global fallback. No composite identity is persisted. Native paths require a session match.

The planner authorized board.py as a necessary consumer and reallocated one runtime line for security. Runtime is 3,755 lines, net +10; the 3,800 cap is unchanged. At source fix c450f433, all 48 Codex tests and all 812 focused Codex/model/hook/watch/vendor cases pass (exit 0). The route differential again has 288 routes and 1,152 cases, with zero verdict or reason changes and the same recorded corpus SHA256. No full suite was rerun at this fix head because its slot is allocated to the downstream model-policy item; the earlier 3,789-pass full run predates this correction. CI is unread and the PR remains draft for native delta review.

## Observed native hook spelling correction

The captured PostToolUse schema names collaborationspawn_agent, with object task_name, agent_type and message inputs and a JSON string result. The final owner-authorized fix round accepts exactly that name and the existing spawn_agent spelling in the same dispatch condition. The consumer, response parser, role validation and redaction remain unchanged. No prefix stripping or shell command parser change is involved.

TDD: `uv run --no-project --with pytest python -m pytest -q tests/test_codex.py` reproduced 22 failures with 49 passes before the condition changed, then passed all 71 cases. Coverage includes the actual minimal input shape through normalization and the seat consumer, both identity fields and response encodings, invalid roles and malformed results, and an unsupported collaboration sibling that remains unnormalized.

At source c511fe421d5d7834cc6081f9c672aa3389cebd92, `specs/gates-at-push/route_diff.py` compared archived main 3feedf5ca60ad78ac602cb1a44c165e2aade0263 and head with the same tests. All 288 routes and 1,152 cases retain their verdict and reason, with zero movements. Corpus SHA256 remains de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1. `bin/wuwei agents check` and `git diff --check` pass. Python physical line counts total 3,755 runtime lines; the correction adds zero lines and the vendor hook matches byte for byte. Existing independent PASS evidence at 88f52709 does not cover this changed source; fresh gates remain required.

Focused verification: `uv run --no-project --with pytest python -m pytest -q tests/test_codex.py tests/test_models.py tests/test_hook.py tests/test_watch.py tests/test_charters.py tests/test_setup.py` passed 1,071 tests in 83.86 seconds, exit 0. AUTH PASS: the archived route differential is unchanged. VAL PASS: both proven names retain blank, malformed, unknown-role and boundary handling. TEST PASS, ERR PASS and CON PASS: the captured minimal schema reaches normalization, persisted seat metadata and board.running, while invalid inputs create no seat or attestation. STATE N.A.: the correction changes no shared state operation. INF N.A.: no new secret, environment key or entry point. Shell parser and path-normalization probes are N.A.; neither parser nor paths changed. The full suite was not rerun for this zero-line correction; CI is unread.
