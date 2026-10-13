# Cross Artifact Analysis: Measurement Handoff Gates

**Date**: 2026-10-13

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | The configured floor raises an empty diff to three gates. | Apply a one-quality exception only after confirming the diff is empty. |
| HIGH | A measure label could hide a code change or misattribute an existing PR branch diff. | Compare the measured worktree with its recorded starting HEAD and status. |
| HIGH | The Claude stop hook completed a zero-check build twice. | Return after the first measurement completion. |
| HIGH | A passing measure gate would enter PR raising. | Mark the measurement done at the gate decision. |
| HIGH | A new completion event kind was absent from signal classification. | Use the registered `state.write` event kind. |
| HIGH | Done measurements remained open at close and in report. | Skip status done items in both readers. |
| HIGH | Finished measurements have no report entry. | List the current verdict and workspace-relative file in Done, and include its path in the done action. |
| HIGH | Tiering on a pre-existing PR branch compares against main. | Diff against the builder's recorded starting HEAD when available. |
| MEDIUM | Scratch files are outside the worktree. | Point the gate brief at the recorded handoff and cite only existing workspace artifacts. |
| MEDIUM | An absolute handoff artifact under the workspace is lost by the path scan. | Retain and normalize resolved workspace paths before briefing. |
| MEDIUM | Two different scratch destinations appear in the measurement builder brief. | Name the workspace scratch directory in the Scratch header. |
| MEDIUM | Lead trust and agent flags must keep their gates. | Apply the one-quality exception only when no risk flag is set. |

No unresolved CRITICAL or HIGH findings.
