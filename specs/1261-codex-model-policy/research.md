# Research

- Source policy: charters/planner.md and agents.TABLE. Standard is the role-file tier because files cannot know an item.
- Current local Codex catalog, $CODEX_HOME/models_cache.json, read 2026-10-27: gpt-6.1-sol and gpt-6-astra support low through ultra; gpt-6-luna supports low through max. Defaults vary, so generated roles set effort explicitly.
- Active collaboration.spawn_agent schema supports agent_type, model and reasoning_effort. Full-history forks reject overrides; this is a requested fork policy, not measured child settings.
- Existing Codex fixtures return task_name or agent_id without resolved metadata. Preserve explicit response.resolvedModel only; launching payload.model names the parent turn.
- Existing models values accept a model plus effort. Native owner IDs remain requests; availability is unmeasured. No model registry or validation framework is added.
