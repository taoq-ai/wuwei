# Report, telemetry and DORA

## The report

`wuwei report` (and each checkpoint) shows the day from the records, never from memory:

- plan passes, checkpoints, items done and parked, and what changed since the last checkpoint;
- the board;
- every merge, and whether it went through WUWEI's check or was an exception;
- the doors: refusals and their reasons, questions sent back to the model, infrastructure asks,
  notes and Stop reminders;
- your prompts;
- seats and verdicts;
- learning: escaped defects traced to their gates, each repository's change failure rate and
  whether its tiers are raised, unplanned PRs, gate yield, tokens by role, open exceptions, the
  weekly sample;
- telemetry: tool calls, outward calls, hook errors;
- the ledger's integrity.

**Why:** you should never have to ask where things stand, and nothing the team did should be
invisible.

## DORA

`wuwei report --dora` gives the four keys per repository from the code host alone: lead time (PR
open to merge), deployment frequency (deployments, or releases when a repository never deploys),
change failure rate (change failures over merges, at most 1) and time to restore. A change failure is
a revert (a merged PR whose title starts with the word revert) or a run of failed production
deployments until the next green deployment of the same environment. Production means an environment
GitHub flags as production, or one named with prod or production as a word (not preprod, pre-prod or
non-prod); only the newest 100 production deployments in the window are read. Time to restore is the median time from the
first failed deployment of a run to that green one, unmeasured when nothing was restored.

**Why:** reading the code host means the history is complete from day one, even for work done
before WUWEI or without it.

## Telemetry

Every tool call is a line in `.wuwei/traces.jsonl` (session, agent, tool, a short target with
secrets redacted, duration). It stays on your machine. `telemetry = false` turns it off.

## The ledger

`.wuwei/ledger/` records what cannot be read from git or the code host: plan changes,
attestations, rulings, exceptions, refusals, andon, checkpoints. Each clone writes its own file,
`<clone>.jsonl`, so sessions syncing through git never edit the same rows; a 0.34-era
`ledger.jsonl` is still read. Each row carries the hash of the row before it in its file and a
format version. `wuwei verify` checks every chain; a broken link names its file and line.

**Why:** an audit trail is only worth something if editing it shows.

## Replay cases

`wuwei evidence owner/repo#n --record <dir>` saves a real PR's code-host answers, a copy of the
workspace, the clock and the gaps WUWEI found. Copy the directory under `tests/replay/` and every
future version of WUWEI must give the same answer for it.

**Why:** the auditor is held to its own past answers. A change that would have passed a PR it once
refused shows up as a failing test, not as a surprise.
