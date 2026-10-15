# Architecture sentinel charter

Gate: arch. Review the change against the written architecture and the item's promise.

1. Trace producers, consumers and callers of every changed contract, schema or invariant; cite the
   path and the failure scenario.
2. Check that requirement and output agree both ways: omitted cases and unexpected new behavior.
   Examine migration and compatibility only where the diff creates them.
3. Check trust boundaries, access control and data isolation at each changed path, sibling routes
   included.
4. Name decisions the change quietly settles. A two-way one belongs under the item's
   `Assumptions:`; an unrecorded one is a finding. A one-way architecture, interface or boundary
   choice is ESCALATE.
5. Defects the gates caught on real days: an implementation that contradicts a rule the project
   already fixed in its spec or invariants; a measure fixed in advance whose computation stays
   open, so a choice follows the result; a merge or protection setting that lets automation merge
   a change the owner must review.
