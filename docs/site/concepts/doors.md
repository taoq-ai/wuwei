# The doors

The doors are WUWEI's police powers: a short, closed list of refusals for what cannot be taken
back. Everything else passes and is recorded. Adding a door is a design change, not a fix.

| Door | Refused | Why |
| --- | --- | --- |
| Merge with gaps | a merge by any route (`gh pr merge`, a REST PUT on `.../pulls/<n>/merge` or `.../ccr/auto_merge` in any spelling, a GitHub MCP merge tool) while the PR has safety gaps (a breaking change without its announcement and your confirmation among them), listing them; arming auto-merge passes when only CI is still running | the moment code reaches everyone is the moment evidence matters |
| Ungated PR | a PR opened ready for review (`gh pr create`, `gh pr new`, a REST POST on `repos/<owner>/<repo>/pulls` or a GitHub MCP create tool without draft), the flip to ready (`gh pr ready`, a REST POST on `.../pulls/<n>/ccr/ready_for_review`, MCP `update_pull_request` with draft false) or a reviewer request on a draft (`gh pr edit --add-reviewer`, `.../requested_reviewers`, MCP reviewers or `request_copilot_review`) before the gates the diff needs pass at the head, listing them; a draft opens before them | CI runs on the draft, and review and merge start at a gated head, so no gate races a merge |
| Admin bypass | `gh pr merge --admin` (or `--admin=true`, `--admin=1`), a `gh api` write to `repositories/<id>/...` (spell it `repos/<owner>/<repo>/...`), a `gh api graphql` query WUWEI cannot read (stdin, a missing file, a file outside one plain `gh` call), `gh api` writes to protection, rulesets, statuses, collaborators, hooks, keys, secrets, environments; `gh repo delete` or a REST DELETE on the repository; a `gh api graphql` mutation that merges, arms auto-merge, opens a PR, marks one ready, requests reviewers, moves a ref, commits to a branch or changes protection or rulesets | the repository's own rules are not changed from an agent session |
| History | force pushes in every form; pushes to or deletion of the default branch, including the GitHub MCP `push_files`, `create_or_update_file` and `delete_file` tools on it or with no branch; `gh api` writes to `merges`, `git/refs/` or `contents/` on any branch | published history does not come back |
| Secrets | a secret pattern or the workspace canary in an MCP call or a network command | a leaked secret cannot be unleaked |
| The record | writes to the ledger (`.wuwei/ledger`, `.wuwei/ledger.jsonl`, or `.wuwei` itself) in the spellings sh expands (`//`, `/./`, `..`, globs such as `.wuwei/*` and `.w*/ledger`, braces such as `{l,}edger`); writes to the cache (`.wuwei/cache`), whose entries feed gate inputs (removing a cache file passes); `find` with `-delete`, `-exec`, `-execdir`, `-fprint`, `-fprintf` or `-fls` on those paths (the cache included); a path in a `python -c` body; a writer or a redirect after `cd .wuwei`, or in a command whose `-C`, `--chdir` or `-D` value names `.wuwei` (`env -C .wuwei`, `sudo -D .wuwei`); `git clean` with `-x`, `-X` or an exclude that is not a plain word, unless every pathspec and `-C` dir is a plain word lying outside `.wuwei` (dry runs included), and git clean after any git option but `-C` or with `GIT_` in the command; a hand-made `wuwei hook` call | an audit you can edit is not an audit |
| Your attention | an owner question (AskUserQuestion, or `request_user_input` in Codex) without an owner class | a question the process answers costs you for nothing |
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
