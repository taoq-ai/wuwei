Verdict: PASS
Gate: arch
Item: 1064
PR: taoq-ai/wuwei
Head: f7cf3ab6f8946b492a7f940371eaa63d7a18e245
Confidence: high
Breaking: no

## Findings
- [medium] .claude/wuwei/cli/wuwei/:1 blocks: no. Nothing checks that the committed copy matches the source. In this repository cli/, charters/ and agents/ change in most PRs, and each change leaves the copy stale until someone reruns `init --cloud`. Until then cloud sessions enforce the older guards, so a guard fix merged to main is not enforced in the cloud. The commit message records "refresh it with init --cloud after each release" as the policy. Put that under `Assumptions:` in the PR body. A test comparing .claude/wuwei with the source tree, or a release step, would turn drift into a visible failure.
- [low] .claude/wuwei/.claude-plugin/plugin.json:3 blocks: no. The copy says version 1.1.0, but origin/main is already at 1.2.0 (041b83d, which bumps only the version). guards.py:173 and the workspace.init record read this version, so cloud sessions will report 1.1.0. Rebasing and rerunning `init --cloud` fixes it.
- [low] .claude/settings.json:3 blocks: no. Nothing was committed to this repository's project settings before. Now every session here gets the standard init permissions: allow Bash(git:*) and Bash(gh:*), deny force push, --admin and ledger writes. This is the product's documented output and is not new to WUWEI, but it is the first time this repository has it.
- [low] .claude/wuwei/cli/wuwei/guards.py:1 blocks: no. This is an existing property of `--cloud`, not something this diff creates: the hooks run from the working tree, so a session that edits .claude/wuwei/ or .claude/settings.json changes the guards that police it, and no door covers those paths. This matters more in this repository, where agents edit WUWEI's code all the time. Candidate for a later item.

## Probes
- `git diff --stat origin/main...f7cf3ab`: 51 files, all under .claude/, plus 3 lines in AGENTS.md. No runtime source under cli/ changed.
- `cmp` of every tracked file under .claude/wuwei, .claude/agents and .claude/skills against the source at the head: identical except .claude/wuwei/.gitignore (vendor-only, `__pycache__/`).
- .claude/settings.json hooks: all five events (SessionStart, PreToolUse, PostToolUse, SubagentStop, Stop) point at `"$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei hook <event>`. This matches setup.py:66 and the test at tests/test_setup.py:107.
- Acceptance 2 (hooks run once where the plugin is installed): hook.py:377 sets VENDORED, and main() returns 0 unless CLAUDE_CODE_REMOTE=true (sync.py:20). tests/test_setup.py:112-116 covers this.
- I ran `python3 -m pytest -q` in a scratch copy made with git archive of the head: 264 passed.
- I tried to call the vendored hook by hand. WUWEI's PreToolUse door refused it ("a hand-made call would forge the record"), so I did not retry. Running it live is left to the goal gate.
- Breaking: no published contract changed. The CLI, its flags and its output are untouched. The files only add project-level config.
- Confidence is high because the diff is only generated output that byte-compares with the source, and the full suite passes.

## Residual risk
Cloud sessions run whatever copy was last committed. Until a check catches drift, the self-hosted guards can lag behind main without anyone noticing.
