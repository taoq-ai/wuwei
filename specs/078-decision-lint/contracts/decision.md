# Decision record and command contract

Save records as `.wuwei/days/<date>/decisions/D-<positive integer>.md`.
Fields are case-sensitive labels, optionally Markdown headings or bold. Each occurs once.
Question, Recommendation, Confidence, Reversibility and Decided-by are single-line.
Other fields may span lines; trailing Consequences and Notes sections are allowed.
Comments, quotes and fenced examples are ignored. Outer table pipes are optional;
must pass/fail values are case-insensitive.
Tables require exactly the documented columns, unique nonempty ids/criteria and all cells.
Option ids are letters followed by letters, digits, underscores or hyphens.
A baseline option description begins `Do nothing` or `Defer`.

```markdown
Question: Which implementation should we use?
Context: The failing case is recorded in tests/test_example.py.
Options:
| Option | Description |
| --- | --- |
| A | Implement the fix |
| B | Defer until the next item |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| No deployment | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Correctness | 10 | 8 | 2 |
Recommendation: A
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: The regression returns on unusual inputs.
Revisit: When the regression returns.
Decided-by: seat
Outcome: pending
```

Weighted sum is 80 for A and 20 for B. Must failures exclude an option; ties are allowed.
Confidence is high, medium or low; Decided-by is seat or owner. Reversibility is one-way,
two-way or unsure (owner). Only own branch and own PR qualify as local blast radius.
Additional blast-radius text routes to owner, including scope agreed with others.

- `bin/wuwei decision lint <file>`: 0 valid, 1 invalid, 2 unreadable or persistence failure.
- `bin/wuwei decision route <id>`: lint today's record, print seat or owner; a seat route
  records the recommendation as its outcome in state and a decision.decided event.
- `check_question(payload)`: shared guard check, each question text must cite one or more
  D-n ids, all existing today and passing lint. M5 may pass `tool_input.question`.
  Morning gates and C-n clarification records are exempt from full decision scoring as
  specified in spec.md. Citation failures give feedback without rejection events.
  AskUserQuestion uses `tool_input.questions[*].question`; metadata cannot supply citations.

Guard checks use 0 clean, 1 findings, 2 unable to inspect. The hook command translates
both 1 and 2 to exit 2. File-tool rejections and named Bash targets append decision.rejected
with file/reasons; Bash day scans only give feedback. The generic event command reserves
all decision. kinds. Owner outcome production is deferred to the answer hook or M5.
Generic state setters and callback writers cannot change decision_outcomes at any depth.
