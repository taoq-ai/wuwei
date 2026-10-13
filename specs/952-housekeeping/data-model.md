# Data Model
process.started: pid, observed command, OS start identity, purpose (pr-wait or
sleep), started_at, session_id (None outside a session), day. No PR snapshot or native exec identity.
process.reaped: matching record, reason and source_day. A signalled zombie is explicitly
reported as signalled, awaiting parent reaping, rather than claiming nothing was sent.
process.cleanup_failed: matching identity and reason, recorded once after failed cleanup.
Matching live failures are listed without scheduling another automatic cleanup duty.
Findings: kind, why, command, optional day and item. External cleanup is a plain listing.
process.orphan_listed: PID and start identity, in the current day. General
workspace orphans are listed once per identity per day; no ownership is conferred.
Legacy item fields remain readable for old timer records.
Current failed reaps carry a transient reap_failed finding flag so close distinguishes them from historical receipts and unmeasured inspection.
All persistent records use the existing event writer. No state schema migration.
