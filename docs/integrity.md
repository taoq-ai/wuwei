# Release and workspace integrity

Install the `wuwei.tar.gz` asset from a release by extracting it into the plugin
installation directory. This archive includes `MANIFEST.sha256` and its SSH
signature. Git source archives are unsigned and report a page. A source checkout
is pinned by `wuwei integrity reconfirm` at a clean commit and passes until HEAD or
the tracked tree changes; ignored development artifacts do not affect its fingerprint.
The manifest inventories every packaged file except itself and its signature.
Git metadata and generated Python bytecode are not shipped or measured.

Run `bin/wuwei integrity check` from a WUWEI workspace. Exit 0 means the release
matches its signature and inventory, or its exact content was explicitly confirmed
on this host. Exit 1 names integrity findings; exit 2 means unmeasured, including a
missing ssh-keygen. Both block PreToolUse. Outside a workspace the hooks return 0.
SessionStart always exits 0 and reports pages or unmeasured results in its context.
SessionStart and every watch/obligations sweep refresh the protected cached verdict;
PreToolUse reads that verdict without walking the installed plugin.

`wuwei init` copies the plugin public key into `.wuwei/integrity/pinned.pub` and
initializes `.wuwei/` history through the VCS adapter. An existing workspace must
have the owner copy that key and initialize its history after reviewing current
content; automatic upgrade must not bless existing hand edits.

Charters, memory, goals and voice are inspected for uncommitted changes and all
commits without a `Promoted-by: wuwei` trailer. Charter overrides and voice produce
pages; other procedure changes produce nudges. `bin/wuwei promote` commits each
landed proposal and its ledger entry, excluding unrelated staged changes. Targets
with prior unpromoted edits are rejected so promotion cannot bless a hand edit. A commit
failure returns unmeasured and leaves landed content visible as an uncommitted change.

To recover, reinstall the signed release and run `bin/wuwei integrity check`.
Alternatively, after reviewing the exact installed contents on the host, the owner
can run `bin/wuwei integrity reconfirm` in a terminal and type the displayed digest.
There is no `--yes` switch. Agent tools refuse this action. The confirmation is tied
to the inventory, manifest, signature and workspace pin; later changes invalidate it.
Missing tools and unreadable measurements cannot be confirmed.

State/event commands cannot manufacture integrity verdicts or confirmations.
Write/Bash protection covers the integrity directory and workspace git metadata.
These records are local tamper evidence, not proof of owner identity. As described
in design 9.1, a same-uid process can alter the verifier, forge records, or create a
terminal. A separate OS principal or external control plane is needed for a hard
owner boundary. Cache freshness is bounded by sessions and sweeps.

## Deferred owner setup

1. Generate and retain an SSH signing key outside the repository. Do not commit the
   private key. Use an unencrypted CI-specific key and restrict secret access.
2. Put the SSH public key in `keys/manifest-signing-key.pub` before releasing. The current
   pin is ED25519 `SHA256:D1UTIXN6ywO+2Li0w/Ja0RDoTKcRTMNmHaO0aYan9UY`.
3. Store the private key as repository Actions secret `WUWEI_MANIFEST_SIGNING_KEY`.
4. Create a release through release-please. CI stages the shipped files, builds the
   inventory, signs with namespace `wuwei-manifest`, verifies against the pinned key,
   and attaches `wuwei.tar.gz`. A missing secret or mismatched key fails the build.
5. Distribute the public key fingerprint through an owner-controlled channel and
   initialize new workspaces from the verified release. Review key rotation on the
   host; changing the plugin pin alone does not replace workspace pins.

No real signing key or secret is included in this issue. Strong host identity is
left to the external control-plane work described in design 9.1.
