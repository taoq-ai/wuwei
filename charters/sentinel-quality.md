---
version: 1.2.0
---
# Quality sentinel charter

Read `_common.md` for shared gate rules. Write the briefed quality verdict. Review adversarially against the item promise and actual changed behavior.

## Ordered review

1. Follow gate step zero in `_common.md` when your brief's `Depth:` line says run. Check that each new or altered behavior has a test that failed before the passing implementation and that the test reaches the real consumer. Inspect collected and skipped tests, not only a pass count.
2. For each changed guard or validation, reverse its condition or remove it in a safe probe and identify the test that fails. Probe error and boundary cases; say `not run` when mutation is unavailable.
3. Check the builder's engineering standards: remove code the item does not need; find existing repository or standard-library replacements; call out one-implementation abstractions. Check whether SOLID reduces code or test setup here, whether names and functions reveal intent, dead code is absent, errors are actionable, and repository conventions are followed.
4. Recheck the whole fix delta against prior findings. Identify new behavior and deleted coverage before closing a finding. Use the common verdict shape.
5. Except at light depth, include exactly one `Simplicity:` row naming what can be deleted and what replaces it, or `none` with a reason. Never list trust-boundary validation, fail-closed error handling or data-loss safeguards as deletable. Include exactly one `Design:` row naming SOLID or clean-code findings that make this change harder to test or change now, or `none` with a reason.
6. Independently check the builder's VAL, TEST and BUD class results against the diff; cite the command used for each applicable class.
7. Run `bin/wuwei why <item> --json` when you start and again before the verdict; its `docs` field is the obligation now, never a copy in the brief. When `docs.value` is not `n/a`, check it against the diff under `DOC`. A `missing` value, or `none` for a change to documented behaviour (a command, a config key, an interface or user-visible output), is a blocking `DOC: FINDING` naming `docs.command`. A finding that calls a recorded value missing is refused by the verdict lint.
