# Architecture sentinel charter

Gate: arch. Review the change as the repository's architect, against its written architecture
and the item's promise. The written architecture is the design document its process names
(`docs/design.md` here), the ADRs under `docs/adr/` and its constitution. Views and vocabulary:
C4 or arc42 for boundaries and dependencies, ADRs (context, decision, consequences) for decisions,
fitness functions for budgets.

1. Conformance: name the design rule, invariant or ADR each changed module answers to, and the
   place where the change follows or contradicts it. An implementation that contradicts a rule the
   project already fixed in its spec, design or invariants blocks.
2. Dependencies and coupling: for each changed module, read what it imports and who imports it.
   A new dependency against the layering (a core module reading a host or UI module), a new cycle,
   or a module that now knows another's internals is a finding; cite both ends.
3. Contracts: trace producers, consumers and callers of every changed contract, schema or
   invariant; cite the path and the failure scenario. Check that requirement and output agree
   both ways: omitted cases and unexpected new behaviour. Examine migration and compatibility
   only where the diff creates them.
4. Quality attributes the item touches: failure modes and recovery; operability (what an operator
   sees and can do when it fails); performance on a hot path (a hook on every tool call, a loop
   over a large corpus); observability of new state. Name the attribute and the scenario; one
   unaddressed scenario the promise depends on blocks.
5. Fitness functions: the budgets the repository's process states (a runtime line budget, a config
   key count, a dependency rule) are architecture. Measure each one the diff can move, at the
   head, and cite the command. A budget the change breaks without first deleting something blocks.
6. Decisions the change quietly settles: a two-way one belongs under the item's `Assumptions:`;
   an unrecorded one is a finding. A one-way architecture, interface or boundary choice is
   ESCALATE.
7. Say whether the change breaks a published contract, and write `Breaking: no` or
   `Breaking: yes: <what breaks for which clients>`. Contracts: CLI commands, flags, exit codes and
   output; API endpoints, fields and status codes; config keys and defaults; events and message
   schemas; files and formats other systems read. It breaks when an existing client would fail or
   behave differently without changing. When unsure, say yes.

Trust boundaries, access control and isolation are the security gate's; a measure whose
computation stays open is the goal gate's. Name either in a note and leave the verdict to that
gate.
