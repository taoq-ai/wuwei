# Research: test function budget

## Decision: Count with the existing CI expression

The workflow counts source definitions matching `^\s*(?:async )?def test_`. The branch began with 3037 definitions, above the gate of 3000. The selected acceptance target is below 2810.

## Decision: Preserve collected cases

The branch began with 7859 pytest items. Identical test bodies can share a parameter table. Related behavior cases with different assertion shapes can be named scenario functions used as parameter values, so their original bodies and fixture inputs remain intact. Per-file collected counts and a source comparison check for case loss.

## Alternatives considered

Changing the CI cap would leave the requested function budget unmet. Deleting non-identical tests would lose coverage. A broad grouping by common setup was tried and reverted because it mixed unrelated behavior.
