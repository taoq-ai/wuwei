# Specification Analysis Report: 616-guard-false-refusals

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 4.1, 4.5, 9.1 and 9.2, issue #616 and the code on `main` at 082e1c6 (v0.23.0
plus #607).

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Invariants | HIGH | constitution Workflow, design 9.2 | Both items change a guard rule, which needs a 9.2 row and a check in `tests/test_invariants.py`; the design spec is owner-only and `test_table_matches_the_checks` requires the table and `INVARIANTS` to match. | Resolved as #556 and #557 did: the checks are pinned as `test_invariant_*` tests in `tests/test_vcs.py` and `tests/test_verdict.py`; rows I25 and I26 are raised with proposed text (spec, Design spec conflict) and moving them into `INVARIANTS` is Deferred until the owner adds the rows. |
| A2 | Security | HIGH | plan `push_commits` | Skipping commits on remote-tracking refs trusts local refs a seat can write (`git update-ref refs/remotes/...`). | Resolved: not a new trust. The range base is already the destination's or default branch's tracking ref, so a forged ref already shortens the range today; design 9.1 says no local file is a boundary, and 4.5 anchors publishing in protected refs and credentials. A foreign-identity commit on no remote is still refused (T001). |
| A3 | Security | MEDIUM | plan `check_write`, `role=''` | A quality seat writing a generically named gate through Bash is no longer held to the quality rules at write time. | Resolved: SubagentStop lints the seat's own gate file with the stopping seat's role, so the quality rules apply before the verdict is received; the Write/Edit path keeps the caller's role. |
| A4 | Blast radius | MEDIUM | `shell.READ_ONLY` | The set is read by the classifier (I10, `unread`), `protect_state` readers and write-target scan. | Resolved: each user reviewed (plan, Users of READ_ONLY); a checksum tool writes nothing and runs nothing, so every user's answer is the correct one. `security.reads_honeytoken` keeps its own list; a digest does not disclose the file. |
| A5 | Correctness | LOW | plan, early return order | The read-only return runs before the interpreter-snippet refusal. | Accepted: `classify` never marks inline interpreter code read-only, so the refusal still runs; `test_bash_relevance_and_opaque_commands` covers it unchanged. |
| A6 | False positives | LOW | spec Clarifications | A Bash write elsewhere whose text names `gate-` still lints every gate of the day. | Accepted: the written target cannot always be read from shell text; the request scopes the fix to reads and the role. |
| A7 | Tests | LOW | `tests/test_verdict.py` | Two scan tests use a bare `echo` as the trigger, which is now a read. | Resolved: changed deliberately to `echo ... > out.txt` (T005). |
| A8 | Replay | LOW | `tests/test_vcs_guard.py` | Replay steps match argv tokens; the range token is unchanged. | Resolved: they keep passing; one assertion pins the new argv tail (T001). |
| A9 | Coverage | LOW | `push_check` HEAD row | A fast-forward merge leaves HEAD on GitHub's commit, which the HEAD identity row still refuses. | Deferred as a follow-up issue linked to #616 (spec, Deferred); the reported case is a merge commit. |

No CRITICAL finding. HIGH findings A1 and A2 are resolved above.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T002 |
| FR-002 | T001 |
| FR-003 | T005, T006 |
| FR-004 | T005, T006 |
| FR-005 | T003, T004 |
| FR-006 | T001, T005 |
