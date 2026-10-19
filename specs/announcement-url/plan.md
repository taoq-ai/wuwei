# Implementation plan: announcement-url

**Spec**: `specs/announcement-url/spec.md`
**Item**: announcement-url, tier full, goal G-2

## Technical context

- `cli/wuwei/evidence.py` `breaking_gaps(root, ref, pr, item_id)` decides the break (title `!`,
  `BREAKING CHANGE:`, or the latest arch verdict along the PR's history, #1135), then reads the
  body for `^Announcement:[ \t]*\S`, then the owner's `breaking` ruling at the head.
- Callers: `evidence.gaps`, so `wuwei evidence`, the board, the merge door and the PostToolUse
  context after `gh pr create`. The create and ready doors read only `gate_gaps`.
- Runtime at the base b28a3dc: 2,992 lines (`cat cli/wuwei/*.py | wc -l`); budget 2 for this item.

## Design

1. The pattern becomes `^Announcement:[ \t]*https?://[^\s/?#]\S*[ \t\r]*$` under `re.M`: a
   lowercase http(s) scheme, a first host character, the rest of the URL with no whitespace, then
   only spaces, tabs or a CR to the end of the line. One host character, not `[^\s/?#]+\S*`: the
   two runs overlap and backtrack with the square of the line length (security gate, round 1).
2. The gap text names the shape: `add "Announcement: <http(s) URL of the published client
   communication, release note or migration guide>", the URL alone on its line, without brackets`.
3. charters/shepherd.md Merge section states the shape and that the announcement exists at the
   head; `bin/wuwei agents build`; `setup.vendor('.')`.
4. No change to the break detection or the confirmation.

## Verification

- New tests red on main in a `git archive` copy, green at the head; full suite green.
- `specs/announcement-url/probe.py` run in a `git archive` copy: generated bodies against a
  `urllib.parse` oracle with no hole, every mutant of the pattern killed.
- `bin/wuwei agents build` reports the agents match; runtime within budget.

## Constitution check

Stdlib only, test first, no new config key, no new door, no network call, runtime within the cap
and the item's budget.
