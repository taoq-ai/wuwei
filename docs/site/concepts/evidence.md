# Evidence

A pull request is done when its safety evidence is complete. `wuwei evidence owner/repo#n` lists one
PR's safety gaps; `wuwei status` lists every open item's. Each gap is **actionable** (the team can close it
now), **waiting** (CI running, CI not started at a code head with no checks yet, the code host unreadable,
an andon) or **yours** (an owner review).

WUWEI never asks how the work was done. A test is in the diff or it is not; a reviewer passed this
head or did not.

| Evidence | Applies | Kind | Why |
| --- | --- | --- | --- |
| The WUWEI footer naming the item | every PR | process | work outside the plan is visible, and the audit can trace each change to a goal |
| The repository's PR template sections | when the repo has a template | process | the repository's own process comes first |
| A test in the diff, or `No test: <reason>` | code changes | safety | test first is the cheapest defect filter there is |
| Under about 400 changed lines, or `Size: <reason>` | every PR, generated files aside | process | small batches fail less and are reviewed better |
| `Rollback: <how to undo>` | full tier, or `owner_paths` touched | process | a change you cannot undo deserves a plan for undoing it |
| The spec engine's steps, judged by their artifacts at the head | standard and full, when the repo has `.specify/` or `openspec/` | process at standard, safety at full | the agreement about what to build is part of the change |
| A breaking change: an `Announcement:` link, then the owner's confirmation at the head | a declared break, or one the arch gate finds | safety | clients you break should hear it from you first, and you decide whether it ships |
| The gates the diff needs, passed before the PR turned ready | the diff, under the tier's ceiling | safety | independent review before anyone else reads the code, and only the reviews the change calls for |
| CI green | every PR | safety | the repository's own checks |
| A review status settled (see [review statuses](#review-statuses)) | a commit status from a workflow the repo runs on `pull_request_review` | safety | a gate waiting on a reviewer needs someone to act; it is not a build |
| Every review thread answered | every PR | safety | people's questions are obligations |
| A reviewer requested | every PR | process | a PR nobody is asked to read is not reviewed |
| Owner review: your approving review, or your `owner review:` answer, at the head (a `breaking:` or `exception:` answer is not one) | `owner_paths` touched | safety | what you chose to review yourself |
| Not stale (under three days open) | every PR | process | inventory rots; flow over stock |

## Review statuses

Some repositories publish their approval rule as a commit status, from a workflow that runs on
`pull_request_review` (ai-stacks' `Review Gate`). WUWEI follows the status's `target_url` to its
workflow run and compares the run's workflow with the workflows the repository has run on
`pull_request_review` (its last 100 such runs, read once a day, and only when a head has an
unsettled status). A match is review evidence, not CI:

| Status | Gap |
| --- | --- |
| pending | `waiting on review: <context>` |
| failure | `change request outstanding: <context>` |

Both are actionable safety gaps: someone has to ask for a review or answer the change request, and
the merge stays refused until then, with or without auto-merge. When the Actions host cannot be
read, the status stays CI (`CI running` or `CI failing`), never a pass.

**Why:** a review gate read as CI tells the team to wait for a build that already finished, or to
fix a build that is not red.

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

A breaking change is a major version under [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html):
an incompatible change to the public API a project declares. Its clients cannot be un-broken, so
it is close to a one-way door. In a repository WUWEI audits, the arch gate reads that repository's
declared public API, or what it documents for clients when it declares none.

WUWEI's own public API is:

- the CLI commands, flags, exit codes and the output documented for scripts;
- the config keys and their defaults;
- the ledger, state and verdict file formats;
- the PR body lines and owner question shapes that seats and owners write;
- the hook input and output contract;
- the skill names (`/wuwei-run`, `/wuwei-watch`, `/wuwei-close`, `/wuwei-rules`, and the old name
  of a renamed skill while its alias ships), the plugin name and the marketplace name;
- the agent role names, which the config's `models` rows name;
- the owner-written files: `.wuwei/goals.md`, `.wuwei/standards.md` and the plan file format.

The gate reads this list, or a project's own declaration, at the base commit, never from the PR's
own head, so a PR cannot shrink the API it is judged by. A change is classified by what it does to
that API:

| Bump | The change |
| --- | --- |
| major | a documented element is removed, renamed or given a different meaning or shape; an input every client must now give; a documented exit code changes meaning |
| minor | a new capability that existing clients need not use; a new check that is off by default or only adds information |
| patch | a fix of behaviour that contradicted the documented public API at the base, including a closed guard bypass and a gap the docs already promised; docs; internals |

A fix makes the code do what the docs already said, so it is a patch even when WUWEI now refuses
or reports more. Refusing or reporting more is a patch only under that condition: the old
behaviour contradicted the documented public API. A new rule that asks every PR for something the
docs never asked is an input every client must now give, so a major. An exit code is judged by its
meaning, not by which inputs reach it: when `wuwei evidence` exits 1 on one more PR because a
documented rule is now checked strictly, 1 still means gaps, so that is a patch. A change with
any major part is a major. When the gate is unsure which bump applies, it escalates to you with
`Breaking: yes`.

Versions 2.0.0 to 4.0.0 were bumped under the earlier rule, where any visible change in behaviour
counted as breaking, and from 4.1.0 the SemVer policy applies.

WUWEI finds a breaking change three ways: the PR declares it (a `!` in the title, a
`BREAKING CHANGE:` line), the architecture gate states it (every arch verdict carries
`Breaking: no` or `Breaking: yes: <what breaks for which clients>`, and yes means a major), and a
change to a contract file (OpenAPI, protobuf, GraphQL, JSON schema) takes the arch gate at any tier
so it looks. A patch is a `fix:` commit and a minor a `feat:`, as release-please bumps them; only
a major takes a `!`.

Before a major merges it needs evidence, in order:

1. An `Announcement: <url>` line: one http(s) URL alone on the line, without brackets. It points at
   a client communication that already exists: a PR or issue comment, or a published release note
   or migration guide. A changelog entry written at release does not count.
2. Your confirmation, asked once the announcement exists:
   `breaking: owner/repo#n at <sha7>: <what breaks>. Announced at <link>. Proceed?`. It binds to that
   head; a change after it asks again.

**Why:** a break nobody announced is an outage for someone else. The team does the work of finding
and announcing it; you decide whether it ships. A major that is not one costs clients an upgrade
review for nothing, so a fix of a documented rule ships as a patch, with release notes.

## Gates before the PR, chosen by the diff

The gates run before review: the PR opens as a draft so CI runs, and `gh pr ready` and reviewer
requests are refused until the gates pass at its head, so reviewers and the merge only ever see gated code.

The tier is a ceiling and the diff decides what runs under it:

| The diff | Gates |
| --- | --- |
| prose only, at any size (`.md`, `.rst` and `.adoc` files outside the spec folders, other than the files seats load such as `AGENTS.md`, `CLAUDE.md`, charters, agents and skills; `LICENSE`; `NOTICE`), or specs of 200 lines or fewer with no contract | none |
| code | quality |
| risky paths (auth, sessions, tokens, secrets, crypto, SQL, migrations, policies, infrastructure, CI, dependency manifests) or `owner_paths`, at standard | + security |
| a contract file or a spec contract (a file under a spec's `contracts/` folder) at any tier, or at standard more than 200 changed lines that are not prose (code, specs, `.txt` files, code under `docs/`, the files seats load) or 10 code files | + arch |
| full tier | all four |

A one-line config flag costs one gate. After a fix round only the gate that found the problem
re-reads. After review comments, a delta of docs, or of at most 20 lines off risky paths, carries
the earlier passes; a larger one is re-read by the one gate it needs (security for risky paths,
arch for a contract, quality otherwise). When the error budget is overrun, or a light item touches a
trust path (auth, sessions, tokens, secrets, permissions, grants, policies) outside docs, the raised
tier takes its full gate set.

**Why:** gates that run after the PR opens race the merge, and four gates on a one-line change
cost more than they find. Review cost follows risk.

## Attested verdicts

A verdict counts only when WUWEI attested it. When a sentinel stops, the SubagentStop hook reads the
file it names (`Verdict file: <path>`), checks its shape, and records its hash, gate, item, head,
confidence and the agent that wrote it. A malformed verdict goes back to the reviewer once with the
format. A file edited after attestation no longer counts, except that a finding (FIX or ESCALATE)
still holds as recorded: replacing it cannot turn it into a pass. A verdict counts only at an
ancestor of the PR head. A pass counts only for this PR, for its repository alone, or when no PR is
named (an imported 0.34 verdict); a finding holds from any PR of the item. A later pass at the same
or an older head never clears a finding: only a pass at a newer head on the PR's line does. The
create and ready doors read no PR yet, so there a pass for any PR of the item in that repository
counts. A gate whose only pass named another PR reads missing: re-run it with
`PR: <owner/repo>#<n>`. A seat that writes over another seat's verdict is sent back to
write its own file beside it. When the stop cannot read the seat's last message, the handback to the
lead carries it, and the verdict is attested from there. A verdict file that does not count is
never silent: the board names it and why (its shape, or that no sentinel attested it). An attested
pass that does not count for this PR or head shows only as the gate missing.

**Why:** a review is evidence only if a reviewer wrote it and it has not changed since. The hook
checks the file at stop, however it was written, so a shell edit cannot slip past the lint.

## Duties

A **duty** is work the team owes that does not hold the merge but reaches the team until it is
done: asking for review where the team asks (see [review requests](watch.md#review-requests)), and,
when a check is red, re-requesting an approval given at an older commit (the approval is named with
its commit, so nobody re-runs a review gate that wants an approval at the head).
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
in the plan closes it later. Only the gap the exception names exactly disappears; a part of a gap
waives nothing.

## When evidence cannot be read

An unreadable code host is a waiting gap, never a pass. A merge whose evidence cannot be read stays
refused.
