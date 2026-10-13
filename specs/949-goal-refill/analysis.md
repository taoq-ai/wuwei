# Cross-artifact analysis: #949

Specification, plan and tasks reviewed in order before implementation.

| Finding | Severity | Resolution |
| --- | --- | --- |
| Design 5.7 retires intraday intake | HIGH | Issue explicitly reverses it for goal work; spec Assumptions proposes wording without editing owner design. |
| Neither goal completion status nor auto-start threshold exists | HIGH | Spec defines present goals as open and a conservative explicit bar. |
| Fail-closed guard convention conflicts with advisory Stop | HIGH | Issue explicitly requires fail-open and exit-zero Stop; dedicated dispatcher translation. |
| Owner retry could admit changed content | HIGH | Bind card to canonical candidate content; retries dedupe and preserve morning proposal. |

No unresolved CRITICAL or HIGH findings. FR-001/002/003 map to T003/T004,
FR-004/005 to T005, FR-006/007 to T006/T007, FR-008 and cross-cutting checks to T008.

## Implementation evidence
- Initial red: 16 failed, 8 passed in 0.67s. The field reproduction returned close
  rather than refill; propose lacked the refill argument; the shim rejected Stop.
- Additional red checks caught missing never-auto path routing, active-queue refusal,
  and tracker candidate lookup, then passed after the shared fixes.
- Independent read-only review found one P1: an unapproved morning candidate could
  override the same ID admitted by refill. A regression failed, then passed after
  admitted refill candidates took precedence in dispatch.candidate.
- Root review also reproduced absent merge risk evidence and a tracker symlink
  regression. Reusing plan.approved and preserving the shared reader's symlink check
  resolved both without adding consumer-specific refill logic.
- Delta review: no blocking findings. Reviewer independently ran the 37 issue tests
  and fake-adapter checks of merge, metrics, telemetry and candidate precedence.
- Issue tests: 37 passed in 0.38s.
- Contract/focused checks: 129 passed in 9.46s (including stdlib and manifest checks).
- Stop timing: 25 real shim invocations on a synthetic exhausted day, each with a
  new next.action and a blocking refill row: median 29.9 ms, p95 31.1 ms wall time.
  No adapters or network were needed; no production workspace was used.
- Final affected-file validation: 5422 passed in 212.40s (0:03:32). All 73 files
  selected by rg imports, verified against AST imports, plus stdlib and manifest
  checks were passed as 75 explicit pytest file arguments with cacheprovider
  disabled. No bare suite was run.
- Final diff check passed. No unresolved blocking findings or unfinished tasks.
- Compatibility tests updated for Stop's fail-open contract and numbered lead JSON
  in the simulated day walker. Owner-only design and constitution remain unchanged.

## Review follow-up analysis before implementation

Prior implementation evidence above is historical. The owner authorized this correction.

| Finding | Severity | Planned resolution |
| --- | --- | --- |
| H1 self-generated progress | HIGH | R002/R003: signature under active Stop plus daily cap; no next.action counter. |
| H2 unbounded refill | HIGH | R002/R004/R005: count default 3 and approved envelope.end; report reason. |
| H3 missing event tiers | HIGH | R002/R003: stop_blocked silent, stop_error warn; keep plan.approved silent. |
| M1 stale global owner wait | MEDIUM | R003 deletes request producer and pending_owner. |
| M2 owner design contradiction | MEDIUM | R001 exact paragraph and table replacements proposed only in spec. |
| M3 oversized commands | MEDIUM | R002/R004 references lead inputs. |
| M4 unresolved repos abort batch | MEDIUM | R002/R004 route only affected candidates to card. |
| M5 incomplete automatic bar | MEDIUM | R002/R004 require build and non-empty safe paths. |
| L2 approved goal scope | LOW | R002/R004 day snapshot and approved IDs, never expand scope. |
| L3 stale no-work goals | LOW | R002/R005 last refill only. |
| L4 answer spent before admission write | LOW | Deferred: shared transactional approval redesign exceeds small correction. |

All CRITICAL/HIGH design ambiguities resolved before implementation; final evidence follows.
FR-001/002/003/004 map to R004, FR-005 to R005, FR-006/007/008 to R003.
R002 and R006 cover all changed behaviors. No uncovered review requirement.


## Review correction evidence

- Regression red: 33 failed, 122 passed in 2.24s. Corrected invalid review/measure
  fixtures then observed the automatic-admission failures with valid candidate data.
- Large-command regression against the prior next implementation: 1 failed,
  57 deselected in 0.26s; the emitted command had 31,286 characters.
- Signal, refill and config checks after correction: 337 passed in 10.32s.
- Hashed-signature regression: 4 failed, 56 deselected in 0.66s before hashing.
  Final issue and signal checks: 157 passed in 4.25s.
- Requested full suite, with eight workers and cacheprovider disabled, completed:
  4 failed, 7646 passed in 137.27s (0:02:17). No init hang or deselection.
  The four failures were two missing public config documentation entries and two
  exact assertions of the previous guards defaults. Both documentation entries and
  both expectations were corrected. No runtime failure occurred in the full suite.
- Read-only delta review reproduced two boundary gaps: starting a new refill number
  while one card was pending bypassed the count cap; discovery crossing envelope.end
  still admitted work. Regressions failed: 2 failed, 60 deselected in 0.27s. The shared
  propose path now refuses a new pass while pending, and its state update rechecks
  the deadline before admission. Independent verification: 4 passed in 0.24s.
- Full-suite failure files plus refill regressions after correction:
  200 passed in 12.15s. H1/H2/H3, M1 through M5, L2 and L3 are resolved. L1 is H3.
  L4 remains the explicitly permitted low-priority deferral in the feature spec.
- Final affected-file validation: 5307 passed in 91.23s (0:01:31). Imports located
  with rg and checked with AST imports; 74 explicitly named files include contracts
  and public documentation. The complete suite was run once; all its failing files
  passed after correction. No tests were deselected.
- Delta reviewer confirmed both boundary findings closed. No open CRITICAL or HIGH
  findings. Diff check passed; no absolute local paths or em dashes were added.
  Owner design and constitution are unchanged; all follow-up changes are uncommitted.

## Round 2 analysis
R2-H1: HIGH, resolved design assumption before implementation: the shared bound check
accepts ISO datetime or time-only values and ignores unparseable deadlines. S002/S003
cover next and report. R2-L1/L2: S002/S003 remove unused imports and make the cap visible
once per day, with warn classification. S004 covers all consumers. No unresolved
CRITICAL/HIGH design questions; implementation and validation completed below. L4 stays deferred.

Round 2 red evidence: 8 failed, 159 passed in 4.12s for the initial format and cap
checks. Splitting next/report assertions confirmed both read paths independently:
10 failed, 2 passed, 64 deselected in 13.90s. The HH:MM cases already passed.
After the shared fix: 574 passed in 12.84s across refill, signal, next, report and
hook tests. Final importing-file validation: 1802 passed in 205.17s (0:03:25),
24 explicit test files selected with rg and AST import checks, plus the requested
signal, report and next tests and relevant contracts. No new module or owner-design
change; the warning uses the existing 50 ms hook event-write timeout.

Round 2 complete: shared deadline parsing, one-time cap warning and unused imports
resolved. Diff checks passed. Changes remain uncommitted.
