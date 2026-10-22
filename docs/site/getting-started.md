# Getting started

## Requirements

Claude Code, Python 3.11 or newer, Git and the GitHub CLI (`gh`), authenticated. WUWEI installs
no packages: its runtime is the Python standard library.

WUWEI supports macOS, Linux and Windows with Python 3.11 or newer; CI runs the full test suite on
all three with Python 3.11, 3.12 and 3.13. Its hooks look for Python 3.11 or newer in this order:
`WUWEI_PYTHON`, then `python3.15` down to `python3.11`, `python3`, `py -3` (the Windows launcher)
and `python`. The first one at 3.11 or later runs WUWEI. A harness can give hooks a shorter PATH
than your shell, so an older `python3` may come first there, for example macOS's
`/usr/bin/python3` 3.9. When no interpreter fits, every tool call is refused with one line that
names each interpreter tried and its version. Set `WUWEI_PYTHON` to the full path of a 3.11 or
later interpreter to choose one. `wuwei doctor` names the interpreter it runs under and the one
the hooks last used.

On Windows, Claude Code runs hooks through Git Bash, so install
[Git for Windows](https://git-scm.com/downloads/win) and Python from python.org (it brings `py`).

The doors read every command as bash. A command run through PowerShell, cmd, wsl or zsh
(`powershell -Command ...`, `cmd /c ...`) is not unwrapped yet, so Codex on Windows, which runs
PowerShell, and zsh on macOS get weaker doors than bash; a follow-up closes this.

## Install

In Claude Code:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

For a verified install, use the signed `wuwei.tar.gz` release asset: it carries
`MANIFEST.sha256` and its signature.

## Create the workspace

The `wuwei` CLI is not on your PATH; it lives inside the installed plugin. From the directory that
will own the workspace (usually your main repository), call it by its full path:

```sh
WUWEI=$(find ~/.claude/plugins -type f -path '*/bin/wuwei' | sort | tail -n 1)
"$WUWEI" init
"$WUWEI" doctor
```

Once the workspace exists, each session's start prints the path as `WUWEI CLI: <path>`, so the
agents call it without help.

`init` creates `.wuwei/` and merges WUWEI's rules into `.claude/settings.json`: an allow list for
everyday work, deny rules for the doors, ask rules for infrastructure. Your own rules stay as they
are. `doctor` checks the install and prints, per repository, how strongly each door holds.

Add more repositories by saying so, or with `bin/wuwei config repos owner/a,owner/b`.

On Codex, install with `codex plugin marketplace add taoq-ai/wuwei` and `codex plugin add
wuwei@wuwei`, then run `bin/wuwei init --codex`; see [running on Codex](concepts/codex.md).

To run WUWEI in Claude Code on the web too, add `--cloud` and commit `.claude/`; see
[cloud sessions](concepts/cloud.md).

## Your first day

1. Open Claude Code in the workspace directory. The session starts oriented: the way of working,
   the decision and done rules, the board, and where the planner charter and your goals are.
2. Run `/wuwei-run`. With no goals yet, it proposes up to three and asks you once. Then the lead
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
