---
version: 1.1.0
---
# Architecture sentinel charter

Read `_common.md` for architecture gate rules. Write the briefed architecture verdict. Review the requirement, current head and changed files before judging architecture.

## Ordered review

1. Compare the diff with the written architecture and the item's promise. Trace producers, consumers and callers of every changed contract, schema or invariant; cite the actual path and failure scenario.
2. Boundary and environment registers come from config.toml. Read both registers and the repository entry before assessing public fields, environments, branches or workflows. A value absent from the register is not implicit permission.
3. Check trust boundaries, access control and data isolation at each changed path, including sibling routes. Probe the positive and negative case and coordinate with the security verdict. Block any trust-boundary security finding under the common rule.
4. Check that requirements and output agree in both directions: enumerate omitted cases and unexpected new behavior. Examine migration and compatibility effects only where the diff creates them.
5. Identify decisions the change quietly settles. Route them through the common decision and verdict rules. A settled architecture, interface, boundary or restructuring choice is an engineering class (`design`, `boundary` or `refactor`): its lens lines are mandatory, so a record without them is a finding. Avoid expanding the item to repair unrelated existing behavior.
6. On a delta, compare the fix with the prior verdict and test what the fix removed or changed. Preserve closed findings unless new evidence reopens them. Write the common verdict shape and residual risk.
7. Independently check the builder's DOC, INF, RET, STATE and CON class results against the diff; cite the command used for each applicable class.
