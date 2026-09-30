# Feature Specification: Hooks are cooperative mistake prevention; publication policy is enforced where changes land

**Feature Branch**: `237-spec-guard-boundaries`
**Created**: 2026-09-30
**Status**: Ready for implementation (the amendment text is already in the working tree)
**Input**: Issue #237, spec(guards). Design sections 4.5, 4.6, 4.7, 9.1 and 10;
`docs/site/security.md`; `docs/integrity.md`; the constitution's cycle budget. Evidence:
the whole-system review of 2026-09-30 (point 2, agreed by the owner as a spec change
first) and the #222 review notes (six rounds).

## Root cause (read on main, 7c2bb20)

This is a spec defect, not a runtime one. The documents disagree about what a hook
guarantees, and the disagreement drove the #222 cycle.

- `docs/specs/2026-09-24-wuwei-design.md:239-248` (4.5 before this change): every Bash
  guard must normalise every wrapper form, with no split between what the parser protects
  and what it cannot. It then calls the `pre-push` git hook and `permissions.deny` "a
  second anchor that does not depend on parsing", which reads as a second boundary.
- `docs/specs/2026-09-24-wuwei-design.md:775-796` (9.1 before this change) says the guards
  defend only against mistakes, corner-cutting and prompt-injected actions, and that hard
  boundaries sit outside the owner's account. Its list of hard boundaries omits the
  credential layout, and it calls the same git hooks "local anchors".
- `docs/site/security.md:48` repeats 9.1's list, also without credentials, and never says
  what a guard does for push, merge, deploy and approval.
- `.specify/memory/constitution.md:74` sets the cycle budget (one fix round plus one delta
  review) with no consequence. #222 then took six rounds (review notes r1 to r6: reader
  carve-outs leaked through pipes, then redirects, then subshells, then wrappers) because
  4.5 made the parser the guarantee, so every leak was a blocking security finding.
- The v0.6.0 dry run (devcmds probe) shows the cost on the other side: `x=$(pwd); echo $x`
  and `python3 -m pytest -q && git status` were refused with exit 2 inside a workspace.
  #234 fixed those forms; the spec still asked for the approach that produced them.
- Design section 10 has no release criterion beyond the suite; 13 asks for one real owner
  day before v1 but says nothing about later releases.

## User Scenarios & Testing

### User Story 1 - One statement of what a hook guarantees (Priority: P1)

A reviewer, builder or owner reads 4.5, 9.1 or the security page and gets the same answer:
Bash guards are cooperative mistake prevention and never an isolation boundary; the hard
boundaries are the code host's server-side rules, publication credentials kept out of
seat environments, and the owner sending approve-tier text.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k guard_boundaries`.

**Acceptance Scenarios**:

1. Given the amended spec, then 4.5 and 9.1 no longer disagree with each other or with
   `docs/site/security.md` about what hooks guarantee.
2. Given the design spec, then no line calls a hook (Claude Code or git) an anchor or a
   hard boundary; the `pre-push` hook and `permissions.deny` are called local checks.
3. Given 9.1 and the security page, then both list the same hard boundaries: server-side
   rules (protected refs, required checks, required reviews), publication credentials kept
   out of seat environments, owner-sent approve-tier text, and the control plane when built.

### User Story 2 - 4.5 says where normalisation is the defence and where it is not (Priority: P1)

A builder working on a guard knows whether a new bypass form is a blocking defect.

**Independent Test**: same test as US1.

**Acceptance Scenarios**:

1. Given 4.5, then normalisation and the bypass table stay for the guards that protect the
   plugin's own records (state, events, generated instructions, and the owner-only
   commands that write them), where the parser is the only local check.
2. Given 4.5, then for push, merge, deploy and PR approval the guard refuses clearly what
   it recognises, and the guarantee is the host plus the credential layout, which
   `wuwei init` documents and `wuwei config check` verifies (protected base branch,
   required checks, no publishing token in seat environments).
3. Given 4.5, then a narrow argv allowlist is allowed for privileged publish actions only,
   and a positive allowlist for all development commands is rejected with the reason
   (allowing an interpreter or the test runner allows arbitrary code).

### User Story 3 - The cycle budget has a consequence (Priority: P2)

**Independent Test**: same test as US1.

**Acceptance Scenarios**:

1. Given the constitution, then the cycle-budget rule names what happens when it is
   exceeded: no further fix rounds; a design reconsideration recorded in the spec, agreed
   with the owner, before more code; #222 (six rounds) is the recorded example.

### User Story 4 - What a real day must prove (Priority: P2)

**Independent Test**: same test as US1.

**Acceptance Scenarios**:

1. Given design section 10, then a short paragraph says no release ships without the live
   rehearsal a later issue defines (#239), and a rehearsal that could not run is
   unmeasured, never a pass.

### User Story 5 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the diff, then no runtime file changed and no existing guard test changed.

### Edge Cases

- Scope creep: the amendment changes no guard's behaviour. The owner-action, commit, push,
  PR, merge and deploy guards keep refusing exactly what they refuse today.
- 4.6 (merge policy) and 4.7 (deployment ban) are unchanged; 4.5 points at them.
- Design 5.3's cycle budget (the product's own rule, per gate) is a different rule and
  already names its consequence (blocking residue is an owner decision); it is unchanged.
- The "planned" wording for manifests and canaries on the security page belongs to #238
  and is not touched here.
- `docs/integrity.md:42-47` already says local records are tamper evidence and a separate
  principal or control plane is needed for a hard owner boundary; it agrees and is
  unchanged.

## Requirements

- **FR-001**: Design 9.1 states that Bash guards are cooperative mistake prevention and
  never an isolation boundary, that no hook is a hard boundary against the owner's own
  user, and lists the hard boundaries once: server-side rules (protected refs, required
  checks, required reviews), publication credentials kept out of seat environments,
  owner-sent approve-tier text, and the M5 control plane.
- **FR-002**: Design 4.5 keeps normalisation and the bypass table and splits their role:
  the defence for the plugin's own records; clear refusal, not the guarantee, for push,
  merge, deploy and PR approval, whose guarantee is the host and credential layout that
  `wuwei init` documents and `wuwei config check` verifies.
- **FR-003**: Design 4.5 allows a narrow argv allowlist for privileged publish actions only
  and rejects a positive allowlist for all development commands, with the reason.
- **FR-004**: No design spec or docs line calls a hook an anchor or a hard boundary.
- **FR-005**: `docs/site/security.md` matches 9.1: cooperative, not isolation; the same
  hard boundaries including publication credentials.
- **FR-006**: The constitution's cycle budget names its consequence and cites #222; the
  constitution version and last-amended date move (1.1.0, 2026-09-30).
- **FR-007**: Design section 10 carries the "what a real day must prove" paragraph.
- **FR-008**: No runtime file (cli, adapters, hooks, bin, agents, charters, skills,
  templates) changes and no existing test changes. One new docs test in
  `tests/test_docs.py` pins FR-001 to FR-007.

## Success Criteria

- SC-001: A grep of the design spec for "second anchor" and "Local anchors" finds nothing.
- SC-002: The new docs test fails against main's documents and passes on this branch.
- SC-003: `git diff --stat main` lists only the design spec, the constitution,
  `docs/site/security.md`, `tests/test_docs.py` and this feature's `specs/` directory.
- SC-004: The amendment stays short: design spec net growth under 40 lines, by replacing
  sentences rather than adding sections (26 lines as written).

## Assumptions

- The spec author writes the amendment (orchestrator notes); the builder adds the docs
  test, checks consistency and runs the suite. The amendment is already in the working
  tree when the builder starts.
- The owner agreed the change (issue evidence line), so the amended design headings read
  "(owner, 2026-09-28; amended 2026-09-30, #237)" and the new section 10 bullet reads
  "(owner, 2026-09-30)". The constitution rule "the design spec is amended only by its
  owner" is met by the owner merging this change. The constitution amendment needs a
  dated line in the commit message (constitution Governance); that is the orchestrator's
  commit.
- "Publishing" means push to a protected ref, merge, approve, release and deploy. Pushing a
  feature branch and opening a PR are not publishing; the shepherd seat keeps doing them.
- "Seat" is a WUWEI role subagent; the planner session and the owner's terminal are not
  seats. `wuwei merge` runs from the planner session, which is where the narrow argv
  allowlist applies.
- `wuwei config check` today validates only `config.toml`, and `wuwei init` does not yet
  describe the host layout. The spec states the requirement; building it is runtime work
  for a follow-up issue (plan, Deferred). The issue forbids runtime code here.
- The "what a real day must prove" paragraph goes in section 10 as its last bullet (the
  issue allows section 10), naming #239 as the issue that defines the rehearsal.
- A docs test is the smallest check that keeps the documents from drifting back; it
  follows the #231 pattern (whitespace-normalised phrase asserts in `tests/test_docs.py`).
- The worktree is one commit behind origin/main (#236). That commit touches none of the
  files this feature changes except `tests/test_docs.py`, where it appends a test; the new
  test also appends, so the merge is a trivial adjacent-hunk resolution at most.
