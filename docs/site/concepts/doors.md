# The doors

The doors are WUWEI's police powers: a short, closed list of refusals for what cannot be taken
back. Everything else passes and is recorded. Adding a door is a design change, not a fix.

| Door | Refused | Why |
| --- | --- | --- |
| Merge with gaps | a merge by any route (`gh pr merge`, `gh api` PUT `.../merge`, a GitHub MCP merge tool) while the PR has safety gaps, listing them; arming auto-merge passes when only CI is still running | the moment code reaches everyone is the moment evidence matters |
| Admin bypass | `gh pr merge --admin`, `gh api` writes to protection, rulesets, statuses, collaborators, hooks, keys, secrets, environments; `gh repo delete` | the repository's own rules are not changed from an agent session |
| History | force pushes in every form; pushes to or deletion of the default branch | published history does not come back |
| Secrets | a secret pattern or the workspace canary in an MCP call or a network command | a leaked secret cannot be unleaked |
| The record | writes to `.wuwei/ledger.jsonl`; a hand-made `wuwei hook` call | an audit you can edit is not an audit |
| Your attention | an AskUserQuestion without an owner class | a question the process answers costs you for nothing |
| Infrastructure | asked, not refused: terraform, tofu, pulumi, kubectl and helm writes go to the harness's own prompt | a one-way door you decide |

A door that cannot read its evidence stays shut. Every other hook fails open: if a hook breaks,
the work goes on and `hook.error` is recorded.

## How strongly a door holds

A hook on your machine is cooperative: it stops honest mistakes and visible workarounds, but
anything running as your user can write any local file. WUWEI is explicit about that with three
levels, which `wuwei doctor` prints per repository:

| Level | Meaning | Example |
| --- | --- | --- |
| wall | the code host or the credentials make it impossible | a ruleset that requires PRs and blocks force pushes |
| refused | a hook refuses it with the reason | the merge door on a repo without a ruleset |
| detected | it can happen, and the audit shows it | a merge done in the browser shows as an exception in the report |

To turn refusals into walls: give the agents their own GitHub identity (an App or machine user
with write access and no admin), protect default branches with rulesets, require code-owner review
on your `owner_paths`, and keep infrastructure and publishing credentials out of the agents'
environment.

## Andon

From the Toyota production line: anyone who sees a problem that breaks the line pulls the cord. A
seat that finds a repository broken for everyone (its base branch red, a leaked secret, a broken
shared dependency) runs `wuwei andon owner/repo --reason "..."`. New builds in that repository wait
until the cord is cleared with `--clear`; other repositories keep flowing.

**Why:** building on a broken base multiplies the damage. Stopping one stream, by the agents'
own judgment, is responsible autonomy; stopping everything is not.
