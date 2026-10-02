# Research: claims re-checked for the new table (2026-10-02)

Every cell for another tool changes wording, so each was re-checked against the tool's own
docs on 2026-10-02. The descriptions from #258 (`specs/258-readme-comparison/research.md`)
still hold. The PR body lists these URLs. "Not described" means the checked page names no
step for that question; the table then names what the user does and does not claim the tool
lacks it.

| Tool | URL checked | Plans | Reviews | Merge | Learned afterwards | Runs in |
|---|---|---|---|---|---|---|
| Spec Kit | https://github.com/github/spec-kit | Specify, plan and tasks per feature, after a constitution once per project | Converge adds "clarification, checklists, and consistency analysis" as extra quality gates | Not described | Constitution set once per project; not described as updated by later work | "a supported AI coding agent"; integrations for several agents |
| OpenSpec | https://github.com/Fission-AI/OpenSpec | You run explore and propose; the AI writes specs, design and tasks | `/opsx:verify` in the expanded workflow | Not described | Archive moves the change and "Specs updated" | "30+ tools and growing" |
| superpowers | https://github.com/obra/superpowers | Brainstorming, then writing-plans breaks work into 2 to 5 minute tasks | Subagent-driven development: "two-stage review (spec compliance, then code quality)" | Finishing a branch "Verifies tests, presents options (merge/PR/keep/discard)" | Not described | Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI, OpenCode and others |
| BMAD Method | https://github.com/bmad-code-org/BMAD-METHOD and https://docs.bmad-method.org/reference/skills-and-agents/ | Analyst, product manager, architect, developer and UX designer agents; brief, PRD, architecture | `bmad-code-review`: "several independent reviewers, then triage" | Not described | `bmad-retrospective` reviews a completed epic against its evidence; "Learn and adjust loops back to Plan" | AI coding tools that support skills; Claude Code and Codex plugins |
| Kiro | https://kiro.dev/docs/specs/, https://kiro.dev/docs/hooks/, https://kiro.dev/docs/steering/ | Specs: requirements (or bugfix), design and tasks | Not described | Hooks; a PreToolUse hook can block tool execution (#258, unchanged) | Steering files the user writes in `.kiro/steering/` | IDE, CLI and web |
| Claude Code | https://code.claude.com/docs/en/overview, https://code.claude.com/docs/en/hooks | Plan mode proposes a plan before edits | Subagents; "automatic code review on every PR" through GitHub Code Review | Hooks run before actions; a PreToolUse hook can deny a tool call (#258, unchanged) | `CLAUDE.md` and auto memory | Terminal, IDE, desktop app and web |

## WUWEI cells (in-repo sources)

- Plans: the planner runs `wuwei rank` and proposes the day; the owner approves at the
  morning gate (`docs/site/daily.md:65`).
- Reviews: sentinel gates, one or three by tier, then one fix round (`docs/site/concepts.md`,
  Review tiers). Gates are sentinels, never the builder that wrote the change.
- Merge: shipped hooks refuse at the moment of action; a merge happens only through the
  merge policy (constitution VII, `repos.merge.*` in `docs/site/configuration.md:44`) and
  the code host's protected refs.
- Learned: the daily retro; seats propose charter and note changes and `wuwei promote`
  lands them (design 6.8, `docs/site/daily.md`).
- Runs: Claude Code, across the configured repositories, through `gh`.
- Hook cost: 40 to 50 ms CPU p95 on M-series class hardware, about 100 ms on 2-CPU runners
  (`docs/site/reference.md:293-305`).
