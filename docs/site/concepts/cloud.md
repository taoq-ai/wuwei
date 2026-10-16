# Cloud sessions

WUWEI runs in Claude Code on the web the same way it runs on your machine, with two differences a
cloud session forces: a repository's own plugins do not load there, and every session starts from
a fresh clone, so nothing it does not put in git survives.

## Setting it up

In the repository the cloud sessions open, run once:

```sh
bin/wuwei init --cloud
```

and commit `.claude/` to the default branch. It copies the plugin there: the CLI and the charters in
`.claude/wuwei/`, the skills in `.claude/skills/`, the agents in `.claude/agents/`, and the five
hooks in `.claude/settings.json`, pointing at the copy. Run it again after upgrading the plugin to
refresh the copy.

The copy acts only in cloud sessions. On your machine the installed plugin serves, and the copy
stays quiet, so the hooks never run twice.

Cloud sessions run a repository's hooks only when the session holds that one repository. In a
session with two or more, no WUWEI hook fires: the doors are off, owner answers and gate verdicts
are not recorded, and `wuwei doctor` warns `hooks: no hook has fired here`. Open a session that
holds only the repository with `.claude/wuwei/`.

Code-host reads are REST, because cloud sessions refuse GraphQL. Review threads come from the
session's own review-thread route when GraphQL is refused.

## State that survives the session

`.wuwei/` travels on its own branch, `wuwei/state`, never in a working branch (its `.gitignore`
ignores everything, so a PR never carries it by accident).

- At a cloud session's start, the SessionStart hook pulls the branch, and rebuilds `.wuwei/` when
  the clone has none.
- When a cloud session stops, the Stop hook pushes what changed.
- Anywhere, `wuwei sync` pulls then pushes; `/wuwei-close` runs it.

Each clone appends only to its own ledger file, `.wuwei/ledger/<clone>.jsonl`, with its own hash
chain, and pushes only that file. Two sessions working at once never drop each other's records.
Other files follow the last writer; a file changed both here and on the branch keeps the local copy
and says so. Telemetry traces, caches and the canary stay on the machine.

**Why:** a fresh clone that forgot the plan, the rulings and the attestations would ask you again
for everything you already decided. Keeping state beside the code, on a branch no PR touches, lets
every session start where the last one stopped.
