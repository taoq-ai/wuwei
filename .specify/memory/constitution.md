# WUWEI Constitution

Source of truth for what gets built: `docs/specs/2026-09-24-wuwei-design.md`. This
constitution governs how it gets built. Where they conflict, the design spec wins and the
conflict is raised, not resolved silently.

## Core Principles

### I. Stdlib only at runtime

Everything under `cli/` and `adapters/` imports only the Python standard library (3.11+).
pytest is a development dependency only. External tools (`git`, `gh`, `ziran`, `claude`,
`codex`, `signal-cli`) are reached as subprocesses behind an adapter, never imported.

### II. Three-state exits, fail closed

Every guard, sweep and adapter call returns `0` clean, `1` findings, `2` could not run.
Exit 2 blocks exactly like exit 1 and prints why. An error inside a guard is exit 2. An
absent adapter or scanner reports "unmeasured" and is never counted as clean. A read that
returns an error body is never parsed as data.

### III. One behaviour, one function, one test

The CLI is the only writer of workspace state and the only home of guards, sweeps, index
and metrics. A behaviour lives in exactly one CLI function with one test. Hooks, skills and
seats call it; none reimplement it. State writes are atomic (temp file then rename);
`events.jsonl` is append-only.

### IV. Test first (NON-NEGOTIABLE)

Red, green, refactor. Write the failing test, watch it fail for the right reason, then write
the minimum code that makes it pass. Guards get table tests for exits 0, 1 and 2. Hooks are
tested by piping recorded Claude Code payloads through the shim. Tests assert on exit codes,
events and files, never on model prose.

### V. Simplicity (ponytail)

The laziest solution that actually works. YAGNI: build only what the issue and spec ask
for. Reuse what already exists in the repository before writing anything new; stdlib before
custom code; one line before fifty. No interface with one implementation, no factory for one
product, no config for a value that never changes. Deliberate shortcuts with a known ceiling
carry a `ponytail:` comment naming the ceiling and the upgrade path. Never simplify away
validation at trust boundaries, error handling that prevents data loss, or security.

### VI. SOLID where it is convenient

Apply SOLID where it keeps the code smaller or the tests simpler: single responsibility per
module, adapters as the one place where substitution (Liskov) and interface segregation
matter, dependencies passed in so tests can replace them. Do not add an abstraction only to
satisfy a principle; Principle V wins a tie.

### VII. Security first

Least privilege for agent tools. Guards refuse at the moment of action. Secrets, phone
numbers and message bodies never land in traces, logs or memory unredacted. A merge happens
only through the merge policy, never by approval or override; nothing ever deploys (design
spec 4.6 and 4.7).

## Constraints

- Writing style for everything the plugin authors (code comments, docs, charters, CLI
  output): no emojis, no em-dashes.
- No hosted service or database in the plugin. The only long-running processes are the
  watch (v1) and the listener (M5). The project's optional telemetry collector (design
  5.13) runs outside the plugin, and the plugin works without it.
- Telemetry adds no record and no step to a hook: its signals are fields on records the
  CLI already appends, and aggregation runs only in CLI commands. What it derives is a proposal the
  owner applies, never applied on its own (design 5.13).
- Conventional commits; release-please drives versions.

## Workflow

- One GitHub issue is one spec-kit feature: `specs/<issue number, 3 digits>-<slug>/` with
  `spec.md`, `plan.md` and `tasks.md`, created with `--number <issue>`.
- Specification mode (design 5.10; amended 2026-10-03, #411): WUWEI itself runs under
  `engine = "speckit"` and `mode = "strict"`. Every feature runs `specify`, `clarify`,
  `plan`, `tasks`, `analyze`, `checklist` and `implement`, in that order, then the full
  suite and the review; none is optional. The `analyze` report is saved as `analysis.md` in
  the feature directory, and a CRITICAL or HIGH finding is resolved before `implement`. A
  trivial change skips the spec only as 5.10 allows (a light lead tier, or the owner's skip
  with a recorded reason), and its pull request says why.
- One feature is one branch in its own git worktree, merged to `main` after the tests pass
  and an adversarial review (correctness, security, and a ponytail over-engineering pass)
  has no open blocking findings.
- Cycle budget per feature: one fix round plus one delta review. A feature that exceeds it
  gets no further fix rounds; the next step is a design reconsideration recorded in its
  spec (why the approach keeps leaking, what replaces it), agreed with the owner before
  more code (example: #222, six rounds on shell parsing for owner actions).

## Governance

Amendments are commits to this file with a dated line in the commit message. The design spec
is amended only by its owner.

**Version**: 1.2.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-03
