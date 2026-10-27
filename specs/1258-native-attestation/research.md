# Research

- Decision: Accept only the account-derived default `.codex/sessions` root. Rationale: observed native producer root and existing account lookup. Alternative: configurable roots would add trust scope and configuration.
- Decision: Require the first metadata record and own rows after the fork boundary. Rationale: full-history children retain parent reports. Alternative: scanning any final accepts inherited evidence.
- Decision: Correlate parent spawn call and result, role, native id and canonical path. Rationale: the actual spawn result is a JSON string containing task_name, while the stop supplies the native UUID.
- Decision: SubagentStop proves completion; any available later task_complete must agree. Rationale: the observed completion record followed the callback, so waiting could deadlock callback progress.
- Decision: Retain the existing report store. Rationale: item 1254 already owns latest valid versions and atomic race handling.
- Decision: Use child turn_context after the fork for recorded model/effort. Rationale: parent settings and the stop model cannot measure the child. Provider resolution stays unmeasured unless supplied.
- Decision: Ordinary owner answers remain unconfirmed. Rationale: their origin boundary belongs to separate item 1260.
