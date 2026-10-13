# Specification Analysis Report: 861-pr-flow-doctor

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | HIGH | Compound Bash text does not match the named command, so the row repeats. | Doctor records the completed check directly after diagnosis; `_seen` consumes that pass. |
| A2 | MEDIUM | Changing shared matching would alter unrelated completion and metrics behavior. | Leave `_ran` and `_matches` unchanged; verify the compound case. |
| A3 | MEDIUM | A doctor hand-over could mark completion in the wrong process. | Append only after `diagnose` in the process that actually runs it. |

CRITICAL 0 open, HIGH 0 open. Requirements map to T001 through T003.
