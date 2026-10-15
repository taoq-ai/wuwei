# Evidence

A pull request is done when its safety evidence is complete. `wuwei evidence owner/repo#n` lists one
PR's safety gaps; `wuwei status` lists every open item's. Each gap is **actionable** (the team can close it
now), **waiting** (CI running, the code host unreadable, an andon) or **yours** (an owner review).

WUWEI never asks how the work was done. A test is in the diff or it is not; a reviewer passed this
head or did not.

| Evidence | Applies | Kind | Why |
| --- | --- | --- | --- |
| `WUWEI-Item: <id>` in the body | every PR | process | work outside the plan is visible, and the audit can trace each change to a goal |
| The repository's PR template sections | when the repo has a template | process | the repository's own process comes first |
| A test in the diff, or `No test: <reason>` | code changes | safety | test first is the cheapest defect filter there is |
| Under about 400 changed lines, or `Size: <reason>` | every PR, generated files aside | process | small batches fail less and are reviewed better |
| `Rollback: <how to undo>` | full tier, or `owner_paths` touched | process | a change you cannot undo deserves a plan for undoing it |
| The spec engine's steps, judged by their artifacts at the head | standard and full, when the repo has `.specify/` or `openspec/` | process at standard, safety at full | the agreement about what to build is part of the change |
| A breaking change: an `Announcement:` link, then the owner's confirmation at the head | a declared break, or one the arch gate finds | safety | clients you break should hear it from you first, and you decide whether it ships |
| Gates passed, one at the head | per tier | safety | independent review at the commit that merges, not an older one |
| CI green | every PR | safety | the repository's own checks |
| Every review thread answered | every PR | safety | people's questions are obligations |
| A reviewer requested | every PR | process | a PR nobody is asked to read is not reviewed |
| Owner review | `owner_paths` touched | safety | what you chose to review yourself |
| Not stale (under three days open) | every PR | process | inventory rots; flow over stock |

## The spec engine

When a repository uses a spec engine, its steps are part of the evidence at `standard` and `full`.
WUWEI does not watch the steps run; it reads their artifacts at the PR head, in every feature
directory the diff touches, so a later commit that only updates `tasks.md` still counts.

| Engine | standard | full adds |
| --- | --- | --- |
| spec-kit (`.specify/`, features in `specs/<feature>/`) | `spec.md`, `plan.md`, `tasks.md` with every task checked (implement done) | a `## Clarifications` section in `spec.md` (clarify ran), `analysis.md` with no open CRITICAL or HIGH row (analyze ran clean), every item in `checklists/` checked |
| OpenSpec (`openspec/`, changes in `openspec/changes/<change>/`) | `proposal.md`, at least one capability spec under `specs/`, `tasks.md` with every task checked | |

**Why:** a spec nobody finished is worse than no spec, because it looks like agreement. Checking the
artifacts, not the commands, keeps the rule true whichever way the steps were run.

At `standard` the steps are process fit: a misfit is recorded, never blocking. At `full` they are
safety gaps and hold the merge, because full is the tier for work where building the wrong thing is
expensive.

## Breaking changes

A change that breaks an outward contract (CLI commands and output, API endpoints and fields, config
keys, events, schemas, formats other systems read) is close to a one-way door: the clients it
breaks cannot be un-broken. WUWEI finds it three ways: the PR declares it (a `!` in the title, a
`BREAKING CHANGE:` line), the architecture gate states it (every arch verdict carries
`Breaking: no` or `Breaking: yes: <what breaks for which clients>`), and a light item that touches a
contract file (OpenAPI, protobuf, GraphQL, JSON schema) is raised to standard so the arch gate
looks.

Before such a change merges it needs evidence, in order:

1. An `Announcement: <link>` line: the client communication, release note, migration guide or press
   release.
2. Your confirmation, asked once the announcement exists:
   `breaking: owner/repo#n at <sha7>: <what breaks>. Announced at <link>. Proceed?`. It binds to that
   head; a change after it asks again.

**Why:** a break nobody announced is an outage for someone else. The team does the work of finding
and announcing it; you decide whether it ships.

## Gates at the head

Each required gate must have passed at an ancestor of the PR's head, and at least one gate must
have passed at the head itself. A fix after review therefore needs one delta review, not a full
re-review, and a merge never relies only on reviews of older code.

## Attested verdicts

A verdict counts only when WUWEI attested it. When a sentinel stops, the SubagentStop hook reads the
file it names (`Verdict file: <path>`), checks its shape, and records its hash, gate, item, head,
confidence and the agent that wrote it. A malformed verdict goes back to the reviewer once with the
format. A file edited after attestation no longer counts, except that a finding (FIX or ESCALATE)
still holds as recorded: replacing it cannot turn it into a pass. At one head, a later pass does not
outvote a finding; a new head does. A seat that writes over another seat's verdict is sent back to
write its own file beside it. When the stop cannot read the seat's last message, the handback to the
lead carries it, and the verdict is attested from there. A verdict file that does not count is
never silent: the board names it and why (its shape, or that no sentinel attested it).

**Why:** a review is evidence only if a reviewer wrote it and it has not changed since. The hook
checks the file at stop, however it was written, so a shell edit cannot slip past the lint.

## Duties

A **duty** is work the team owes that does not hold the merge but reaches the team until it is
done: today, asking for review where the team asks (see [review requests](watch.md#review-requests)).
Duties show on the board and in the Stop reminder, like safety gaps.

## Safety and process

Only **safety** gaps hold a merge and reach the team while it works: a test, the gates at the head,
green CI, answered threads, owner review, a breaking change's announcement and confirmation, the
spec engine's steps at `full`, and evidence that can be read. Everything else is
**process fit**: the plan link, the PR template, small batches, the `Rollback:` line, the spec
engine's steps below `full`, a requested reviewer, staleness. Process fit never blocks and is never shown on the
board or asked about; the merge records it, the report lists it, and the steward turns a rule that
keeps misfiring, or keeps being skipped, into a fix.

**Why:** continuous flow. Neither you nor the model should be distracted by a rule that does not
fit this change. The audit still sees every misfit, and the process learns from them.

## Exceptions

For a safety gap only, you can accept one gap at one head as an exception (see [decisions](decisions.md#exceptions)). The
gap disappears from that head's evidence, the exception stays on the record, and a follow-up item
in the plan closes it later.

## When evidence cannot be read

An unreadable code host is a waiting gap, never a pass. A merge whose evidence cannot be read stays
refused.
