# Data Model

Existing seats retain id, role, item, brief, head, status and started_at.
Automatically registered seats additionally carry prompt_sha256 and
launcher_session_id, which keeps a stopped seat bound to its runtime identity. Their brief
is the private original prompt, saved atomically with mode 0600. Seat/event
metadata never contains its body. Running seats transition through existing
stopped or unmeasured states. Existing trace_sessions and transcript fields
bind runtime identity and enable terminal-report recovery.
