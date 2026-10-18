# Concepts

Every idea in WUWEI earns its place by preventing a mistake or saving your attention. This map
says what each one is, why it is there, and where it lives.

| Concept | Why it is there | Where it lives |
| --- | --- | --- |
| [Auditor, not a gate](philosophy.md) | Process the model cannot see the point of gets routed around; evidence cannot be | the whole design |
| [Plan passes and checkpoints](the-day.md) | Days change; a plan you can redo any time stays true | `/wuwei-run`, `/wuwei-close`, `.wuwei/plan.json` |
| [WSJF and RICE ranking](the-day.md#ranking) | The most valuable work first, with evidence for every score | `wuwei plan add` |
| [The team and its charters](team.md) | Independent roles catch what one agent misses | `charters/`, `agents/` |
| [Models and effort](models.md) | Each seat runs on the model and effort its work needs, from one table you can override | `charters/planner.md`, the Agent call |
| [The evidence contract](evidence.md) | "Done" means something checkable, the same for every PR | `wuwei status`, `wuwei evidence` |
| [Attested verdicts](evidence.md#attested-verdicts) | A review counts only if a reviewer wrote it and nobody edited it | SubagentStop, the ledger |
| [Breaking changes](evidence.md#breaking-changes) | Clients you break should hear it from you first, and you decide whether it ships | `Announcement:`, the `breaking:` question |
| [The doors](doors.md) | Some mistakes cannot be taken back | PreToolUse, harness rules, the code host |
| [Enforcement levels](doors.md#how-strongly-a-door-holds) | Honesty about what is prevented and what is only detected | `wuwei doctor` |
| [Reversibility and confidence](decisions.md) | Ask only when a mistake would be costly and you are unsure | `_common.md` |
| [Owner question classes](decisions.md#asking-the-owner) | Your attention is the scarcest resource | the owner-question door |
| [Exceptions that expire](decisions.md#exceptions) | Accepting a gap is a debt, not a pardon | rulings, follow-up items |
| [ADRs from one-way answers](decisions.md#adrs) | Why a hard decision was taken outlives the session | `docs/adr/` in each repo |
| [Hooks as the sensei](hooks.md) | Guidance at the moment beats rules nobody reads | `hooks/hooks.json` |
| [Harness permissions](permissions.md) | One place for who may call which tool | `.claude/settings.json` |
| [Andon](doors.md#andon) | Stop one broken stream, not the whole team | `wuwei andon` |
| [The learning loop](learning.md) | Mistakes become standards; useless rules go | steward, `.wuwei/standards.md` |
| [Error budget](learning.md#error-budget) | Autonomy is earned by results and lost by escapes | evidence tiers |
| [Calibration and gate yield](learning.md#calibration-and-yield) | Know which reviews pay and which reviewers are overconfident | the report |
| [Skills and memory proposals](learning.md#skills-and-memory) | Stop re-learning the same repository facts | retro proposals |
| [Report, telemetry, DORA](metrics.md) | See what happened without asking | `wuwei report` |
| [The ledger](metrics.md#the-ledger) | A tamper-evident record of what was decided | `.wuwei/ledger/` |
| [Replay cases](metrics.md#replay-cases) | The auditor itself is held to its past answers | `tests/replay/` |
| [Many repositories](many-repositories.md) | One process, the shape of each repository | one workspace |
| [Running on Codex](codex.md) | One process whichever agent does the work | `wuwei init --codex`, `.codex/` |
| [Cloud sessions](cloud.md) | A fresh clone starts where the last session stopped | `wuwei init --cloud`, `wuwei sync`, the `wuwei/state` branch |
| [Work in progress](watch.md) | Nothing waits on your nudge: PRs and replies keep moving | `/wuwei-watch`, `wuwei owe` |
