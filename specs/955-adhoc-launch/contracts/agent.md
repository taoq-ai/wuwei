# Agent Contract

PreToolUse Agent accepts a nonempty prompt, description and known WUWEI agent
type. With no WUWEI brief marker it registers the prompt after existing launch
checks; an explicit marker requires the existing logged, unmodified brief.
Returns 0 on registration, 1 on policy refusal, 2 on unavailable evidence.
SubagentStop resolves the original prompt digest or brief reference and runs
the existing stop logic. CLI seat start --adhoc remains supported.

Typed WUWEI ad-hoc launches require a planner caller (no agent_id) and exclude the planner
role. Bind an item only from name, description or an explicit Item: prompt line.
Item-bound builders follow the #901 refusal under guards.enforce; unbound
builders count against CAP. A seat carrying prompt_sha256 never supplies a
dispatch.receive gate verdict. Transcript identity comes only from its first
prompt, so a continue message cannot rebind a seat.

Untyped nested launches retain #676 registration. Builder refusal checks every
named plan item, including ambiguous metadata. Prompt sentinels never count
toward gate batches. Pending same-prompt launches in a role and session must
share one item; otherwise retry with an Item: line to make identity explicit.
