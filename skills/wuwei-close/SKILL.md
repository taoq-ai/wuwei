---
name: wuwei-close
description: Checkpoint the WUWEI day with the report and the steward's retro. Use when the owner ends the day, pauses, or wants to see where things stand. Closing never locks anything; a later plan pass reopens the day.
---

# /wuwei-close

1. Run `wuwei close`. It writes `.wuwei/days/<date>/report.md` for the day so far; a second close
   the same day starts with what changed since the first.
2. Launch the steward (agent type `steward`) with the report path. It writes
   `.wuwei/retro/<date>.md` with at most three proposals: defect vaccines, calibration and yield
   findings, skills and memory lines for a repository, rules to retire.
3. Apply each proposal that changes how the process runs to `.wuwei/standards.md` (one dated line
   each). A proposal for a repository's `CLAUDE.md`, `AGENTS.md` or skills becomes a light plan item,
   built and reviewed like any change. A goal change waits for the owner's next plan pass.
4. Send the owner a short summary where the owner reads it (the session, or a DM through the
   connected tools): what needs the owner first, then done, open gaps, escapes, exceptions,
   andon, decisions taken under Assumptions, the weekly sample PR and the retro's proposals.
5. Run `wuwei sync` so the state survives this machine or session (it pushes `.wuwei/` to the
   `wuwei/state` branch; outside a git repository it says the state stays local).
6. Open items carry to the next pass as they are. Do not ask whether to continue tomorrow.
