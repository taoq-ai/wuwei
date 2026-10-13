# Data Model

No schema changes. gate.asked retains session_id and hashed topics for question identity, reply, command hint and token hint. The hook strips trailing context from a recognized generated card identity before hashing. owner.approved consumption remains unchanged. Build and dispatch retain existing workflow transitions.
