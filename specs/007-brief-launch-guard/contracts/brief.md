# Brief and launch contract

`bin/wuwei brief <role> <item> <name> [--worktree PATH] [--pr OWNER/REPO#N]
[--gate] [--track SLICE|FULL]` reads the body on stdin. Success prints its
workspace-relative path. Existing names refuse. Errors never grant launch permission.

Outside a WUWEI workspace, the guard returns 0 before parsing input. In a workspace,
only subagent_type values whose final colon-separated component is a charter stem,
or which start with wuwei:, require a brief. Explore, general-purpose and missing
or empty subagent_type values pass before validation.

Agent tool_input.prompt begins `WUWEI brief: <printed path>` on its own line.
tool_input.subagent_type is the role, optionally plugin-prefixed; optional name must match.
The event kind is `brief written`, payload has name, role, item, path, sha256, gate,
worktree, head and pr. The digest binds the contents; the logged head binds the worktree.
HEAD is rechecked for every worktree brief at launch. Gate safety is fresh.

State seats defaults to an empty object keyed by brief name. An allowed launch reserves
id, role, item, brief, head, status running and started_at while holding state.lock.
Capacity and reuse checks use that same fresh state snapshot. CAP is config.cap for
running builders; config.host.seats caps all running roles. A used brief cannot launch
again, including after the seat stops.

SubagentStop reads the initial user prompt's WUWEI brief marker from
agent_transcript_path and resolves the reservation day from that path, even after
midnight. The agent_type must match the reservation role. A missing transcript,
unmatched brief or mismatched role logs seat stop unmatched and returns 0 without
releasing a seat. Reservation cleanup never blocks a stop.

The seats namespace is reserved against generic state writes. The seat stood down
event kind is reserved and cannot release reservations through wuwei event.
SubagentStop is the only automatic release. A dedicated owner command that refuses
seat callers is a follow-up outside this feature.

Running reservations count toward capacity until stopped. After
host.reservation_timeout_seconds (default 14400), refusals name stale reservations;
staleness alone does not block other items or release capacity.

host.free_memory() returns available bytes: Darwin free + inactive + speculative pages
from vm_stat; Linux MemAvailable from /proc/meminfo. Memory floor is
config.host.free_memory_mb (MiB). Invalid readings are exit 2.
vcs.branches(repo, pattern) returns branch names. Both operations return
registry.Result and accept optional root.

Protected path regexes default to [] in the schema. Owners configure
brief.full_path_patterns; repos[].default_branch supplies the branch default.
