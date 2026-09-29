# Feature 104: Signed integrity manifest and workspace integrity

## User Scenarios & Testing

### US1 (P1): Detect installed plugin tampering
An owner needs every shipped file checked against an authenticated release inventory.
- Given one byte changed in an installed charter, integrity check exits 1 naming
  that file and all PreToolUse hooks in the workspace deny with exit 2.
- Given a manifest signed by another key, check exits 1.
- Given ssh-keygen is absent, check exits 2 with an unmeasured reason.
- Given an unsigned installation, check reports a page, never clean.
- Given a failed check, guards use the cached verdict until a clean reinstall or
  explicit owner re-confirmation on the host. Further changes invalidate confirmation.
- Outside a WUWEI workspace hooks return 0. SessionStart always returns 0 with context.

### US2 (P1): Detect unapproved workspace changes
- Given a hand edit to .wuwei/charters/builder.md, SessionStart reports a page.
- Uncommitted or trailer-less changes to memory and goals report a nudge;
  charter overrides and voice report a page, including deletions and renames.
- Init establishes workspace history. Every landed promotion records its changes
  with a Promoted-by: wuwei trailer, without absorbing unrelated edits.

### US3 (P2): Authenticate releases
CI inventories every packaged file and signs the inventory using the repository
signing secret. The pinned public key is shipped and copied during init.

## Requirements
- FR1: Verify signatures and file contents at SessionStart and every sweep.
- FR2: Cache verdicts for PreToolUse, without hashing the plugin there.
- FR3: Missing tools, unreadable input and adapter failures are unmeasured (exit 2).
- FR4: Protect verdict, confirmation and pinned-key files from ordinary state/event
  commands and agent Write/Bash operations. No seat-accessible approval flag.
- FR5: External processes run only through closed adapter operations.
- FR6: Document owner signing setup and the same-uid residual from design 9.1.

## Key Entities
Release inventory and signature; pinned public key; workspace integrity verdict;
owner confirmation tied to measured content; workspace promotion history.

## Success Criteria
All four issue acceptance scenarios pass offline; PreToolUse p95 remains below
50 ms for the cached integrity check; full regression suite passes.

## Assumptions
- MANIFEST.sha256 and its detached signature exclude themselves from the inventory.
  Generated Python bytecode and git metadata are not shipped content.
- A source checkout is unsigned and reports a page until explicitly confirmed on
  the host; no development-mode bypass is inferred from .git.
- Re-confirmation requires a host terminal and is denied through agent tools.
  Same-uid processes can forge files or the terminal; this is tamper evidence,
  not proof of owner identity, as specified in 9.1.
- Workspace history examines all protected-path commits so later promotion cannot
  hide an earlier trailer-less edit. Owner review is required to repair history.

## Deferred
Owner provisions the real pinned public key and CI signing secret. Strong owner
identity requires a separate OS principal or the future external control plane.
Dependencies #81, #15, #31 and #114 are reused from the current checkout.
