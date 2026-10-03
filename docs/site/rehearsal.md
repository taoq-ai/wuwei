# Release rehearsal

The rehearsal drives one item through a real day with real Claude Code seats, real
Git and a real test repository on GitHub. Run it before a release. Every pull
request runs the cheaper scripted day (`tests/test_e2e_day.py`), which uses the
same hooks with recorded adapters.

One item goes through the whole journey: plan and owner approval, a builder, a
failing fast check with a continued builder, three gates with a quality FIX, the
fix round and its delta, a raised PR, one owner decision answered on your
terminal, a merge under the auto-merge policy, and a verified close. When a run leaves
state and evidence disagreeing, see [recovery](recovery.md).

## Prerequisites

- Python 3.11 or newer, Git, `ssh-keygen`, Claude Code and `gh` on `PATH`.
- A terminal. You answer one decision on it, so the rehearsal cannot run in CI.
- A disposable GitHub repository that you own. It needs a default branch with at
  least one commit, no required reviews and no required checks, and merging to it
  must deploy nothing. The rehearsal leaves its merged PR and branch there.

## Variables

| Variable | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude credential. Or pass `--local-login` to use your existing Claude login. |
| `WUWEI_REHEARSAL_REPO` | The test repository as `owner/name`. |
| `GH_TOKEN` | A GitHub token scoped to the test repository only, with contents and pull request write access. |

`GH_TOKEN` is kept in the Claude session environment, because the planner pushes
the item branch and the CLI calls `gh`. Any seat in the session can read it. Use a
fine-grained token limited to the test repository and revoke it afterwards.

## Run

From the repository root:

```sh
export WUWEI_REHEARSAL_REPO=you/wuwei-rehearsal
export GH_TOKEN=<fine-grained token for that repository>
python3 scripts/headless_e2e.py --rehearsal
```

With your Claude login instead of an API key:

```sh
python3 scripts/headless_e2e.py --rehearsal --local-login
```

The runner builds and signs the plugin with a throwaway key, as the headless day
does, and starts under a scratch HOME. It clones the test repository and keeps
`origin`. The workspace uses the GitHub code host, auto-merge with no soak, no
deploy on merge, no required reviewers and your GitHub login as the owner.
Nothing from your own Claude or Git settings is used, and everything is removed
on exit.

## The owner decision

The first session ends after it raises the PR and routes decision `D-1` ("merge
the rehearsal PR today or defer"). The runner then prints
`Rehearsal: confirm decision D-1 option A on this terminal` and runs
`bin/wuwei decision outcome D-1 A` for you. That is the normal owner command: it
shows a digest on this terminal. Review the decision and type the digest to
confirm it within 10 minutes, so stay at the terminal when the first session
ends. The rehearsal adds no bypass. If you decline, the rehearsal fails
before the second session. The second session resumes the first, merges the PR,
waits for `pr state` to report it merged, then writes the report, the retro and
closes the day.

## Bounds

| Session | Turns | USD | Seconds |
| --- | --- | --- | --- |
| First (plan to decision) | 150 | 15 | 1800 |
| Second (merge to close) | 40 | 5 | 600 |

The values are in `REHEARSAL` in `scripts/headless_e2e.py`. An exhausted bound is
unmeasured (exit 2), not failed. The runner validates the newest day under
`.wuwei/days`, so start it well before midnight UTC.

## Output

The first output line after the run is the verdict:

```text
rehearsal pass: interventions 1, elapsed 1260s, cost USD 4.21, refusals 0
```

Each finding follows on its own line. The last line is one JSON object with the
fields `verdict`, `interventions`, `elapsed_seconds`, `cost_usd`, `refusals`,
`findings` and `pr`:

- `interventions`: the planned owner decision plus every manual `state
  transition`, `state set` or `state recover` call. A manual call is also a
  finding, because the product must move every phase itself.
- `refusals`: the reason of every `hook.refusal` event and every CLI call that
  exited 2. They are listed for review and do not fail the run by themselves.
- `cost_usd`: the sum over both sessions, or `null` when a session does not
  report its cost.
- `findings`: each journey step the product did not record, such as a missing
  continue, FIX, delta, PR, decision, merge or close. A step the model skipped is a
  finding, never a pass.

## Exit codes

- Exit 0: pass. Every step was recorded and no finding remains.
- Exit 1: fail. The findings name the missing steps.
- Exit 2: unmeasured. A missing credential, missing or invalid
  `WUWEI_REHEARSAL_REPO`, missing `GH_TOKEN` or no terminal is reported before any
  external call. Runtime errors, exhausted bounds and unreadable evidence are also
  unmeasured. Unmeasured is never a pass.
