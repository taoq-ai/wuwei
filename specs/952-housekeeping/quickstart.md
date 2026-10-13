# Quickstart
Run `bin/wuwei doctor --section processes` to inspect cached-state process findings.
Run `bin/wuwei next --housekeeping` to reap matching owned waits. Doctor processes and close
show the plain listing for manual cleanup. Current stale seats use their existing recovery commands.
Normal next wraps only PR waits and timers. SessionStart and next skip cwd probes.
Close reaps before retro. Failed reaps are findings rather than repeated duties.
Close prints unmeasured inspection and continues; a reap that fails in that close
attempt still stops it. Only a live wait for the current session and day makes next
passive. Other-session and prior-day recorded waits are obsolete cleanup candidates.
Housekeeping refuses extra argv even when combined with the background flag.
