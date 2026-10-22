# Feature Specification: a smart tier picks each item's gates from its Cynefin domain and raises them on measured diff signals

**Feature branch**: `leone/smart-tier`
**Item**: smart-tier (taoq-ai/wuwei), tier full, goal G-4
**Input**: the owner, 2026-10-22: "Can we please add a 'smart' tier? Standard turns out to be too slow
sometimes and full even worse. I'd like to have the tier adjusted to the complexity of the item. And
can we use a formal framework for defining the complexity of the item?" Approved scope: Cynefin plus
measured signals. Today's blocking findings by gate: quality 4, security 5, arch 2 (both changes to a
trust rule), goal 0.

## The promise in my words

A new tier, `smart`, is what `wuwei plan add` gives a new item. The lead files each smart item
under one Cynefin domain (clear, complicated or complex) with one line of evidence. The gates
start from the standard rows (code takes quality, risky or owner paths add security, a contract or
a wide change adds arch). A complicated item on a trust path adds arch. A complex item takes
quality, security and arch, a short `How this fails` and the spec engine's artifacts. Goal runs only
when the promise is marked in doubt. Signals measured at the head only ever add a gate: a changed
Python function whose decision count, read with `ast`, rises to McCabe complexity over 10 adds
security; a patch that names what a guard waives or refuses adds arch. No field a lead or seat
writes can take a gate away. Light, standard and full work as before.

The acceptance scenarios, restated:

1. A clear item that changes plain code (no risky, owner or contract path, no rise, no guard
   words) owes quality alone.
2. A clear item whose diff adds a branch to a function on a risky path owes security as well.
3. A complicated item whose diff changes what a guard waives owes arch.
4. A full item owes what it owed before: arch, quality, security and goal.

Outside: classifying old items (they keep their tiers); a cyclomatic measure for languages other
than Python (their files are measured by path, size and guard words only).

## How this fails

1. A guard change whose patch names none of the guard words (say a renamed helper that now
   returns early) reads as no guard change, so a clear item on it owes no arch. In this repository
   `guards.py`, `hook.py` and `evidence.py` are owner paths, so security still runs; elsewhere it
   is a residual risk, probed only by the word list.
2. A lead files a complex item as clear to skip the spec engine and the arch read. The measured
   signals still raise the gates (the lowering probe: 70 cases, 0 holes), but the spec artifacts
   are not a gate and go. The steward reads the domain against what escaped.
3. The complexity read costs two contents reads per changed Python file per head, on the board and
   at the doors. It is cached a day per base and head sha, so a warm board makes no new call, but a
   PR with hundreds of Python files makes hundreds of reads once.

## Clarifications

- Q: Where is the domain stored? A: the plan item field `domain`, one line, `"<clear|complicated|complex>: <why>"`,
  set by `wuwei plan add --domain` or the lead's candidates file. `plan.add` refuses another
  shape. Evidence reads only `clear:` and `complicated:`; anything else, a missing field included,
  reads as complex.
- Q: How is "in doubt" stored? A: `in_doubt: true` on the item (`--in-doubt`). A re-add without
  the flag keeps it.
- Q: What is a change to what a guard waives or refuses? A: a code file whose patch (hunk headers,
  context and changed lines) names deny, denied, refuse(d/s), ask, allow(ed/s), waive(d/s),
  excepted or exception(s) in any case, or `permissionDecision`, `PROCESS` or `DUTY`; and a code
  file with no patch, which is unmeasured.
- Q: What is the cyclomatic measure? A: per Python function, the decision nodes `ast` finds (if,
  conditional expression, for, async for, while, except handler, assert, boolean operator,
  comprehension, match case), summed over functions that share a name, at the merge base and the
  head. A function whose count rises and reaches 10 or more (McCabe complexity over 10, his own
  threshold) raises security. A file missing or unparsed at the base reads empty; unread or
  unparsed at the head, or with no head sha, it counts as a rise. Test files and files with no
  added lines are not measured.
- Q: What does the error budget do to smart? A: it rises one step to standard and takes its full
  gate set.
- Q: Which rows does smart share with standard? A: all of them: risky or owner paths add security;
  over 200 non-prose lines or 10 code files add arch; a contract adds arch.

## Requirements

- FR-001: `smart` is a tier; `wuwei plan add` and the candidates file default to it; `--domain` and
  `--in-doubt` record the domain and the doubt.
- FR-002: at smart, the gates are the standard rows plus the domain floor and the measured signals,
  and no item field removes one.
- FR-003: a complex smart item owes the spec engine's standard artifacts as safety; clear and
  complicated owe none.
- FR-004: the create and ready doors read the complexity at the branch head and its merge base.
- FR-005: light, standard and full owe what they owed before.

## Assumptions

- The domain lives in one field with its evidence (`clear: <why>`), so the reason travels with it;
  overturned if the owner wants the evidence in `why`.
- The threshold is McCabe's 10, reached by a rising function, not any rise: one added branch in a
  small function stays clear. Overturned if escapes show small rises hiding defects.
- A complexity rise raises security, a guard change raises arch (today's two arch findings were
  trust-rule changes). Overturned if the steward's gate yield shows the other pairing.
- The guard words are read over the whole patch, context included, so a change to a continuation
  line of `PROCESS` is caught by the context line that names it. It fails toward more arch.
- Smart under an overrun error budget rises to standard.
- The lead's charter now gives `standard` or `full` only when the owner asks; the domain carries
  the rest.

Rollback: first set each open `smart` item to `standard` (`wuwei plan add <id> "<title>" --tier
standard` with its scores), then revert the PR. Reverted code reads a leftover `smart` item as
quality only, and an overrun budget on one raises a KeyError.
