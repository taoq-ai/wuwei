# Research

- Decision: fix api and command_result inside edges.py. Root causes before edits: line 556 checks deployment/environment paths before methods; line 615 omits env ls; line 653 omits binding in card detail. All publish checks route through check_deploy and command_result; gh routes through api.
- Rationale: reuse _scan and GH_VALUED for spaced, attached and equals options. A local GET-only predicate avoids changing existing release/ref rules.
- Alternative rejected: broad early return for all reads would skip explicit deny rules or sibling writes in compounds.
- Decision: change publish card detail at the existing needs_owner call; do not change all owner cards or approval identity.
- Existing #939 done behavior in closing.py, report.py and dispatch.py needs no changes for this guard-only issue.
- No graphify graph is present. Focused source tracing avoids generating an unrelated subsystem or local-path artifacts.

- Review refinement: reject unparsed short clusters conservatively and return immediately for a recognized safe deployment/environment read, preventing workflow-word collisions in environment names.

- Follow-up F1 root cause: GH_VALUED omitted --preview; api returned clean on multiple operands before inspecting paths. Reuse the existing scanner, parse each target path once, and deny ambiguous deployment/environment targets.
- Follow-up F3 root cause: the deployment/environment safe-read predicate ignored header values. Reuse scanned -H/--header values for a conservative case-insensitive override check.
- F2 and F4 require owner decisions, as explicitly instructed; no init migration or design edit is part of the implementation.
