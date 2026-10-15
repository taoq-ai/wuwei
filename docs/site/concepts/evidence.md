# Evidence

A pull request is done when its evidence is complete. `wuwei evidence owner/repo#n` lists one PR's
gaps; `wuwei status` lists every open item's. Each gap is **actionable** (the team can close it
now), **waiting** (CI running, the code host unreadable, an andon) or **yours** (an owner review).

WUWEI never asks how the work was done. A test is in the diff or it is not; a reviewer passed this
head or did not.

| Evidence | Applies | Why |
| --- | --- | --- |
| `WUWEI-Item: <id>` in the body | every PR | work outside the plan is visible, and the audit can trace each change to a goal |
| The repository's PR template sections | when the repo has a template | the repository's own process comes first |
| A test in the diff, or `No test: <reason>` | code changes | test first is the cheapest defect filter there is |
| Under about 400 changed lines, or `Size: <reason>` | every PR, generated files aside | small batches fail less and are reviewed better |
| `Rollback: <how to undo>` | full tier, or `owner_paths` touched | a change you cannot undo deserves a plan for undoing it |
| The spec engine's steps, judged by their artifacts at the head | standard and full, when the repo has `.specify/` or `openspec/` | the agreement about what to build is part of the change |
| Gates passed, one at the head | per tier | independent review at the commit that merges, not an older one |
| CI green | every PR | the repository's own checks |
| Every review thread answered | every PR | people's questions are obligations |
| A reviewer requested | every PR | a PR nobody is asked to read is not reviewed |
| Owner review | `owner_paths` touched | what you chose to review yourself |
| Not stale (under three days open) | every PR | inventory rots; flow over stock |

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

## Gates at the head

Each required gate must have passed at an ancestor of the PR's head, and at least one gate must
have passed at the head itself. A fix after review therefore needs one delta review, not a full
re-review, and a merge never relies only on reviews of older code.

## Attested verdicts

A verdict counts only when WUWEI attested it. When a sentinel stops, the SubagentStop hook reads the
file it names (`Verdict file: <path>`), checks its shape, and records its hash, gate, item, head,
confidence and the agent that wrote it. A malformed verdict goes back to the reviewer once with the
format. A file edited after attestation no longer counts.

**Why:** a review is evidence only if a reviewer wrote it and it has not changed since. The hook
checks the file at stop, however it was written, so a shell edit cannot slip past the lint.

## Exceptions

You can accept one gap at one head as an exception (see [decisions](decisions.md#exceptions)). The
gap disappears from that head's evidence, the exception stays on the record, and a follow-up item
in the plan closes it later.

## When evidence cannot be read

An unreadable code host is a waiting gap, never a pass. A merge whose evidence cannot be read stays
refused.
