# Specification Analysis Report

Analyzed after tasks, before implementation, 2026-10-13.

## Findings

No open CRITICAL or HIGH findings. The narrow #839 exception is explicitly required
by issue #960 and recorded as proposed design wording, without editing owner files.
The direct caller check uses the issue's documented fallback, not a claim of parent
authentication. Explicit affected tests follow the user's instruction over the
constitution's generic full-suite wording.

## Coverage

| Requirement | Tasks | Coverage |
| --- | --- | --- |
| FR-001 | T003, T004 | Field cases, options, wrappers, paths, outside cwd |
| FR-002 | T003, T004 | Word fallback before generic log-only reason |
| FR-003 | T005 | Parsed text and unrelated unsupported syntax |
| FR-004 | T002, T005 | Caller evidence and configured shim replay |
| FR-005 | T004, T006 | Shared guard, no new subsystem or state |
| SC-001 | T003, T004 | Full-pipeline deny and refusal records |
| SC-002 | T005, T006 | Offline explicit affected files |

Five requirements, six tasks, 100 percent requirement coverage. No unmapped tasks,
ambiguities or duplication findings. No new schema or dependencies.

## Checklist and implementation gate

Built-in requirements checklist: seven of seven pass. The custom security checklist
is left for the reviewer. Proceed under the user's explicit instruction to complete
implementation without questions; unchecked custom review items do not withdraw
that authorization. No extension hooks are configured.

## Verification results

Initial red (new tests, before runtime changes):

```text
24 failed, 12 passed, 668 deselected in 0.59s
```

Both field cases and 22 related forms returned 0 instead of 2. The compatibility
controls passed. First green:

```text
36 passed, 668 deselected in 0.48s
1424 passed in 26.64s
```

Review found one HIGH issue: _wuwei_action stopped at separate Python option
values before -m. Four additional full-pipeline cases reproduced it, then the
existing helper was fixed in the permitted single fix round:

```text
4 failed, 36 passed, 668 deselected in 1.26s
40 passed, 668 deselected in 0.56s
```

Final affected-file run:

```text
1428 passed in 46.59s
```

Command arguments, using the task's assigned pipeline interpreter from the worktree root:

```text
-m pytest -q -p no:cacheprovider tests/test_protect_state.py tests/test_hooks.py tests/test_canary.py tests/test_enforce.py tests/test_env_credentials.py tests/test_goals_rank.py tests/test_guard_mutation.py tests/test_integrity.py tests/test_invariants.py tests/test_owner_edits.py tests/test_promotion.py tests/test_scope_first.py tests/test_tone.py
```

These are all files returned by searching tests/ for protect_state, including every
direct importer and the discovery, enforcement, scope and mutation checks. Tests
exercise local fixtures and fakes, with no network or real GitHub calls.

Independent delta review: no blocking findings; reviewer also reran the 40 focused
cases successfully. The single HIGH review finding is resolved. Runtime changes
remain in one existing module, with no new helper, parser, dependency or state.
`git diff --check` passed. All six tasks are complete; changes are uncommitted.

## Remaining limitations

No authenticated parent check was added, using the issue's explicit fallback.
The unparsed check is intentionally a literal whole-word check, not a shell
interpreter or sandbox for obfuscated programs. Custom security checklist markers
remain reviewer-owned; the implementation and code review are complete.

## Review follow-up analysis, before implementation

The subsequent attack harness found F1-F3 HIGH, F3b-F4 MEDIUM and F5 LOW gaps in
the earlier delta review. The earlier completion verdict above is historical.
FR-006 and T008-T009 cover variables, launcher case, Python clusters and arbitrary
program/event pairs. FR-007 and T008-T009 cover split words and inline code/aliases.
FR-003 compatibility controls and T010 cover every ordinary harness row and all
affected test files. F6 is a separate deferred issue recorded in Assumptions.

No specification CRITICAL or HIGH findings remain: the user's explicit follow-up
defines the broader matching rules and authorizes this fix round. Implementation
findings remain open until the new regression tests pass. No new parser, dependency,
state, hook entry point or owner prompt is planned.

Review follow-up red, before guard edits:

```text
39 failed, 56 passed, 668 deselected in 4.80s
```

Each new attack failed because the hook pipeline returned 0 instead of 2. All
compatibility controls passed. After F1-F5 fixes, the same focused selection:

```text
95 passed, 668 deselected in 4.31s
```

The pipeline asserts deny output, a protect_state refusal record, unchanged state
and no gate.asked record. Cases without an event verify mixed-case launchers and
Python short-option clusters independently of the adjacent-pair rule. All four
known event names are covered for a renamed launcher. F5 covers Python, Perl, Node
and both separate and attached git -c aliases, with ordinary snippet controls.
Harness plugin paths use portable relative fixtures; submitted Bash is never run.

The built-in requirements checklist remains seven of seven passed. Custom security
checklist: nine reviewer-owned unchecked criteria. As in the original gate, the
explicit instruction to apply the review fixes without questions authorizes work;
their markers remain untouched by implementation. No extension hooks are configured.

Final review follow-up run, using the pipeline Python 3.12.13 interpreter and the
same thirteen explicit filenames listed above:

```text
1483 passed in 112.50s (0:01:52)
```

The importer search confirms every Python test importing protect_state is included.
Manual delta review checked all six requested changes against the implementation:
F1-F4 and F5 are fixed, F6 remains a documented static-analysis limit and a separate
follow-up pending filing. No open blocking finding remains in this requested delta.
The existing legitimate hook, enforcement, mutation and invariant tests passed.
`git diff --check` passed. All ten tasks are complete; changes remain uncommitted.
