# Data model

Native rows have increasing nonnegative ordinals, an outer type and an object payload. The first row is session_meta at ordinal zero. Its id identifies the native thread. A child carries parent_thread_id, agent_role, agent_path, thread_source=subagent and a nonnegative subagent_history_start_ordinal. Rows at or before the boundary are inherited and cannot prove the child report or settings. This includes inherited parent session_meta rows; first child metadata still owns identity. Additional metadata after the boundary is invalid.

A parent function_call for collaboration.spawn_agent pairs with a later function_call_output by call_id. The requested role and task_name must match child metadata and the canonical path under the parent. Exactly one pair is accepted.

The latest own assistant message with phase final_answer supplies report text. A later event_msg task_complete, when present, must name that text. The trusted SubagentStop must name the same text or leave it empty for transcript selection.

Child turn_context supplies recorded model and reasoning effort after the fork and before the report. Missing settings remain unmeasured. Existing seat.started requested and parent fields stay intact; attestation uses child recorded settings separately from provider-resolved model.

Ordinary native canonical paths remain the ledger and board identity, scoped by session. Credential/canary-bearing identities instead use a stable SHA256 key at both start and verified stop. Existing report filenames hash the persisted identity; native notification authors use the same mapping for comparison. Existing pending/kept report versions and atomic os.replace claims are reused.
