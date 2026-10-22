# Decisions

## Reversibility and confidence

Every open choice is weighed on two questions: can it be undone cheaply, and how sure are you?

| | Sure | Unsure |
| --- | --- | --- |
| **Undone cheaply** | act | act, and record the assumption |
| **Hard to undo** | act, with a `Rollback:` line | ask the owner |

**Why:** most mistakes are cheap if they can be undone, so the model should act and keep moving.
The expensive mistakes are the ones that are both hard to undo and uncertain, and those are the
only ones worth your attention. This is the one-way and two-way door idea, made into a rule the
model applies itself.

## Assumptions

A choice taken without asking is recorded under `Assumptions:` in the spec or PR body: what was
assumed, why, and what would overturn it. Gates review assumptions like any other finding, and the
steward samples them for reversals.

**Why:** an assumption written down can be checked and corrected. An assumption left in the
model's head cannot.

## Asking the owner

A question reaches you only when it starts with its class:

| Class | For |
| --- | --- |
| `one-way:` | hard to undo and unsure |
| `scope:` | work outside the goals, a reviewer's out-of-scope request |
| `goal:` | the goals themselves |
| `trust:` | a trust-boundary question a gate cannot settle |
| `infra:` | an infrastructure change |
| `owner review: owner/repo#n at <sha7>` | a change under your `owner_paths` |
| `exception: owner/repo#n at <sha7>: <gap>` | accepting one safety gap (tests, gates, CI, threads) at one head |
| `plan:` | approving the plan view at the end of a plan pass |
| `breaking: owner/repo#n at <sha7>: <what breaks>. Announced at <link>. Proceed?` | shipping a [breaking change](evidence.md#breaking-changes) (a major), after its announcement |

Any other question is sent back to the model: decide it, record the assumption, go on. The model
never asks whether to continue planned work. Each question comes once, with a recommendation.

**Why:** your attention is the scarcest resource on the team. The report counts your prompts and
how often you chose the recommendation; a kind of question you always answer the same way becomes a
rule at the next retro.

## Exceptions

Sometimes a safety gap is acceptable: a hotfix without the security gate at 2am. (A process gap,
such as a spec rule misfiring on an old feature at standard tier, never reaches you: it does not block, and the
merge records it for the retro.) You accept it with an
`exception:` question. WUWEI records the ruling, drops that gap at that head, and adds a follow-up
item to the plan that closes it later. The report lists open exceptions.

The gap in the question must be the gap as `wuwei evidence` prints it. Case, spacing, end marks and
a printed `[waiting]` do not matter. For a gate gap, the gates it names also work: `security` for
`gates missing at head <sha7>: security`. A part of a gap waives nothing: `security` does not drop
`gates missing at head <sha7>: quality, security`, and `e` drops no gap at all. A gap that ends in an
`analysis.md` finding row runs to the row's last `|`, so a sentence inside the row stays in the gap.

**Why:** an accepted gap is a debt. Exceptions expire into work, never into silence.

## ADRs

When you answer a `one-way:` question, the planner records the decision as a short Architecture
Decision Record (context, decision, consequences) through the item's PR. It goes where the
repository keeps its ADRs: an existing `docs/adr/` or `docs/decisions/`, else the item's spec
folder. When your answer re-confirms an existing ADR, the planner amends that ADR instead of adding
a file.

**Why:** the reason for a hard decision outlives the session that took it, and the next person
(or agent) who wants to reverse it should find it.
