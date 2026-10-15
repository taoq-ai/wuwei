# Harness permissions

Who may call which tool is decided in one place: Claude Code's own permission rules in
`.claude/settings.json`. WUWEI does not keep a second allow list.

`wuwei init` merges three sets of rules into the project settings and leaves your own untouched:

| Rules | Contents | Why |
| --- | --- | --- |
| allow | `git`, `gh`, reading, writing and searching files | everyday work should not prompt you |
| deny | force pushes, admin merges, repository deletion, edits to the ledger | the doors, held by the harness as well as the hook |
| ask | terraform, tofu, pulumi, kubectl and helm writes | infrastructure is your decision |

Deny rules and WUWEI's hook refusals take precedence over allow rules, so allowing broadly is safe:
the doors stay held.

## Allowing a tool

To let the team post to Slack or update Linear, allow the tool the way you always would: answer
"Yes, don't ask again" on the prompt, or add `mcp__slack` (a whole server) or
`mcp__linear__save_issue` (one tool) to `permissions.allow`. WUWEI still scans every outward call
for secrets and the workspace canary, whatever the rules allow.

## Fewer prompts

If you still see prompts you always approve, Claude Code's `/fewer-permission-prompts` skill reads
your transcripts and proposes allow rules for them.

**Why:** a permission system you maintain twice drifts, and a plugin that re-asks what the harness
already allows is friction for nothing.
