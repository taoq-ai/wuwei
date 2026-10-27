# Native evidence fixture

`native-evidence.json` retains sanitized producer shapes from the 2026-10-27 native parent/child probe. Original row digests identify the discovery source; they do not hash the sanitized fixtures. Identifiers and workspace paths are replaced. The test expands `<task-root>` to the native canonical task root, which is an identity rather than a filesystem home. The parent tool call uses collaboration.spawn_agent, while the observed hook transport uses collaborationspawn_agent. Function output is a JSON string carrying task_name. Native state rows and turn_context payloads have no inner type; additional tests reconstruct those observed shapes with synthetic values.

The fixture is test data, not a real approval or attestation. Owner-answer records are excluded from this feature. The full report body is retained so the exact final-answer notification can be checked against its report.
