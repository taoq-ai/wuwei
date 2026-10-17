# Feature Specification: owner review reads only owner review rulings, and CI not started covers docs-only diffs, an unreadable Actions host and pull_request_target

**Feature branch**: `claude/merge-evidence`
**Item**: merge-evidence, tier full, goal G-2
**Input**: `evidence.owner_approved` counts any approved ledger ruling at the head, so an approved
`breaking:` or `exception:` answer clears the owner review hold on `owner_paths`. The CI not started
read (#1085) left three follow-ups from its gates: a docs-only PR waits on CI a path filter skips, an
unreadable Actions host shows a gap that does not say why, and a repository whose CI runs only on
`pull_request_target` reads as having no CI.

## The promise in my words

1. The owner review gap on `owner_paths` clears only on the owner's own review at the head: an
   approving GitHub review by the owner login, or a ledger ruling with no `kind` (what the hook
   records for an `owner review:` answer). An approved `breaking` or `exception` ruling at the head
   no longer counts. The exception path still drops a gap whose text its `gap` field names, as
   before; that is a separate reader (`excepted`).
2. A PR whose files are all docs or specs (the `DOCS` pattern, `specs/`, `openspec/`, the same
   reading the no-test gap uses) and whose rollup is empty gets no `CI not started` gap, and makes
   no Actions read. A rollup with any check still holds on running or failing CI.
3. When the Actions read fails (a `GhError` such as HTTP 403, or an odd reply shape), the gap still
   shows and reads `CI not started at <sha7> (Actions host unreadable: <error>)`.
4. A repository counts as having CI when it ran a `pull_request` workflow or, failing that, a
   `pull_request_target` workflow. The second read happens only when the first finds none; the
   answer is cached a day per repository as before.

The acceptance scenarios, restated:

1. Owned path `infra/main.tf`, approved `breaking` and `exception` rulings at the head, no owner
   review: `owner review needed` shows. Add an approved ruling with no kind at the head: it is gone.
2. Files `docs/site/x.md` and `specs/a/spec.md`, empty rollup, a repository with a `pull_request`
   run: no `CI not started`. Files with `cli/wuwei/x.py`: it shows.
3. `gh.run` raises `GhError('HTTP 403')` on the Actions read, empty rollup: `CI not started` shows,
   naming the unreadable Actions host and `HTTP 403`.
4. The repository's only runs are `pull_request_target` runs, empty rollup: `CI not started` shows.

## Clarifications

### Session 2026-10-17

- Q: Which rulings are owner review rulings? A: Those with no `kind`. `hook._answers` records an
  `owner review:` answer with no kind, a `breaking:` answer with `kind: breaking`, and an
  `exception:` answer with `kind: exception`. No other writer exists.
- Q: Does any other reader depend on breaking or exception rulings counting as owner review? A: No.
  `owner_approved` has one caller, `evidence.gaps`. `breaking_gaps` reads only `kind == breaking`,
  `excepted` and `report.day` read only `kind == exception`. None reads `owner_approved`.
- Q: Does a release-please PR (read as generated) skip the CI read? A: No. The docs-only test uses
  the file list before the generated exemption; the generated exemption still applies only to the
  no-test gap, as on main.
- Q: What does the real `pull_request_target` read return? A: One read-only call,
  `gh api 'repos/taoq-ai/wuwei/actions/runs?event=pull_request_target&per_page=1'`, answered
  `total_count: 0` and an empty `workflow_runs` list: the same shape `gh.workflow_paths` parses for
  `pull_request`.
- Q: (arch and security gates at fc27033) Does the CI read reuse the no-test reading? A: No.
  `DOCS` reads every `.txt`, any path under `docs/` and `LICENSE*` as docs, so a `requirements.txt`
  or `docs/exploit.py` diff skipped the gap. The CI read uses its own `PROSE` pattern: a `.md`,
  `.rst` or `.adoc` file, `LICENSE`, `NOTICE`, or anything under `specs/` or `openspec/`, and never
  `AGENTS.md`, `CLAUDE.md`, `charters/*.md`, `agents/*.md` or `skills/*/SKILL.md` at any depth.
  Both names of a renamed file must be prose (`gh.pr` now carries the previous filename in
  `renamed`), and an empty file list keeps the gap. The no-test gap keeps `DOCS`, and `needed()`
  keeps its own reading, because changing either moves the test or gate rules outside this item.
- Q: Does any falsy `kind` count as an owner review ruling? A: No. Only a row without the `kind`
  key counts, and a blank `head` matches no head.
- Q: Is a failed read cached? A: No, as on main: the exception leaves `_cached` before it writes.

## How this fails

1. An owner who answered `exception: o/r#n at <sha>: owner review needed` expects that to clear the
   hold. It still does, through `excepted`, which matches the `gap` text; only a bare breaking or
   exception answer with another gap no longer counts as review.
2. A docs-only PR in a repository whose docs CI is required waits on nothing and merges before docs
   CI registers. A rollup with any check still holds on running or failing CI; the plan item records
   this as an assumption the owner can overturn.
3. A repository with no `pull_request` runs now costs two Actions reads a day instead of one; a
   rate-limited host answers the second with an error, which shows the gap rather than a pass.

## Breaking

Three outward changes to what `wuwei evidence` and `wuwei status` report:

1. An owner review that a `breaking:` or `exception:` ruling cleared on main now holds the merge. A PR
on `owner_paths` that was ready on main reads `owner review needed` until the owner answers
`owner review: <owner/repo>#<n> at <sha7>` (or approves on GitHub at the head).
2. When the Actions host is unreadable, the gap text changes from `CI not started at <sha7>` to
   `CI not started at <sha7> (Actions host unreadable: <error>)`. A reader matching the old text
   exactly must match the prefix instead; no code in WUWEI matches it exactly.
3. A head whose diff is only prose or specs (see FR-002) is no longer held by `CI not started`; on
   main it was held until checks registered.

Migration: for each open PR on `owner_paths` that relied on a breaking or exception answer, ask the
owner review question at its head.

## Assumptions

- A docs-only change is safe to merge before docs CI registers (from the plan item); overturned if
  the owner wants docs CI to hold merges, in which case point 2 reads the workflow's paths instead.
- The error text in the gap is the exception's own message; a `GhError` carries the host's message,
  which holds no secret (it is what `gh` prints). Overturned if a host error ever echoes a token.
- The cache key `ci-<repo>` is unchanged, so a `[]` cached by main for a repository that runs only
  `pull_request_target` reads as no CI for up to a day after upgrade. Overturned if that day matters,
  in which case the key gains a suffix.
- A docs-only `.txt` or image diff now keeps the gap (fails closed, as on main); overturned if such
  PRs wait often, in which case `PROSE` widens.
- The second read is `pull_request_target` only after an empty `pull_request` answer, so a repository
  with both costs one read, as on main.

## Requirements

- FR-001 `owner_approved` counts a ruling only when it has no `kind` key and its non-blank head prefixes the PR head.
- FR-002 No `CI not started` gap and no Actions read when the file list is non-empty and every file, by both
  names, matches `PROSE`.
- FR-003 An unreadable Actions host gives `CI not started at <sha7> (Actions host unreadable: <error>)`.
- FR-004 A `pull_request_target` run counts as CI.
- FR-005 Vendored `.claude/` copy rewritten; runtime within 3,000 lines.
