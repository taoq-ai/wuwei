# Specification analysis: 1068 guards multi-line

| ID | Category | Severity | Location | Summary | Status |
|----|----------|----------|----------|---------|--------|
| A1 | Coverage | LOW | spec.md Edge cases | A heredoc piped into a shell (`cat <<EOF \| sh`) is not read as commands. Not a regression: main does not read it either. | Out of scope, recorded |
| A2 | Coverage | HIGH | guards.py `_lines` | Two heredocs on one line, the first unquoted with `$(`, the second quoted: the second body covered the first (gate finding at ee252d7). | Resolved in fix round 1: bodies read in order, test added |
| A4 | Coverage | HIGH | guards.py `_lines` | An arithmetic `<<` (`$((1<<EOF))`, `(( x = 1 << EOF ))`) started a heredoc and hid the next line (gate finding at ee252d7). | Resolved in fix round 1: no heredoc inside `((`, tests added |
| A6 | Coverage | HIGH | guards.py `_lines` | The round 1 arithmetic check counted raw text, so a quoted or commented `))` cancelled a real `((` (gate finding at 1450f8d). | Resolved in fix round 2: depth tracked in the scan loop, four tests added |
| A7 | Coverage | HIGH | guards.py `_lines` | The round 2 depth counter mis-paired `))` (`$(((1)) <<EOF )`, `$(( (1+(2)) <<EOF ))`, `$(( $(echo $(echo 1))<<EOF ))`), and `$[`, `${` and `a[` were untracked (gate findings at 7fd4019). | Resolved in the redesign: one-way flag, seven refusing tests |
| A8 | Consistency | LOW | spec.md Edge cases | A heredoc whose body names a door after a closed `$((..))` or `${..}` is refused. | Accepted cost, pinned by a test |
| A9 | Coverage | HIGH | guards.py `OPENER` | A compound-array subscript (`a=( [1<<EOF ]=x )`), an extglob group and an opener split by a backslash-newline did not set the flag (gate findings at 4be5260). | Resolved in redesign fix round 1: `=(` and extglob openers, read from the emitted text, tests added |
| A10 | Consistency | HIGH | guards.py `segments` | shlex merged a closing backtick with `;` into one token outside CONTROL (gate finding at 4be5260). | Resolved in redesign fix round 1: any token of `();|&` and backticks separates, tests added |
| A11 | Coverage | HIGH | guards.py `_lines` | An unquoted body joined by a backslash-newline (`$\` newline `(`, `EO\` newline `F`) was dropped (gate finding at 4be5260). | Resolved in redesign fix round 1: such a body is read as commands, tests added |
| A12 | Coverage | MEDIUM | guards.py `_lines`, `bash` | A `#` inside `${...}`, `RecursionError` from deep nesting, and a quadratic rescan of unterminated heredocs (gate findings at 4be5260). | Resolved in redesign fix round 1: tests added |
| A13 | Consistency | LOW | spec.md Assumptions | `=(` sets the flag, so `a=(1 2)` stops later body dropping; `[[` sets it too. | Accepted cost, recorded |
| A14 | Coverage | HIGH | guards.py `_lines` | A `#` right after a `)` that closes `$( )` or `<( )` was read as a comment and hid the rest of the line (gate finding at 1647e2e). | Resolved in redesign fix round 2: `)` starts no comment, four tests added |
| A15 | Coverage | MEDIUM | guards.py `bash` | `RecursionError` was refused only when the raw text named a door (gate finding at 1647e2e). | Resolved in redesign fix round 2: always refused, tests added |
| A5 | Coverage | MEDIUM | tests/test_guards.py | Quote closing, the single-quote backslash rule, the join without a space, and four DOORS words had no test that a reversed guard fails. | Resolved in fix round 1: tests added, mutants killed |
| A3 | Consistency | LOW | spec.md FR-004 | The raw-text door pattern is broad. It meets only unreadable commands, so it fails closed. | Accepted |

Coverage: FR-001 to FR-006 each map to a task (T001 to T007) and to at least one test.
No CRITICAL or HIGH finding.
