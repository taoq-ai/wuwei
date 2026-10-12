# Quickstart: check the scanner fixes live

The audit's scratch workspace (`ws/`): three repos and bare origins, a scratch `HOME`,
`code_host = "none"`, `spec.mode = "off"`, `adapters.scanner = "ziran"`, ZIRAN 0.40.0 on
`PATH`, offline. Repos: `audit/agent-svc` (a Python agent service), `audit/web-app`
(TypeScript, no `.py`), `audit/util-lib` (small library). For the slow runs `util-lib`
gets a gitignored `.direnv/` of 14 792 `.py` files; a bare `ziran audit` of it takes 85.6 s,
over the adapter's 60 s timeout. Each command runs from `ws/` with `HOME`,
`WUWEI_WORKSPACE` and `WUWEI_NOW` set to a scratch day; `bin/wuwei` is this branch's.

## Before and after

Before: the audit at `b9774292` (0.29.0). After: this branch, same workspace.

| Finding | Command | Before | After |
| --- | --- | --- | --- |
| S1 | `bin/wuwei seat brief lead day lead-s1b --body "..."`, agent-svc at its SA002 commit | 1.33 s, `Source scanner: unmeasured: audit/agent-svc: ziran audit: unmeasured: ValueError: invalid audit finding` | 0.67 s, `Source scanner: measured: 16`, ids `audit/agent-svc:scanner:SA002:<path>/app.py:0` |
| S2 | same brief, web-app has no `.py` | 1.31 s, `unmeasured: audit/web-app: ... invalid or empty audit measurement` | measured, web-app contributes 0 rows |
| S3 | `bin/wuwei seat brief lead day lead-slow ...`, util-lib slow | 0 candidates, agent-svc's rows dropped | `Source scanner: measured: 16; unmeasured: audit/util-lib: ziran audit: unmeasured: TimeoutExpired; run bin/wuwei config set adapters.scanner '"none"' to switch the scanner off`, 8 scanner candidates |
| S4 (#862) | first `seat brief lead` of the day, slow repo | 63.18 s | 64.79 s (the one timeout of the day) |
| S4 (#862) | `bin/wuwei plan propose lead.json`, then again | 62.99 s, 64.83 s, both `TimeoutExpired` | 0.59 s, 0.55 s, the remembered `TimeoutExpired` |
| S5 | `bin/wuwei seat brief steward day steward-probe ...` 3 s into the slow lead brief | 30.17 s, exit 2, `brief.lock remained locked for 30s` | 0.17 s, written |
| P4 | `bin/wuwei plan propose lead.json` on the approved day, slow repo, no cache | 3.91 s (62 s with the slow repo), then refused | 0.15 s, `morning gate already approved` |
| S6 | `bin/wuwei plan resume AUD-1` (card answered Yes), then three trace sweeps | the next sweep parks AUD-1 again; 67 `scanner.finding` rows for 5 chains after ten sweeps | AUD-1 stays `planned`; `scanner_owed: 0` and no new `scanner.finding` on each sweep (0.48 to 0.60 s) |
| S7 | `bin/wuwei close` with 5 critical chains today | 5 cards, one close run each | 1 card in 0.64 s naming `Bash -> Edit; Bash -> WebFetch; Bash -> Write; Read -> WebFetch; Write -> Bash`; after one Yes the scanner no longer holds the close |
| S8 | `scanner.rows` on the AUD-1 worktree, as `dispatch receive` calls it | 14 rows, 14 block, all already on main | 0 rows (the item changed no file); had it changed `tools.py`, that file's 4 rows block |

## Commands

S1 to S3 on a fresh day (`WUWEI_NOW=2026-10-13T08:00:00+00:00`):

```bash
bin/wuwei plan session verify-planner
bin/wuwei seat brief lead day lead-s1 --body "Discover today's work."
grep '^Source scanner' .wuwei/days/2026-10-13/briefs/lead-s1.md
# Source scanner: measured: 16
```

S4 and S5 on another fresh day with the slow util-lib (`WUWEI_NOW=2026-10-14T08:00:00+00:00`):

```bash
bin/wuwei seat brief lead day lead-slow --body "Discover today's work." &   # about 65 s, once
sleep 3; bin/wuwei seat brief steward day steward-probe --body "Probe."     # returns at once
wait
bin/wuwei plan propose lead.json   # under 1 s
bin/wuwei plan propose lead.json   # under 1 s
grep discovery.scanner .wuwei/days/2026-10-14/plan.md
# - discovery.scanner: measured: 16; unmeasured: audit/util-lib: ziran audit: unmeasured: TimeoutExpired; run bin/wuwei config set adapters.scanner '"none"' to switch the scanner off
cat .wuwei/days/2026-10-14/scanner-audit.json   # one entry per repo: head plus rows or reason
```

S6 and S7 on the audit's day (`WUWEI_NOW=2026-10-12T16:00:00+00:00`), where AUD-1 is parked
by a scanner chain:

```bash
bin/wuwei plan resume AUD-1          # Owner step card; answer Yes, then run it again
bin/wuwei plan resume AUD-1          # AUD-1: resumed
# a trace sweep (dispatch receive and close run it): AUD-1 stays planned, scanner_owed 0
bin/wuwei plan park AUD-1 --reason "verify close"
bin/wuwei close                      # exit 1, one Owner step card naming all five chains
```

A new HEAD in a repo, or the next day, audits it again. A fast failure (ZIRAN missing) is
not remembered, so installing ZIRAN takes effect on the next call.
