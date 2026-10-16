# Specification analysis: 1068 guards multi-line

| ID | Category | Severity | Location | Summary | Status |
|----|----------|----------|----------|---------|--------|
| A1 | Coverage | LOW | spec.md Edge cases | A heredoc piped into a shell (`cat <<EOF \| sh`) is not read as commands. Not a regression: main does not read it either. | Out of scope, recorded |
| A2 | Coverage | HIGH | guards.py `_lines` | Two heredocs on one line, the first unquoted with `$(`, the second quoted: the second body covered the first (gate finding at ee252d7). | Resolved in fix round 1: bodies read in order, test added |
| A4 | Coverage | HIGH | guards.py `_lines` | An arithmetic `<<` (`$((1<<EOF))`, `(( x = 1 << EOF ))`) started a heredoc and hid the next line (gate finding at ee252d7). | Resolved in fix round 1: no heredoc inside `((`, tests added |
| A5 | Coverage | MEDIUM | tests/test_guards.py | Quote closing, the single-quote backslash rule, the join without a space, and four DOORS words had no test that a reversed guard fails. | Resolved in fix round 1: tests added, mutants killed |
| A3 | Consistency | LOW | spec.md FR-004 | The raw-text door pattern is broad. It meets only unreadable commands, so it fails closed. | Accepted |

Coverage: FR-001 to FR-006 each map to a task (T001 to T007) and to at least one test.
No CRITICAL or HIGH finding.
