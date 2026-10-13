# Implementation Plan: Hook invocation guard (#960)

## Summary

Fix both bypasses in the existing shared `protect_state.check_bash` guard.
Keep shell parsing, hook entry points, state schemas and owner workflows unchanged.

## Technical Context

Python 3.11+ stdlib runtime; pytest development tests. One runtime module,
`cli/wuwei/guards/protect_state.py`, and its existing regression test file.
Full-pipeline tests call real discovery, enforcement and refusal recording without
executing submitted Bash. Existing shim replay tests exercise legitimate hooks.

## Root Cause

Before changes, `cli/wuwei/guards/protect_state.py:304` catches ParseError and
returns without inspecting hook invocations. `shell.py:247` rejects the reported
command substitution. `commands/hook.py:295` makes generic UNPARSED refusals log-only.
At `protect_state.py:317`, the matcher tests only the first returned action word,
where `_wuwei_action` leaves global arguments intact. The leading `--workspace`
option is consumed by the real CLI at `cli/wuwei/__main__.py:37`, hiding hook from
the guard. The root-present condition also misses calls selecting a workspace
from an outside cwd even when the hook dispatcher has established scope.

## Constitution Check

- Stdlib only; no new runtime module or dependency.
- Red tests before runtime edits, then targeted tests and review.
- One shared check for all Bash callers, including terminal normalization.
- Preserve 0/1/2 exits and existing denial/event output.
- Task explicitly narrows #839 for the hook-forgery pattern. Proposed design
  wording is in spec Assumptions; owner-only design is untouched.
- Task explicitly requests affected files instead of the bare suite, and forbids
  commits, pushes, stash and GitHub commands. Leave working tree changes.

## Design

1. On ParseError, detect wuwei and hook as whole words before generic unparsed
   handling. Return the same specific refusal as parsed hook invocations.
2. After existing wrapper normalization and `_wuwei_action`, skip leading options,
   consuming the value of --workspace, before testing the subcommand. Stop at the
   first non-option so text operands of other subcommands remain data.
3. Apply hook detection whenever this guard is selected. The dispatcher already
   scopes calls to workspaces, including explicit workspace operands from outside.
4. Keep one shared reason constant. Do not expand the shell grammar.
5. Consume Python interpreter option values (-W, -X and --check-hash-based-pycs)
   in the existing _wuwei_action helper before locating -m, including combined
   no-argument switches. This closes the review finding without a new parser.
6. Preserve the hook CLI without a forgeable parent check; rationale in research.md.
7. Review F1-F4: lower-case launcher names, accept short-option clusters ending in
   m, normalize quotes/backslashes for fallback word checks, and refuse adjacent
   hook-or-variable/event argv pairs for every program. Reuse guards.EVENTS.
8. Review F5: share the fallback word check with inline-code arguments detected by
   shell.inline_code and git -c alias values. Do not evaluate code or read scripts.
9. Port the review harness's F1-F4 and ordinary rows into the existing pipeline
   tables; add F5 checks and ordinary inline-code controls before runtime edits.

## Verification

Use the task's pipeline interpreter with `-m pytest -q -p no:cacheprovider` and
explicit filenames. First run new full-pipeline field regressions and observe
expected allow-versus-deny failures. Then run every test file importing the changed
module, plus hooks, enforcement, mutation, invariant, scope and tone coverage.
All commands/payloads use temporary fixtures; submitted malicious Bash is never run.

## Structure and Complexity

No schema migration, new module, service or parser. Relevant contracts and data
remain as documented in data-model.md and contracts/hooks.md. All tasks execute
sequentially because the fix and tests share a single behavior.
