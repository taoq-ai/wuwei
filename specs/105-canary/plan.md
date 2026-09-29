# Implementation Plan: Prompt canary and honeytoken

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests. Extend existing init,
agent renderer, outward checks, trace recorder, state protection and event writer.
No new adapter, dependency or subprocess in core.

## Design

Add `cli/wuwei/security.py` for initialization, validated secret loading, exact
matching, recursive replacement, and reserved redacted page/scanner evidence.
Store secrets in `.wuwei/security.json` at mode 0400. Use an init option for the
relative honeytoken path, persisted in security material. The template enables
security so a missing file cannot silently disable a new workspace's detection.
Exclude private generated artifacts and marker files with workspace git ignores.

Extend `agents build` to render workspace copies with a never-repeat line, retaining
source-only generation outside a workspace. Include local charter overrides.
Brief headers and runtime charter selection point to generated instructions.

Run security checks before outbound classification and style policy. Reuse the
existing PR guard for literal gh outbound arguments and file-backed bodies. Pass workspace
context explicitly into lint. Reuse the trace recorder; inspect response content
without persisting it, exempt exact generated instruction reads, then redact the entire payload before selecting span fields.
Use shared scope and shell relevance helpers before parsing literal read operands.
Record security findings in trace attributes and append reserved events without
raw paths, tool arguments or token values. Protect secrets and generated artifacts
through the existing state guard. Reserve security/scanner event namespaces and
security state fields without treating them as owner authorization.

## Constitution Check

Stdlib only; test first; existing atomic writer and locked append; scoped guards;
0/1/2 exits; no new external tools; source-only golden generation preserved.
No constitutional exceptions.

## Validation

Use temporary workspaces and in-process commands. Tests generate their own tokens.
Verify independent init values, path validation, generated surfaces, outbound
profiles and adapter hooks, fetched content, read aliases, redaction, reserved
writers, missing material and outside scope. Run the task-specified full pytest
suite and check changed files for forbidden typography and local machine paths.

## Deferred

ZIRAN execution remains with the scanner integration. This issue produces its
local scanner findings and trace attributes without claiming a full scan ran.
