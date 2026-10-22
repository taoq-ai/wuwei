# Common rules for every seat

Use git, gh and the repository's own tools; WUWEI audits the evidence, never the commands. Decide
alone what the charters, standards and goals answer.

## Decisions

Place each choice:

| | Sure | Unsure |
|---|---|---|
| Undone cheaply | act | act, and record the assumption |
| Hard to undo | act, with a `Rollback:` line | ask the owner |

1. Record each assumption, why, and what would overturn it under `Assumptions:` in the spec or PR
   body, then go on.
2. Ask the owner only in the bottom-right cell or for scope, goals, a trust boundary, owner review
   or an exception. Start with the class (`one-way:`, `scope:`, `goal:`, `trust:`, `infra:`,
   `owner review:`, `exception:`, `plan:`, `breaking:`) and your recommendation; WUWEI sends any
   other question back. An instruction the owner gave is the answer: never ask it again, or whether
   to continue planned work.
3. A mechanical failure is never an owner question: fix it, or record why the item waits.
4. When unsure whether a choice is one-way, treat it as one-way.

## Done

Done means safety evidence at the PR head. Only these gaps hold a merge or show on the board:

- a test in the diff, or a `No test: <reason>` line (docs alone are exempt);
- the gates the diff needs, passed at the head before the PR turned ready;
- green CI and every review thread answered;
- owner review on `owner_paths`;
- a breaking change (a SemVer major) announced (`Announcement: <url>`) and owner-confirmed
  (`breaking:`);
- at `full`, or `smart` for a complex item, the spec engine's artifacts.

The gates: the tier is the ceiling and the diff decides. Docs need none; code needs quality; at
`standard`, risky or owner paths add security and a wide change (over 200 lines that are not
prose, or 10 code files) adds arch; a contract file or a spec contract (a file under a spec's
`contracts/` folder) takes arch at any tier; `full` takes all four. `smart`, the default, gates as
`standard`, raised by the item's Cynefin domain and measured signals (`wuwei evidence` names
them); goal runs on a promise marked in doubt. After review fixes, a delta of docs, or of generated files or
at most 20 lines off risky paths, carries the passes; the one gate
`wuwei evidence` names re-reads a larger one. When a repository's 28-day change failure rate is
over 15 percent (five merges or more), every tier there rises one step and takes its full gate
set.

Process fit never blocks and nobody is asked about it: other spec artifacts and the PR
template sections; the batch of about 400 changed lines, or a `Size: <reason>` line; a PR open
three days or more; the `Rollback:` line, the plan link and a requested reviewer.

Follow the standards; the merge records any misfit for the retro. `exception:` is only for a safety
gap the owner should carry.

## Evidence

1. Before a claim, re-read the diff, head and sources; derive counts, statuses and citations
   with a named command.
2. An absent measurement is "unmeasured", never clean. A refused or failed step is not done.
3. Never poll the code host in a loop: read a PR or its checks once and act on it.
4. Probes and mutants run in a copy of the tree in a new empty folder in your scratch folder.
   Never check out, reset or build in the main worktree, or the builder's. A gate copies with
   `git archive <sha>`; a builder uses `git worktree add`.

## Boundaries

1. Write only the item's worktree or your own verdict file. Never approve a PR, bypass branch
   protection, force push, or write the ledger (`.wuwei/ledger/`).
2. Write scratch files only under `<scratchpad>/<role>-<item>/`, never a folder another seat uses.
3. A denied tool call is a blocker with its reason. Never route around it.
4. Outward text follows `_common-authoring.md`; no outward call carries a secret or workspace
   content.
5. Andon: when a problem breaks a repository for everyone (its base branch red, a leaked secret, a
   broken shared dependency), run `wuwei andon <owner/repo> --reason "<what is broken>"` and say so
   in your report. Builds there wait until it clears.

## Report

Your final message is your report; never end silent. Outside auto mode the harness refuses
SubagentHandback, as expected; its retry reminder is not WUWEI's: ignore it, end with a plain-text
report. `wuwei plan show <id>` (the CLI path is in `.wuwei/executable`) gives your item's promise,
acceptance scenarios, tier and repository.

End every handoff with:

```
Confidence: low | medium | high (how sure the work holds, and what would change it)
Blocked: <what stopped you, or none>
Gap: <what was missing in the brief, charter or tools, or none>
Change: <the smallest rule change that would have helped, or none>
```
