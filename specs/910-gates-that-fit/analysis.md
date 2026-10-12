# Analysis: 910-gates-that-fit

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | HIGH | A guard that refuses a builder when the other holders reach CAP deadlocks once CAP drops below the builds in a build phase and all of them are stopped: each sees CAP others. | A builder launches while its item is among the first CAP holders in plan order, or a slot is free (`slot`). The holders never wait on the rest. |
| A2 | HIGH | The launch set offered builder continuations and fix rounds without a CAP check, so the guard could refuse what `next` offered and the seat would run unregistered (#837). | `launch_set` waits any build or fix kind builder launch that fails `slot`, the guard's own test. |
| A3 | MEDIUM | The #845 window room never covered a second opinion unless its runtime was also in the seat policy; `windows` was not asked for it. | The runtime of `gates.second_opinion` joins the runtimes `launch_set` reads. |
| A4 | MEDIUM | Fitting seats before the memory hold would spend window room on a set that does not launch. | The subset is taken only in its own branch, after the memory hold and the CAP check. |
| A5 | MEDIUM | A long-running build ahead in plan order now holds a fix round behind it at CAP, where the old guard let it in while that builder was stopped. | Accepted: it is the rule new builds already follow, and the lead charter says a slot frees at builder handoff. |
| A6 | LOW | The batch is not offered again until all its seats stop (`derive.offers` skips an item with a running seat), so a freed host seat can go to a build meanwhile. | Kept: the decision code is #902's; within a sweep gates still launch before builds. |
| A7 | LOW | The concurrent-reservation test relied on CAP; CAP no longer reads reservations. | It races on the host seat ceiling instead, which still does. |
| A8 | LOW | The guard's CAP refusal text changed. | `guards.CAPACITY` names `build slots`, so it stays log-only (#837). |
| A9 | HIGH (review F1) | The design spec is owner-only; an amendment was written there under the owner's name. | Reverted; the wording is a proposed amendment in the spec's Assumptions. |
| A10 | MEDIUM (review F2) | The slot count read the state captured at the start of the sweep, so a fix round opened in it was not counted and builds past CAP were offered. | The count is read fresh at the CAP check and after the offers; a test opens a fix in the sweep. |
| A11 | LOW (review F3) | Only the sweep that deferred held new builds; a seat freed while the first batch ran went to a planned build. | `gate_waits` also holds while an initial gate batch runs with seats left to launch; tested. |
| A12 | LOW (review F4) | A #904 environment hold keeps its slot. | Recorded under Assumptions. |

No open CRITICAL or HIGH findings. Every FR maps to a task and a test.
