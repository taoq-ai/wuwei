# Implementation plan

Python 3.11 stdlib only. Change hook.codex and its post-tool consumer, preserving Agent semantics for supported launches.

## Research and data model

The 2026-10-27 sanitized native probe found agent_type input and a JSON task_name output. Legacy tests use agent_id. Decode an object structurally instead of searching serialized text. Normalize message to prompt and reasoning_effort to effort. Requested model remains asked; resolvedModel is not synthesized. Existing agents.TABLE validates explicit role names. No alternative native role field has evidence.

A successful known-role response becomes Agent with agentId. Missing role becomes an unconfirmed dispatch carrying agentId and a precise role-capability diagnostic. Invalid identity raises a diagnostic caught by the existing hook.error path. Neither path attests work.

## Constitution check

Stdlib only; no new dependencies, config, doors or attestation. Tests precede runtime edits. Runtime delta stays at most nine lines. Vendor copies remain identical. No shell command parser changes.

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
