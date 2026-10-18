# Feature Specification: the wide-change trigger counts code and spec lines, never prose, and a spec contract takes arch

**Feature branch**: `fix/wide-specs`
**Item**: wide-specs, tier full, goal G-2
**Input**: bug #1131. taoq-ai/taoqi#124 changed only `specs/**` (about 1,780 lines, tier standard).
The planner briefed "docs need no gate"; `wuwei evidence` asked for arch, because `needed()`
counted every file's lines, prose included, for the wide trigger. The rule and the code disagreed.

## The promise in my words

The issue's second option, made true in both the code and the rules:

1. In `evidence.needed`, the wide trigger (over 200 changed lines) counts every line but prose.
   Prose is what the CI-not-started rule already calls prose (`PROSE`, docs/design.md "CI not
   started"), outside `specs/` and `openspec/`: a `.md`, `.rst` or `.adoc` file other than the
   files seats load, or a path that is exactly `LICENSE` or `NOTICE`. Code files, spec files,
   `.txt` files, code under a `docs/` folder and the files seats load count (fix rounds at a7654a8
   and 4b535bd). So a prose-only diff needs no gate at any size, and a large spec diff at standard
   takes arch.
2. A change under `specs/**/contracts/` or `openspec/**/contracts/` takes arch at any tier, as a
   contract file (an OpenAPI or Swagger file, `.proto`, `.graphql`, `.schema.json`) does. The
   contract check reads every file in the diff, so a contract file under `docs/` takes arch too.
3. `charters/_common.md` says so: a wide change is over 200 lines that are not prose, or 10
   code files; a spec contract takes arch at any tier. `docs/design.md` line 77 and the site's evidence
   page match, `tests/test_charters.py` reads the new threshold text, and the agents are rebuilt.

The quality and security triggers do not change, nor does the 10 code files count.

The acceptance scenarios, restated:

1. A standard item with 1,780 lines under `specs/` only: `needed` returns `('arch',)`.
2. A standard item with 300 lines of `README.md` and `docs/site/*.md` only: `needed` returns `()`.
3. A light item adding `specs/001-x/contracts/api.yaml`: arch is in the result.
4. At the head, `bin/wuwei agents build` leaves git status clean and `tests/test_charters.py`
   passes with the new threshold text.

## How this fails

1. A spec contract is missed, so an outward contract change merges without arch. Ways in: a
   contract folder directly under `specs/` (`specs/contracts/api.yaml`), an OpenSpec change
   (`openspec/changes/x/specs/contracts/events.md`), a `.md` contract (prose by its extension), or
   the full tier with no code (where the early return for code does not fire). The pattern is
   anchored at `specs/` or `openspec/` and allows zero or more folders before `contracts/`; each
   of these has a test.
2. A false hold: prose or a near-miss path is read as a spec contract or as wide, so a docs PR
   waits for arch. Ways in: `docs/contracts/api.md`, `specs/contracts.md`, a 200-line spec (the
   bound is over 200), 150 code lines plus 600 lines of README and LICENSE. Each has a test that
   expects no arch.
3. The delta rule moves the wrong way after review fixes. `gate_gaps` runs `needed` on the delta,
   so the same counting applies there: a 300-line README delta now carries the passes (on main it
   asked arch to re-read), a 200-line spec delta carries them, a 201-line spec delta and a 2-line
   spec contract delta are re-read by arch. The delta test pins all four through the REST compare
   shape.
4. Code read as prose, so it owes no gate (security and arch at a7654a8). The first build counted
   only what `needed` calls code, which drops every path under a `docs/` folder and every path
   that starts with `LICENSE` or `NOTICE`: a 300-line `docs/conf.py`, `src/docs/handler.py` or
   `NOTICE_handler.py` lost arch, and `docs/openapi.yaml` lost the contract check. The fix reads
   prose by the repository's one prose test (`PROSE`); each of those paths has a
   test that expects arch.

## Clarifications

### Session 2026-10-18

- Q: Which files count as spec files? A: The paths `needed` already leaves out of code as specs:
  those starting with `specs/` or `openspec/`, the same prefixes `gaps`, `PROSE` and `SPEC_RULES`
  use. A spec folder nested deeper (`packages/x/specs/`) is not a spec anywhere in WUWEI today and
  stays prose or code by its extension.
- Q: Does a code file count twice when it sits under `specs/` (a risky `.txt` such as
  `specs/requirements.txt`)? A: No. The counted set is one list filtered once, so each file counts
  once.
- Q: Does a contract file pattern (OpenAPI, `.proto`) inside `specs/` now take arch? A: Yes. The
  contract pattern runs over every file in the diff (since the fix round at a7654a8). Such a file is a contract by the
  existing rule; on main it slipped past only because spec paths were not code. Recorded under
  Assumptions.
- Q: Does the wide trigger fire at full or light? A: As before, only at standard; light stays the
  ceiling, and full takes all four once there is code. A full item whose diff is specs only takes
  arch only for a spec contract. Unchanged by this item.
- Q: Are generated files under `specs/` counted? A: No. `lines()` already drops generated paths
  (lockfiles, `dist/`, `vendor/`, snapshots), wherever they sit.

### Fix round at a7654a8

- Q: What is prose for the wide trigger? A: The planner's ruling: a `.md`, `.rst`, `.adoc` or
  `.txt` file outside `specs/` and `openspec/`, or a path that is exactly `LICENSE` or `NOTICE`.
  Everything else counts, so `docs/conf.py`, `src/docs/x.py`, `LICENSES/x.py` and
  `NOTICE_handler.py` count. A risky `.txt` (`docs/requirements.txt`) is code and counts.
- Q: Does this change what is code for the quality gate or the test rule? A: No. `code` and the
  no-test rule in `gaps` keep their split; code under `docs/` taking no quality gate is a
  follow-up the planner files.
- Q: Which files does the contract check read? A: Every file in the diff, so a contract file under
  `docs/` (`docs/openapi.yaml`) takes arch at any tier, as the rule "a contract file takes arch at
  any tier" says.
- Q: Are the files seats load (`AGENTS.md`, `CLAUDE.md`, `charters/*.md`, `agents/*.md`,
  `skills/*/SKILL.md`) prose? A: Yes, by the promise's definition (`.md` outside the spec
  folders). Over 200 lines at standard they took arch on main and take no gate at the head.
  Recorded under Assumptions.

### Fix round at 4b535bd

- Q: Is a `.txt` prose? A: No. The planner's ruling: keep one prose definition, the `PROSE` regex
  the CI-not-started rule uses, which leaves `.txt` out. A 300-line `requirements/prod.txt`,
  `constraints.txt` or `CMakeLists.txt` takes arch at standard, as on main.
- Q: Are the files seats load prose? A: No, by the same regex: `AGENTS.md`, `CLAUDE.md`,
  `charters/*.md`, `agents/*.md` and `skills/*/SKILL.md` count, so over 200 lines at standard
  they take arch, as on main. This replaces the answer of the round at a7654a8.
- Q: Does `PROSE` cover `openspec/`? A: Its pattern `(open)?specs/` matches `openspecs/`, not
  `openspec/`, so `openspec/` files are not prose to it; `needed` counts both spec prefixes by
  name, so the wide trigger is right either way. The CI-not-started side is a candidate item.
- Q: Does `code` change? A: One line, the arch gate's call: `DOCS` anchors `LICENSE` and `NOTICE`
  (`^(LICENSE|NOTICE)$`), so a root path that only starts with them (`NOTICE_handler.py`,
  `LICENSES/x.py`, `LICENSE-MIT`) is code: quality at light and standard, all four at full, and
  the test rule. `COPYING` was already code on main.

## Assumptions

- The owner prefers arch on large spec diffs and on spec contracts (the issue says the second
  option "seems more useful"; the plan item takes it). Overturned if the owner picks "count code
  lines only", a one-line change in `needed`.
- A contract file (OpenAPI, Swagger, `.proto`, `.graphql`, `.schema.json`) under `specs/` takes
  arch at any tier, as it would anywhere else. Overturned if the owner wants only the
  `contracts/` folder to count inside specs.
- Code under `docs/` still takes no quality gate and no test at any size (unchanged from main);
  the planner files it as a follow-up.
- "Spec contract" is a new term; a grep of charters, docs, skills and cli at the base found no
  other meaning for it.

## Breaking

The arch gate found this breaking at a7654a8, which overturns the first build's "not breaking".
`wuwei evidence`, the create and ready doors and the merge now ask for gates on PRs that read
mergeable on main. The commit and PR title take a `!` and a `BREAKING CHANGE:` line.

- Newly held until arch passes, at any tier: a diff that touches a file under
  `specs/**/contracts/` or `openspec/**/contracts/` (spec-kit's plan step writes
  `specs/<feature>/contracts/` for most features), a contract file (OpenAPI, Swagger, `.proto`,
  `.graphql`, `.schema.json`) under `specs/`, `openspec/` or a `docs/` folder, and a delta after
  review that touches a spec contract, even 2 lines.
- Newly held at standard: a spec-only delta after review over 200 lines is re-read by arch.
- Newly held at every tier: a root path that starts with `LICENSE` or `NOTICE` but is not exactly
  that name (`LICENSE-MIT`, `LICENSES/`, `NOTICE_handler.py`) is code: quality at light and
  standard, all four at full, and a test or a `No test:` line.
- Newly passing at standard: prose over 200 lines (`.md`, `.rst` and `.adoc` files such as README
  and docs pages, `LICENSE`, `NOTICE`) no longer takes arch. `.txt` files and the `.md` files
  seats load still take it, as on main.
- Migration: plan an arch gate for any PR that changes a spec contract or a contract file, at any
  tier; prose-only PRs need no gate; add a test or a `No test:` line to a PR that edits a file
  such as `LICENSE-MIT`. No config or data changes.

## Rollback

Revert the merge commit. `needed` then counts every file's lines again and spec contracts stop
calling arch; no state, config or ledger format changes.

## User scenarios

### US1: the wide trigger counts code and specs, never prose (P1)

Acceptance 1 and 2. Tests in tests/test_evidence.py.

### US2: a spec contract takes arch at any tier (P1)

Acceptance 3. Tests in tests/test_evidence.py.

### US3: the rules say what the code does (P1)

Acceptance 4. Test in tests/test_charters.py.

## Requirements

- FR-001: `needed` counts every line but prose for the wide trigger (prose: `PROSE`, outside the
  spec folders).
- FR-002: `CONTRACT` matches `specs/**/contracts/` and `openspec/**/contracts/`, and `needed` runs it
  over every file at any tier.
- FR-003: The delta rule in `gate_gaps` follows FR-001 and FR-002 with no change of its own.
- FR-004: charters/_common.md, docs/design.md and docs/site/concepts/evidence.md state the rule;
  agents rebuilt; `.claude/` re-vendored; runtime at most 3,000 lines (2,976 to 2,978).

## Success criteria

- SC-001: Every acceptance scenario has a test that passes at the head. Scenarios 2 to 4 ran red
  on main; scenario 1 already held on main (it counted every line) and is pinned so the new count
  keeps it.
- SC-002: The full suite passes.
