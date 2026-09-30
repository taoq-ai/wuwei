---
name: wuwei-retro
description: Compile the steward retro, promote supported charter learnings, and check close evidence.
---

# /wuwei retro

Run inside a WUWEI workspace using the executable recorded in `.wuwei/executable`. Never invoke Python without `-P`.

1. Run `wuwei close` first if it has not run today. It runs the close steward review once and prints `steward_launch`; launch that steward with Agent exactly as returned. It then refuses until the retro exists. Do not run `wuwei steward run --trigger close` yourself: a second close review the same day writes no brief and says so. Read captured role notes, verdicts, events and the steward metrics.
2. Run `wuwei retro`. Review the per-role table, cycle table and generated proposals. A `Change: Hard rule: ...` note becomes a pending owner decision record. Do not edit a guard or hard rule from the retro.
3. Run `wuwei promote` to land supported charter proposals. Inspect rejections and resolve them through a corrected proposal when evidence warrants it. Promotion writes the charter, dated changelog and ledger in a local commit with the promotion trailer.
4. Run `wuwei retro` again so Applied reflects landed proposals. Run `wuwei close --check retro` and address any owed or unmeasured evidence before closing the day.
