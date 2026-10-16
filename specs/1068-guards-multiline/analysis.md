# Specification analysis: 1068 guards multi-line

| ID | Category | Severity | Location | Summary | Status |
|----|----------|----------|----------|---------|--------|
| A1 | Coverage | LOW | spec.md Edge cases | A heredoc piped into a shell (`cat <<EOF \| sh`) is not read as commands. Not a regression: main does not read it either. | Out of scope, recorded |
| A2 | Coverage | LOW | spec.md Assumptions | Two heredocs on one line, the first unquoted with `$(`, the second quoted: the second body may cover the first. | Accepted, recorded |
| A3 | Consistency | LOW | spec.md FR-004 | The raw-text door pattern is broad. It meets only unreadable commands, so it fails closed. | Accepted |

Coverage: FR-001 to FR-006 each map to a task (T001 to T007) and to at least one test.
No CRITICAL or HIGH finding.
