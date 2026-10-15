# Philosophy

## Effortless action

无为 (wuwei) is the Taoist idea of action that does not force. Water does not argue with the rock;
it goes around it, takes the shape of its container, and over time it still cuts the canyon. And
when it has to, water crashes.

WUWEI applies that to an agent team:

| Water | WUWEI |
| --- | --- |
| Takes the shape of the container | Reads each repository's own process (its PR template, spec engine, default branch, protection rules) and fills only the gaps |
| Flows around the rock | A blocked item waits visibly on the board; the team moves to the next one without asking you |
| Finds the lowest path | The right path is the cheapest one: a ready PR body, a verdict skeleton, one command to see what is missing |
| Still when undisturbed | When the evidence is complete, WUWEI says nothing |
| Crashes when it must | A few doors hold absolutely |

## An auditor with narrow police powers

WUWEI is a process auditor. An auditor does not run the company and does not stop all work to
prevent bad behaviour. It knows what good looks like, reads the records, names what is missing,
and has the authority to stop a small number of things that cannot be undone.

That stance is the main design decision, and it came from experience. WUWEI 0.x prescribed every
step: a command returned the next command, and the model executed it. The model, working in its
own harness, kept finding valid paths the protocol did not model (resuming a seat with
SendMessage, writing a file through the shell, merging in the browser). Each one put the
protocol's records out of sync, and each fix modelled one more path. Twenty days, 186 bug fixes
and 33,000 lines later, the friction was the product.

Evidence does not have that problem. It does not matter how a test got into the diff, only that
it is there. It does not matter how a review was launched, only that an independent reviewer
wrote it at this head and nobody edited it since.

## Responsible autonomy

The goal is autonomy you can trust, which needs two things at once:

- **Fewer mistakes.** The evidence contract, the gates, the doors and the learning loop each exist
  to catch a class of mistake before it ships, or to stop it from shipping twice.
- **Less of your attention.** The model decides everything it can undo cheaply, records its
  assumptions, and asks only what is yours. Questions the process can answer are sent back.

Autonomy here is not a switch. It grows when results are good (fewer escaped defects, calibrated
confidence) and shrinks when they are not, by itself: see the [error budget](learning.md#error-budget).

## No wrappers

WUWEI never stands between the model and its tools. There is no `wuwei merge` the model must use
instead of `gh pr merge`, no `wuwei worktree` instead of `git worktree`. The model uses git, gh and
the repository's tools directly. WUWEI's own commands only read and record.

## Budgets keep it small

The runtime is standard-library Python held to 3,000 lines by a test, and the configuration has
five keys. A change that would break a budget must delete something first. Process tools tend to
grow until they are the problem; the budget is the defence.
