# Feature Specification: Register ad-hoc seats at Agent launch

Issue: #955. Branch: `955-adhoc-launch`. Date: 2026-10-13.

## User Scenarios & Testing

### US1: Launch from the prompt (P1)

As the planner, launch a WUWEI agent with its task prompt once. With an active
day and no brief marker, a successful launch records its role, item and private
prompt and reserves a running seat. A plan item explicitly identified by name,
description or an Item: line is retained; otherwise
the generated seat name identifies the ad-hoc work. Explicit brief references
continue to require their original recorded evidence.

### US2: Preserve launch boundaries (P1)

For typed WUWEI launches, unknown roles, the planner role, nested launches, runtime
mismatches, protected paths on SLICE, insufficient
memory, CAP and host seat limits still refuse the launch. A named gate item
must satisfy existing gate readiness and clean-worktree rules. Refused launches
reserve no seat. Concurrent launches respect the same locked capacity check.
A builder tied to a plan item must use its recorded build launch under #901.
An ad-hoc sentinel never supplies a gate verdict to dispatch.receive.

### US3: Stop and recover (P1)

A transcript beginning with the recorded prompt binds tool traces and its stop
to the seat. Later user messages cannot change that binding. SubagentStop
records completion; the existing seat stop command
and terminal-report recovery can recover it. Explicit seat start --adhoc still
labels its matching launch.

## Requirements

- FR-001: Automatically register valid WUWEI launches without a brief marker.
- FR-002: Keep the complete original prompt in a private file inside the day;
  state and events carry only its path, digest and seat metadata.
- FR-003: Preserve shared role, runtime, capacity and protected-path checks;
  named gate items retain their readiness and clean-worktree checks.
- FR-004: Bind traces and stop/recovery to the prompt digest or existing brief
  reference. Preserve explicit seat start --adhoc and ordinary brief launches.
- FR-005: Invalid explicit references never fall back to automatic registration.
- FR-006: Use the existing atomic state writer and private file writer, reject
  symlink destinations, and retain three-state guard exits.
- FR-007: Refuse dispatch.receive for any seat carrying prompt_sha256; direct
  the caller to bin/wuwei dispatch next for a logged gate brief.
- FR-008: Refuse item-bound ad-hoc builders under #901 and preserve CAP for
  unbound builders. Infer items only from explicit identification.
- FR-009: The first prompt defines transcript identity. Refuse typed ad-hoc launches
  from callers with agent_id present and exclude planner as an ad-hoc role.

## Key Entities

The existing seat gains a private prompt file reference and prompt digest;
its actual WUWEI role remains available to capacity and role guards. No new
state collection, command, module, status or owner interaction is introduced.

## Success Criteria

- SC-001: The 2026-10-13 field case launches with one prompt and no prior file
  or registration command, then records its stop.
- SC-002: Table tests cover successful, refused and unmeasured launches,
  private storage, stop, recovery and the explicit registration command.
- SC-003: Every test file importing changed modules passes with the assigned
  interpreter, explicit file arguments, fake adapters and no network.

## Assumptions

- This issue supersedes the design 4.1 missing-brief refusal only. Proposed
  owner wording: automatic typed WUWEI prompt registration permits unbound builders and
  ad-hoc reviews, preserves #901 for planned builders, never admits an ad-hoc
  gate verdict, and is available only outside seats. An explicit brief reference
  still requires matching evidence. The owner-only design stays unchanged.
- Item inference uses whole-word matches in name or description and exact plan
  identifiers on explicit Item: lines. Free prompt prose is not an item selector.
  Non-builders with zero or multiple matches use the generated ad-hoc seat name.
  Builders check every match against #901; ambiguity never bypasses it.
- Ad-hoc work does not create or advance a build record. Builders naming no
  plan item remain allowed and count against CAP. A builder naming a plan item
  goes through the #901 refusal, including when its recorded builder is running.
  The existing guards.enforce policy applies to that refusal.
- A sentinel associated with a plan item retains launch gate checks. No ad-hoc
  sentinel may deliver gate evidence: dispatch.receive requires the gate brief
  produced by the existing dispatch workflow.
- Prompt identity uses the existing stripped-text SHA-256 convention. Duplicate
  prompts retain the existing trace-session binding and oldest-unbound policy
  within one item. Refuse an indistinguishable pending launch for a different
  item in the same role and launcher session; retry with an Item: prompt line.
- Untyped general-purpose and Explore launches retain #676 registration,
  including callers with agent_id present. Only typed launches refuse nesting.
- #937 is present in history (a30d25fb is an ancestor of HEAD). The earlier
  claim that it was absent was incorrect. This issue preserves existing stop
  and recovery behavior and its plain-final payload regression.
- Generated names skip existing brief files, including private evidence left
  after a failed event append. Such evidence is preserved, never overwritten.
- Repository-specific instructions override interactive clarification, commits,
  and the constitution's bare full-suite step. No questions or GitHub writes.

## Clarifications

2026-10-13: Resolved role, identity, privacy, explicit-reference and build-record
ambiguities using the assumptions above. No outstanding clarification.

## Deferred

Review findings L2 (identical typed and untyped prompts), L3 (CAP double count
with enforcement off), and L5 (hashed trace-session identity) were not selected
in this follow-up. L3 cannot arise from a new item-bound ad-hoc builder with
enforcement on after HIGH-2. These remain recorded for separate owner triage;
no issue was filed because this seat may not use GitHub commands.

## Review-driven design reconsideration

The owner-authorized review follow-up narrows the boundary between ad-hoc work
and planned workflow evidence. Sharing role and item fields had incorrectly
allowed prompt-only seats to stand in for logged build and gate briefs. Keep
automatic registration, but enforce the two workflow entry points: build next
for item-bound builders and dispatch next for gate verdicts. No new lifecycle
or artifact type is needed. This replaces the earlier broad assumption that
any ad-hoc builder could name a plan item.

The proposed owner wording is recorded under Assumptions. The owner design
remains unchanged.

## Round 2 requirements and assumptions

- FR-010: Builders inspect every item named by name, description or Item: line
  under the reservation lock. Any named item retains the existing #901 refusal
  for prompt-only builders, including missing or running build records.
- FR-011: A bound prompt sentinel never counts toward a dispatch gate batch.
- FR-012: Missing-worktree advice for a bound prompt sentinel names dispatch
  next for the item, without suggesting flags on a nonexistent brief command.
- FR-013: Include item identity in launch collision checks. Since the harness
  transcript carries the prompt but not the launch description, reject pending
  same-prompt, same-role, same-session launches for different items and request
  an Item: line. Same-item duplicates preserve their launch-order behavior.

The owner explicitly authorized this second round. The approach remains shared
checks with complete item matching, no new lifecycle or binding subsystem.
Untyped launches and owner design wording remain as specified above.
