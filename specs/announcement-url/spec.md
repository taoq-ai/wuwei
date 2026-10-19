# Feature Specification: an Announcement: line counts only as an http(s) URL alone on its line

**Feature branch**: `fix/announcement-url`
**Item**: announcement-url, tier full, goal G-2
**Input**: the arch gate on #1142 at 4b535bd. The PR body carried
`Announcement: CHANGELOG.md (placeholder ...)`, and `breaking_gaps` (cli/wuwei/evidence.py line
341 at b28a3dc) accepted any text that is not a space after the colon. A placeholder cleared a
safety gap before any announcement existed.

## The promise in my words

1. `breaking_gaps` counts an `Announcement:` line only when the text after the colon, less spaces
   and tabs around it, is one `http://` or `https://` URL with a host and no whitespace. The line
   starts at the beginning of a line of the PR body; a CRLF body counts the same as an LF body.
2. Any other text leaves the announcement gap. Its reason names the shape:
   `add "Announcement: <http(s) URL of the published client communication, release note or
   migration guide>", the URL alone on its line`.
3. The rest of `breaking_gaps` holds: a break is still declared by `!` or `BREAKING CHANGE:`, or
   read from the latest arch verdict along the PR's history (#1135); the owner's confirmation still
   binds to the head.
4. The shepherd charter says the line holds one http(s) URL and nothing else, and the client
   communication must exist at the head: a PR or issue comment, or a release note or migration
   guide already published. A changelog entry the release will write later does not count. The
   agents are rebuilt and `.claude/` is re-vendored.

The acceptance scenarios, restated:

1. A breaking PR whose body says `Announcement: CHANGELOG.md (placeholder)`: `wuwei evidence`
   shows the announcement gap, and its text names the http(s) URL shape.
2. A breaking PR whose body says
   `Announcement: https://github.com/o/r/issues/1#issuecomment-1`: the announcement gap clears and
   the only breaking gap left is the owner's `breaking:` confirmation.

## How this fails

1. A placeholder still passes because the pattern is loose somewhere: a URL inside prose
   (`see https://...`, `https://... (later)`), a scheme the pattern did not mean (`ftp:`,
   `file:`, `javascript:`), an empty host (`https://`, `https:///n`), a URL on the next line, or a
   Unicode space that `\s` and `\S` read differently. Each is a test row, and the probe reads
   12,960 generated bodies against a `urllib.parse` oracle with no hole.
2. A real announcement is refused: GitHub returns PR bodies with CRLF line ends, so a pattern
   anchored on `$` without `\r` would refuse every URL in a body edited in the web UI. A CRLF row
   and the probe's line-end class pin it; a mutant that drops `\r` is killed.
3. A PR that was mergeable on main now holds (its `Announcement:` names a file or says TBD). That
   is the intent, and it is a breaking change to the evidence contract; the PR declares it with
   migration notes. On 2026-10-18 no open PR in taoq-ai/wuwei carries an `Announcement:` line (REST
   read of the open pulls), so none is newly held here; other repositories are unmeasured.

## Clarifications

### Session 2026-10-18

- Q: Does a URL with prose before or after it count (`see https://x`, `https://x (posted)`)?
  A: No. The value is the URL alone, so the shape is one a reader and the code read the same.
- Q: Does a Markdown link or an angle-bracket URL count (`[n](https://x)`, `<https://x>`)?
  A: No, by the same rule; the gap text names the shape to write instead.
- Q: Is the scheme read case-blind (`HTTPS://x`)? A: No. The line itself is read case-sensitive
  (`announcement:` never counted on main), and seats write lowercase schemes. Recorded under
  Assumptions.
- Q: What when the body has two `Announcement:` lines, one a placeholder and one a URL? A: The URL
  line counts; any line of the right shape is the announcement.
- Q: Does the code check the URL resolves or is published? A: No. WUWEI does not fetch it (no
  network call from evidence for an arbitrary host). The charter asks the shepherd for an
  announcement that exists at the head, and the owner reads the link in the `breaking:` question.
- Q: Does a `http://` URL count? A: Yes, the promise says http(s).

## Assumptions

- The value must be the URL alone. Overturned if the owner wants prose around the URL; that is a
  one-line change to the pattern.
- The scheme is lowercase only. Overturned if a seat or the owner writes `HTTPS://`; add `(?i:https?)`.
- No reachability check. A fake URL still passes the code; the owner reads it in the `breaking:`
  question, which stays the last word. Overturned if the owner wants evidence to fetch it.
- The change is breaking (it holds PRs that read mergeable on main), so the title takes `!` and the
  body a `BREAKING CHANGE:` line. Overturned if the arch gate reads it as internal.

## Breaking

`wuwei evidence`, the board and the merge door (`guards.merge_door`) now hold a breaking PR whose `Announcement:` line is
not a URL alone on its line (a file path, `TBD`, `see CHANGELOG`, a URL inside prose, a non-http
scheme). The gap text changes to name the shape.

- Migration: post the announcement first (a PR or issue comment, or a published release note or
  migration guide) and put its http(s) URL alone after `Announcement:`. No config, state or ledger
  change.

## Rollback

Revert the merge commit. The pattern goes back to any text after the colon; no state, config or
ledger format changes.

## User scenarios

### US1: a placeholder leaves the gap and the reason names the shape (P1)

Acceptance 1. Tests in tests/test_evidence.py and tests/test_breaking.py.

### US2: a URL alone clears the announcement gap and leaves the owner's confirmation (P1)

Acceptance 2. Tests in tests/test_evidence.py.

### US3: the shepherd charter asks for an announcement that exists at the head (P2)

Test in tests/test_charters.py.

## Requirements

- FR-001: `breaking_gaps` counts a line matching `^Announcement:[ \t]*https?://[^\s/?#]\S*[ \t\r]*$`
  (multiline), and no other, in time linear in the body: a 65,536-character body reads in under 1 s.
- FR-002: Any other body leaves the gap with the text that names the shape.
- FR-003: The break detection and the confirmation are unchanged (#1135 tests pass unedited but for
  the gap text).
- FR-004: charters/shepherd.md states the shape and that the announcement exists at the head;
  agents rebuilt; `.claude/` re-vendored; runtime within the item's budget of 2 lines.
- FR-005: docs/design.md, docs/site/reference.md, docs/site/concepts/evidence.md and
  charters/_common.md name the same shape, without brackets, and the gap text says so.

## Success criteria

- SC-001: Each acceptance scenario has a test that passes at the head; the placeholder rows ran red
  on main.
- SC-002: The probe finds 0 holes and kills every mutant; the full suite passes.
