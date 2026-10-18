# WUWEI Constitution

What to build: `docs/design.md`. This file governs how it is built. Where they conflict, the design
wins and the conflict is raised.

## Principles

### I. Stdlib only at runtime

Everything under `cli/` imports only the Python standard library (3.11+). pytest is dev-only.
External tools (git, gh, ssh-keygen) are reached as subprocesses for reading and signing, never
wrapped as WUWEI commands the model must use.

### II. Evidence over steps

WUWEI reads artifacts and says what is missing. No command tells the model which command to run
next. State that git or the code host already holds is never copied into WUWEI's records.

### III. An auditor, not a gate

The doors in design section 6 are the closed list of refusals; adding one is a design change.
Everything else passes and is recorded. A door that cannot read its evidence stays shut; every
other hook fails open and records why.

### IV. The owner decides only what matters

Only the decision classes in design section 8 reach the owner. A mechanical failure is never an
owner question. An instruction the owner gave is the approval.

### V. Test first (non-negotiable)

Write the failing test, watch it fail for the right reason, then the minimum code. Hooks are
tested through `hook.handle` with recorded payload shapes; the code host through a fake `gh.run`.
Tests assert on decisions, records and files, never on model prose.

### VI. Simplicity, with budgets

The laziest solution that works. Reuse before writing; stdlib before custom code; no interface
with one implementation. Budgets: runtime at most 3,400 lines (a test holds it), six config keys
(`repos`, `owner_paths`, `prioritisation`, `tracker`, `telemetry`, `models`). A change that breaks
a budget deletes something first. An item that adds more than 10 runtime lines names the lines it
removes where it can, and no item waits on a free-lines round. Never simplify away validation at
a trust boundary, data-loss safeguards or security.

### VII. Security first

Least privilege for agent tools (`agents/allowlist.json`, reviewed). Secrets never land in traces
or the ledger. The harness's permission rules decide tool access; WUWEI adds deny and ask rules,
never a parallel allow list.

## Constraints

- Writing style for everything the plugin authors: no emojis, no em dashes.
- No hosted service, database or long-running process.
- Conventional commits; release-please drives versions.

## Workflow

- One GitHub issue is one change. A feature runs the spec-kit steps in `.agents/skills/` and keeps
  its spec in `specs/<issue>-<slug>/`. A bug fix is a failing test and the fix.
- WUWEI audits itself: every PR names `WUWEI-Item: <issue>` and passes the gates its tier needs.
- Cycle budget: one fix round and one delta review. A change that needs more is a design
  reconsideration agreed with the owner before more code.

## Governance

Amendments are commits to this file with a dated line in the commit message. The design is
amended by its owner.

**Version**: 3.2.0 | **Ratified**: 2026-10-15 | **Last amended**: 2026-10-18 (runtime budget 3,400 lines, six config keys)
