# Quickstart: live Codex smoke for #871, #860 and #873

A throwaway workspace with a throwaway git repository. It checks, against the real Codex
companion: the doctor row for an empty `codex.command` (#860), one round with two second
opinions that both start (#871), a forced job failure that frees its seat, names the error
and relaunches on rerun (#871), and one Codex builder (#871, the retro lines in its prompt).

Two steps are scratch shortcuts that write day state with the CLI's own `wuwei.state` module
instead of running the morning gate and two Claude builders. Everything after them is the
real CLI.

The same script ran offline with a stand-in companion (a Python script answering `task`,
`status` and `result`); the expected lines below come from that run, except where marked
"varies".

## Setup

Set these first. `WT` is this worktree; the companion path is the installed Codex plugin's.

```bash
WT=<path to this worktree>
W=$WT/bin/wuwei
COMPANION=$(ls ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | tail -1)
MODEL=gpt-5.4            # any model your Codex login runs
S=$(mktemp -d)
cd "$S"
export WUWEI_WORKSPACE="$S"
```

## 1. Workspace and repository

```bash
git init -q -b main repo
git -C repo -c user.name=t -c user.email=t@e commit -q --allow-empty -m init
git init -q --bare origin.git
git -C repo remote add origin "$S/origin.git"
git -C repo push -q origin main
"$W" init . > /dev/null 2>&1; echo "init exit $?"
```

Expected: `init exit 0`.

## 2. Config with the second opinion on and `codex.command` still empty (#860)

```bash
python3 - "$MODEL" <<'EOF'
import sys, pathlib
path = pathlib.Path('.wuwei/config.toml')
text = path.read_text()
text = text.replace('[gates]\n', f'[gates]\nsecond_opinion = "codex:{sys.argv[1]}"\n', 1)
text = text.replace('code_host = "github"', 'code_host = "none"', 1)
text = text.replace('engine = "speckit"', 'engine = "none"', 1)
text = text.replace('seats = 0 #', 'seats = 8 #', 1)
text += ('\n[[repos]]\nname = "scratch/repo"\npath = "repo"\ndefault_branch = "main"\n'
         'fast_checks = ["true"]\nidentity = { name = "Scratch", email = "scratch@example.test" }\n')
path.write_text(text)
EOF
"$W" doctor 2>&1 | grep -A1 "codex.command"
```

Expected, one warn row naming the script `COMPANION` points at:

```text
  warn       codex.command: codex.command empty: runtime codex unavailable; companion found at <COMPANION>
      fix: <WT>/bin/wuwei config set codex.command '["node", "<COMPANION>"]'
```

## 3. Set `codex.command` (the throwaway config is edited in place)

```bash
python3 - "$COMPANION" <<'EOF'
import sys, pathlib
path = pathlib.Path('.wuwei/config.toml')
path.write_text(path.read_text().replace('command = [] #', f'command = ["node", "{sys.argv[1]}"] #', 1))
EOF
"$W" doctor 2>&1 | grep -c "codex.command"
```

Expected: `0` (no row once the command is set).

## 4. The day, three items, worktrees and builder briefs (scratch shortcut for the gate)

```bash
PYTHONPATH="$WT/cli" python3 - "$MODEL" <<'EOF'
import sys
from wuwei import state
state._write_state(lambda d: d.update(gate_approved=True, goals=['G-1'], seat_policy={
    'builder': {'runtime': 'codex', 'model': sys.argv[1]}}), '.')
EOF
for item in A B C; do
  flag=""; [ "$item" != C ] && flag="--trust-surface"
  "$W" plan add $item --goal G-1 $flag > /dev/null; echo "plan add $item exit $?"
  "$W" worktree add $item > /dev/null; echo "worktree add $item exit $?"
  "$W" seat brief builder $item builder-$item --worktree worktrees/$item --body "Add $item.txt with one line." > /dev/null
  echo "seat brief builder $item exit $?"
done
```

Expected: nine lines, each `exit 0`. A and B carry `trust_surface`, so they tier STANDARD
and get the second opinion.

## 5. A and B built and at the gate (scratch shortcut for two builders), then their gate briefs

```bash
for item in A B; do
  echo "change $item" > worktrees/$item/$item.txt
  git -C worktrees/$item add . && git -C worktrees/$item commit -q -m "change $item"
done
PYTHONPATH="$WT/cli" python3 - <<'EOF'
from wuwei import state
for item in ('A', 'B'):
    state.transition(item, 'implement', '.')
    state.transition(item, 'gate', '.')
state._write_state(lambda d: d['seats'].update({f'builder-{i}': {
    'item': i, 'role': 'builder', 'status': 'stopped'} for i in ('A', 'B')}), '.')
EOF
for item in A B; do
  "$W" dispatch next $item > next-$item.json; echo "dispatch next $item exit $?"
  python3 - "$W" next-$item.json <<'EOF'
import json, shlex, subprocess, sys
action = json.load(open(sys.argv[2]))
print('  tier', action['tier']['tier'], 'roles', action['roles'])
for command in action.get('commands', []):
    code = subprocess.run([sys.argv[1], *shlex.split(command)[1:]], capture_output=True).returncode
    print('  ran', ' '.join(shlex.split(command)[1:6]), 'exit', code)
EOF
done
```

Expected, for each of A and B:

```text
dispatch next A exit 0
  tier standard roles ['arch', 'quality', 'security', 'quality@codex']
  ran seat brief arch A arch-A exit 0
  ran seat brief quality A quality-A exit 0
  ran seat brief security A security-A exit 0
```

## 6. One round: both second opinions are runs

```bash
"$W" dispatch next --all > round.json; echo "dispatch next --all exit $?"
python3 - <<'EOF'
import json
for entry in json.load(open('round.json'))['entries']:
    print(' ', entry['item'], entry['action'], [seat['command'] for seat in entry.get('seats', []) if 'command' in seat])
EOF
```

Expected (C waits because gates launch before new builds):

```text
dispatch next --all exit 0
  A gates ['wuwei dispatch opinion A']
  B gates ['wuwei dispatch opinion B']
  C wait []
```

## 7. A forced job failure frees the seat and names the error

`CODEX_HOME` pointing at an empty directory gives the Codex app-server no login and no state,
so the job fails. (A plain file would not do: the start lock lives in `CODEX_HOME`, so the
dispatch would refuse before any job starts.)

```bash
mkdir "$S/empty-codex-home"
CODEX_HOME="$S/empty-codex-home" "$W" dispatch opinion A; echo "opinion A exit $?"
PYTHONPATH="$WT/cli" python3 -c "from wuwei import state; s = state.read_state('.')['seats']['quality-A-codex']; print('  seat', s['status'], '|', s.get('failed', '')[:90])"
```

Expected (the error text after `runtime seat failed:` varies; it is the companion's
`errorMessage`, or the failed turn's summary):

```text
wuwei dispatch: runtime seat failed: <companion error>; rerun the same command to relaunch it, and run bin/wuwei doctor if it fails again
opinion A exit 2
  seat stopped | runtime seat failed: <companion error>
```

If the job does not fail (the companion reused an app-server broker that a previous run in
this worktree started), skip this step: it then proves nothing, and step 8 still runs.

The companion keeps one app-server broker per worktree. The broker this step started runs
under the empty `CODEX_HOME`, and step 8's relaunch in the same worktree reuses it and fails
again (live smoke L3). The companion has no stop command; its own `SessionEnd` hook stops the
broker, so run it for worktree A from the same shell before step 8 (or redo step 7 in a
worktree step 8 does not use):

```bash
echo "{\"cwd\": \"$S/worktrees/A\"}" | node "$(dirname "$COMPANION")/session-lifecycle-hook.mjs" SessionEnd
```

## 8. Both second opinions at once (they start one after the other)

```bash
"$W" dispatch opinion A > opinion-A.json 2> opinion-A.err &
"$W" dispatch opinion B > opinion-B.json 2> opinion-B.err &
wait
for item in A B; do
  python3 -c "import json,sys; v = json.load(open('opinion-$item.json')); print('  $item', v['role'], v['verdict'])" 2>/dev/null || cat opinion-$item.err
done
```

Expected: A is a new job (the rerun relaunches after step 7), and both finish:

```text
  A quality@codex <PASS or FIX>
  B quality@codex <PASS or FIX>
```

The verdict varies with the model. Codex cannot write the day directory from its sandbox,
so WUWEI writes each job's final message to `.wuwei/days/<date>/decisions/gate-quality-<item>-codex.md`;
that file starts with `Verdict:` and holds the `Head:`, class-sweep, `Simplicity:` and `Design:`
lines (live smoke L1). Prose about a rejected verdict write there means the verdict format did
not reach the seat. A `retro note missing` line means the retro contract did not reach it (the
#871 field comment); a `REJECT` from the verdict lint is the model's verdict format, and
rerunning `dispatch opinion <item>` continues the same thread, asking for the whole verdict as
the final message. The B job starts only after A's job has its thread: the companion's job
list (`node "$COMPANION" status --all` in each worktree) shows B created a few seconds after
A, not 0.3 s.

## 9. One Codex builder

```bash
"$W" build C .wuwei/days/*/briefs/builder-C.md worktrees/C; echo "build exit $?"
PYTHONPATH="$WT/cli" python3 -c "from wuwei import state; d = state.read_state('.'); print('  C', d['items']['C']['phase'], d['builds']['C']['status'])"
git -C worktrees/C log -1 --format='  %an %s'
git -C worktrees/C status --porcelain | wc -l
```

Expected, after the Codex job finishes (minutes). The job leaves its changes uncommitted (the
worktree's git metadata is outside its sandbox), and WUWEI commits them with the repository
identity from step 2 (live smoke L2):

```text
build exit 0
  C gate done
  Scratch chore(C): Codex builder changes
       0
```

A build that ends with HEAD still at its start head, or with uncommitted changes, is not done:
the loop continues the job with `no change over the start head` or `uncommitted changes`. A
second unchanged head parks C with `no change over the start head`; repeated uncommitted
changes park it after `build.stuck_after`. C never reaches `gate` on an unchanged head. A
credential file the job left (for example `.env`) is never committed: the job continues with
`private files .env: remove them or add them to .gitignore`. One the job committed itself, even
if a later commit deletes it, is caught too, before the gates: the job continues with `git reset
--soft <start>`, remove the files, add them to .gitignore, and commit again.

A `build exit 2` with `runtime seat failed: <error>` leaves the build `ready`; rerunning the
same `wuwei build` command dispatches a new job.

## Cleanup

```bash
cd / && rm -rf "$S"
```
