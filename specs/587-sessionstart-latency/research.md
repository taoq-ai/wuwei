# Research: SessionStart latency (#587)

Host: the pipeline Mac (10 CPUs), Python 3.12, load 9 to 19 during every run, so wall is
load-bound and CPU (`RUSAGE_CHILDREN`, sh launcher, interpreter and its children) is the
local figure. Fixture: `seeded_workspace` from `tests/test_hooks.py` (signed plugin copy,
1000 note events, a raised item, a running seat), SessionStart payload, `reset()` before
every run, first two runs dropped.

## Method

- Split: the hook process with only one guard run (fresh interpreter, warm bytecode).
- Interleaved A/B: the fixture's plugin copy and a second copy with the candidate change,
  each re-manifested and re-signed with the fixture key, run alternately 40 to 60 times,
  same output asserted. An A/A control (both copies unchanged) moved 0.1 to 3.2 ms, which
  is the noise floor of a median.
- Module sets: `LAUNCHER_MODULES` dumps `sys.modules` at exit (as the existing pins do).
- `-X importtime` without threads, and cProfile of each guard in-process with the
  integrity `together` calls made sequential.

## Figures (CPU unless named)

| Run | Median | Note |
| --- | --- | --- |
| bare hook (`hook` + `env` imports, no guard) | 17 to 18 ms | `python3 -I` floor 17 ms |
| session guard alone | 28 to 29 ms | about 11 ms above the bare hook |
| integrity guard alone | 81 ms | about 37 ms in `git` and `ssh-keygen` children on this Mac |
| full SessionStart | 94 to 110 ms | wall median 65 to 93 ms |

| Candidate (A/B, 40 to 60 pairs) | CPU median change | Wall median change |
| --- | --- | --- |
| imports: promotion, digest, decision, ssh adapter | -6.3 to -6.7 ms | -6 to -7 ms |
| SessionStart guards in turn, not on two threads | -4.8 to -6.4 ms | -2 to -3 ms |
| both | -7.7 to -9.7 ms | -2 to -6 ms |
| all integrity threads removed too | -13.5 ms | +33 ms (children no longer overlap); rejected |
| deferring `brief` and `discovery` in `watch` | +2.7 ms | none; rejected |
| a faster inventory loop (string paths, a regex for control characters) | about -0.4 of 4 to 5 ms | rejected as noise |

Modules loaded by SessionStart: 143 now, 122 with the import cuts. SessionStart-only
modules against the PreToolUse `git commit` path: 32; their import self time is about
3.8 ms on a quiet run, so most of the gain is the import plus the interpreter-lock
contention it adds.

## Rejected

- Fewer syncs on the integrity verdict records or the session registry write: records,
  and the runner's sync latency cannot be measured from here.
- Caching the signature verification or the inventory: the verdict record is writable by a
  seat (design 9.1), so a cached result would be forgeable trust.
- Removing the integrity guard's own `together` calls: they overlap the Git and
  `ssh-keygen` children with hashing, the one overlap that pays on two CPUs.
- `config.toml` is read seven times per SessionStart (served from the in-process parsed
  copy). Not measured: the installed WUWEI hook refused writing a scratch `config.toml`
  for the timing, and the read is a few hundred bytes.
