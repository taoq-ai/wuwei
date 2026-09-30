# Research: Hook latency and corrupt state

## Method

A copy of the v0.5.0 dry-run workspace (paths rewritten to the copy, originals untouched)
was driven through the release `bin/wuwei hook <event>` with the dry run's stubs on PATH:
15 runs per path for wall and child CPU, and one cProfile run per path through
`wuwei.__main__.main` with `subprocess.run` timed. Host load was about 6 on 10 CPUs, so
absolute numbers are high; the call counts are what matter.

## Findings

| Path | Wall med | CPU med | Subprocesses | Main cost |
|---|---|---|---|---|
| PreToolUse `ls` | 66 | 61 | 0 | start (17 ms) plus imports (35 to 40 ms) |
| SessionStart | 114 | 105 | 3 (ssh-keygen, git status, git log) | integrity measure, config parsed 5 times (1.3 ms each) |
| PreToolUse `git commit` | 147 | 133 | 8 git | two `commit_context` calls, 4 sequential git each |
| PreToolUse `git push` | 221 | 199 | 16 git | as commit, plus `push_context` 6 and `push_commits` 2 |
| SubagentStop builder | 216 | 203 | 5 gh | seat-free `discovery.intake` inside the hook |
| Stop planner turn | 268 to 310 | 252 to 288 | 6 to 7 gh | `pr_actions.evaluate` live evidence per owned PR |

One git process costs about 10 ms wall and CPU on the owner's host (`/usr/bin/git` is the
Xcode shim). `read_state` costs 0.13 ms at the dry-run state size, so state reads are not
cached. `load_config` costs 1.3 ms and runs five times per hook.

A truncated `state.json` gives `state.json: Unterminated string ...` in `wuwei state get`,
SessionStart ("memory unmeasured", "session continuity unmeasured") and Stop ("Stop
unmeasured", blocking), and `wuwei state recover` does not exist.

## Decisions

- Stop per turn trusts the watch's record, not the network, when it is fresh and clean.
  Rejected: a cheaper fake `gh` in the benchmark (meets the number, not the problem, since
  a real code host makes each read a network call); caching raw evidence (comment bodies
  in state).
- Seat-free discovery runs in the watch. Rejected: keeping it in the hook with fewer
  sources (still network).
- Commit and push keep every git read and run independent reads concurrently with
  `concurrent.futures`. Rejected: dropping the effective identity reads on push (loosens
  the guard), parsing git config files or `git var -l` in Python (re-implements git),
  combining reads into one `rev-parse` with mixed modes (fragile).
- Recovery restores a writer-made snapshot. Rejected: replaying `events.jsonl` (payloads
  are summaries, not state); hard-linking the previous inode (loses the last write and a
  same-inode truncation also breaks a link of the current file).
- Lazy imports are not planned: the measured paths are dominated by subprocesses. If a
  path is still over budget after the cuts, move module-level imports of `watch`,
  `closing`, `pr_actions` and `memory` in `cli/wuwei/guards/stop.py` and
  `cli/wuwei/guards/lifecycle.py` into their check functions, and measure again.
