# Research: what each tool says about itself (checked 2026-09-30)

Each line is what the tool's own README or docs said on the date checked. The builder
re-checks each URL when writing and drops any claim that no longer holds. The PR body lists
these URLs.

| Tool | URL checked | What it says (paraphrased, short quotes marked) |
|---|---|---|
| Spec Kit | https://github.com/github/spec-kit | Open source toolkit giving coding agents structured processes and templates. Spec-driven flow: "Constitution once per project; specify → plan → tasks → implement → converge per feature" (arrow is theirs, write "then" in the README). Installed with `uv tool install specify-cli`, then `specify init <project> --integration <agent>`; several agents through integration keys. Extensions, presets, workflows and bundles. Artifacts are Markdown under `.specify/` and the feature spec folders. |
| OpenSpec | https://github.com/Fission-AI/OpenSpec | "Spec-driven development (SDD) for AI coding assistants". Flow: explore, propose (a change folder with proposal, specs, design, tasks), apply, archive. Specs show `## ADDED Requirements`; archive moves the change to `openspec/changes/archive/` and updates the specs. Works with "30+ tools". npm install. Artifacts under `openspec/specs` and `openspec/changes`. |
| superpowers | https://github.com/obra/superpowers | A development methodology built on composable skills plus instructions that make the agent use them. Skills include brainstorming, writing plans, test-driven development, systematic debugging, verification before completion, using git worktrees, subagent-driven development. Supports Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI, OpenCode and others. A session-start hook activates it; the agent checks for relevant skills before any task; the README calls them "Mandatory workflows, not suggestions". |
| BMAD Method | https://github.com/bmad-code-org/BMAD-METHOD and https://docs.bmad-method.org/reference/skills-and-agents/ | "Agile AI Driven Development". Loop of Clarify, Plan, Build and verify, Learn and adjust, sized to the work. Agents: Analyst, Product Manager, Architect, Developer, UX Designer. Documents: product brief, PRD, UX design, architecture, epics and stories. Installed with `npx skills add bmad-code-org/BMAD-METHOD` or as a Claude Code or Codex plugin. |
| Kiro | https://kiro.dev, https://kiro.dev/docs/specs/, https://kiro.dev/docs/hooks/ | Agentic AI with an IDE, CLI, web interface and mobile app, built and operated by AWS. A spec is `requirements.md` (or `bugfix.md`), `design.md` and `tasks.md`. Hooks run shell commands or agent prompts on events (file save, create, delete, PreToolUse, PostToolUse, Stop); a PreToolUse hook can block tool execution unless preconditions are met. Steering files carry across surfaces. |
| Claude Code | https://code.claude.com/docs/en/common-workflows, https://code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/sub-agents, https://code.claude.com/docs/en/memory | Plan mode: Claude reads files and proposes a plan, no edits until approved. Subagents work in their own context window with their own tools and prompts. Hooks run shell commands before or after actions; a PreToolUse hook can deny a tool call with `permissionDecision: "deny"` and a reason shown to Claude, or exit 2. Memory: `CLAUDE.md` read at session start, and auto memory Claude writes as it works. |

## WUWEI facts the section may cite (in-repo sources)

- Roles: planner, lead, builder, shepherd, steward, four sentinels (`docs/site/concepts.md`).
- Guards: hooks call the CLI and refuse at the moment of action with a reason; cooperative
  mistake prevention, not an isolation boundary (design 9.1, `docs/site/security.md`).
- State: the CLI is the only writer of workspace state and events (constitution III).
- Retro to charter: seats propose, `wuwei promote` lands charter and note changes, ledger
  (design 6.8, `docs/site/daily.md`).
- Security: signed release manifest and integrity check (`docs/integrity.md`), ZIRAN audit
  of role tool grants in CI (`docs/site/security.md`).
- Integrations: `gh` for the code host; tracker and chat are optional adapters
  (`docs/site/adapters.md`). Codex is an optional seat runtime.
- Hook cost: 40 to 50 ms CPU p95 on M-series class hardware, about 100 ms on 2-CPU CI
  runners (`docs/site/reference.md`, "Hook latency budget").
- Proof: the live rehearsal is required before a release (`docs/site/rehearsal.md`,
  design section 10).
