# Getting started

## Requirements

Claude Code, Python 3.11 or newer, Git and the GitHub CLI (`gh`), authenticated. WUWEI installs
no packages: its runtime is the Python standard library.

## Install

In Claude Code:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

For a verified install, use the signed `wuwei.tar.gz` release asset: it carries
`MANIFEST.sha256` and its signature.

## Create the workspace

From the directory that will own the workspace (usually your main repository):

```sh
bin/wuwei init
bin/wuwei doctor
```

`init` creates `.wuwei/` and merges WUWEI's rules into `.claude/settings.json`: an allow list for
everyday work, deny rules for the doors, ask rules for infrastructure. Your own rules stay as they
are. `doctor` checks the install and prints, per repository, how strongly each door holds.

Add more repositories by saying so, or with `bin/wuwei config repos owner/a,owner/b`.

To run WUWEI in Claude Code on the web too, add `--cloud` and commit `.claude/`; see
[cloud sessions](concepts/cloud.md).

## Your first day

1. Open Claude Code in the workspace directory. The session starts oriented: the way of working,
   the planner charter, your goals and the board.
2. Run `/wuwei-plan`. With no goals yet, it proposes up to three and asks you once. Then the lead
   ranks candidates, you see the plan as a view (`.wuwei/plan.html`), approve or change it, and the
   work starts.
3. Work with the session as usual. You will be asked only one-way, scope, goal, trust,
   infrastructure, owner-review and exception questions.
4. Run `/wuwei-close` when you stop. You get the report and the retro; planning again later
   reopens the day.

## Recommended: give the agents their own identity

The strongest doors live on the code host, not on your machine. Give the agents a GitHub App or
a machine user with write access and no admin rights, protect your default branches with a
ruleset, and keep infrastructure credentials out of the agents' environment. Then a merge without
review is impossible, not only refused. See [the doors](concepts/doors.md).
