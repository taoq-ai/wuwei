# Release and workspace integrity

Integrity is a warning at SessionStart and a row in `bin/wuwei doctor`. It never refuses a tool call.

## The plugin

Install the `wuwei.tar.gz` asset from a release by extracting it into the plugin directory. The archive carries `MANIFEST.sha256` and its SSH signature. The manifest lists every packaged file except itself and its signature. Git source archives are unsigned and read as a finding.

A development checkout has no signature. It is confirmed at a clean commit with `bin/wuwei doctor --fix --apply integrity-reconfirm`, and stays confirmed until HEAD or the tracked tree changes. Ignored build artifacts do not count.

Claude Code writes one marker per running process into `.in_use/` at the install root, named by its process id. Markers come and go, so they are not measured. Anything else there, a symlinked `.in_use` or a deeper one is still a finding.

## When it is measured

- SessionStart measures the plugin and the workspace history, and prints any finding as a warning in the session context.
- `bin/wuwei doctor` shows the `integrity` row from the cached verdict. A release file changed after that verdict is a finding. The row names its fix: reinstall the signed release, or reconfirm.
- `bin/wuwei init` and `init --upgrade` end by measuring and print `plugin integrity: clean` or the finding.

`init` copies the plugin public key into `.wuwei/integrity/pinned.pub` and starts `.wuwei/` history in git. Agent tools cannot write the integrity directory or the workspace git metadata.

## Workspace history

Charters, memory and goals are checked for uncommitted changes and for commits without a `Promoted-by: wuwei` trailer. Each one is a warning at SessionStart. `bin/wuwei retro --promote` commits each landed proposal with that trailer, and the gate's Yes commits goals the same way. A target with an earlier hand edit is rejected, so promotion cannot bless it.

## Recovering

Reinstall the signed release and run `bin/wuwei doctor`. For a development checkout or a change you reviewed, run `bin/wuwei doctor --fix --apply integrity-reconfirm` ([integrity reconfirm](recovery.md#integrity-reconfirm)). It asks its Owner step card in the session. The confirmation is tied to the measured fingerprint, and a later change voids it.

These records are local tamper evidence, not proof of identity. A process running as your user can alter the verifier or forge records. A hard boundary needs a separate OS user or an external supervisor.

## Release signing setup

1. Generate an SSH signing key outside the repository and keep the private key out of it.
2. Put the public key in `keys/manifest-signing-key.pub` before releasing.
3. Store the private key as the Actions secret `WUWEI_MANIFEST_SIGNING_KEY`.
4. Release through release-please. CI builds the inventory, signs it with namespace `wuwei-manifest`, verifies it against the pinned key and attaches `wuwei.tar.gz`. A missing secret or a mismatched key fails the build.
5. Publish the key fingerprint through a channel you control. Changing the plugin pin does not replace existing workspace pins.
