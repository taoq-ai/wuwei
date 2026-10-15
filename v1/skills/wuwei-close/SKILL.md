---
name: wuwei-close
description: Checkpoint the WUWEI day with the report and the steward's retro. Use when the owner ends the day, pauses, or wants to see where things stand. Closing never locks anything; a later plan pass reopens the day.
---

# /wuwei-close

1. Run `wuwei close`. It writes `.wuwei/days/<date>/report.md` for the day so far.
2. Launch the steward (agent type `steward`) with the report path. It writes
   `.wuwei/retro/<date>.md` with at most three proposals.
3. Apply each proposal that changes how the process runs to `.wuwei/standards.md` (one dated line
   each). A goal change waits for the owner's next plan pass.
4. Send the owner a short summary where the owner reads it (the session, or a DM through the
   connected tools): done, open gaps, exceptions, decisions taken under Assumptions, and the retro's
   proposals. Lead with what needs the owner, if anything.
5. Open items carry to the next pass as they are. Do not ask whether to continue tomorrow.
