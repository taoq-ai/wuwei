---
name: wuwei-report
description: Complete the steward retro and present the daily owner report.
---

# /wuwei report

Run `wuwei next` first and follow the step it names; run the steps below when it names this skill or the owner asked for it. Run inside a WUWEI workspace using the executable recorded in `.wuwei/executable`. Never invoke Python without `-P`.

1. Follow `/wuwei retro` through the close check. Do not count a proposal as applied until `wuwei promote` lands it.
2. Run `wuwei report` and present the local report to the owner. It shows outcome measures beside the owner's baseline, open work, parked work and its decisions, answered decisions and carry. Keep unavailable measures as `unmeasured`.
3. Run `wuwei close` and resolve findings. The Stop hook is the final close guard.

The report is local owner text. Any outward post must use the existing outbound tier and stay a draft when that tier requires approval.
