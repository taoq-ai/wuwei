# Requirements Checklist: PR Auto Claim

- [x] Successful item worktree and head branch cases are defined.
- [x] Unmatched, failed, and hook error cases are defined.
- [x] No network call and fail-open behavior are explicit.
- [x] Owner-only design conflict is recorded as an assumption.
- [x] The original pretool refusal and gate checks protect recorded items.
- [x] Only configured, open PRs are offered after stuck-seat recovery.
- [x] Ambiguous output, dry runs, refused claims, and timeouts have defined outcomes.
- [x] Worktree matches retain the local branch; tracker review duty is deferred explicitly.
- [x] Matched unsafe PRs retain their item in the offered claim command.
- [x] Pending PR listings respect event freshness, the poll interval and cleared rows.
