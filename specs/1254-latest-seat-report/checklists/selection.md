# Approved selection checklist

- [x] Record the owner's explicit approval of the additional design round.
- [x] Validate an entry before it can establish a newest-version marker.
- [x] Reject directory, dangling link, symlink, FIFO, invalid UTF-8, empty, blank, and unreadable entries.
- [x] Reject malformed agent, role, version, and extra filename components.
- [x] Exercise pending and archive placement through the real hook consumer.
- [x] Validate moved copies in delivery and retention fallbacks.
- [x] Preserve all six deterministic claim/listing/read race regressions.
- [x] Compare valid legacy positive version numbers numerically.
- [x] Reuse existing files and add no persistent store or authenticity protocol.
