# Feature Specification: the SessionStart context fits Claude Code's 10,000-character cap

**Feature branch**: `fix/session-context-cap`
**Item**: session-context-cap, tier full, goal G-1
**Input**: Claude Code caps a hook's `additionalContext` at 10,000 characters. Past that, the
session gets a file path and a 2,000-character preview (code.claude.com/docs/en/hooks.md, read
2026-10-18). `hook.session_start` injected `_way.md`, `_common.md` and `planner.md` in full, then
goals and standards (up to 3,000 characters each) and the whole board. It measured 16,092
characters for an empty workspace at main, so a planner session saw only a preview and read its
charter by hand.

## The promise in my words

At session start the hook sends at most 10,000 characters. It keeps what the planner needs before
its first move and names the rest by path:

- the WUWEI CLI path;
- the way (`_way.md`) in full;
- the Decisions and Done sections of `_common.md`, the rules the way points to;
- one line naming the files to read before the first plan pass: the planner charter
  (`planner.md`), the rest of `_common.md`, and the workspace goals and standards;
- the board in its own order. When the whole does not fit, the board drops its last item lines
  until it does, and says how many it left out and that `wuwei status` lists them all.

A charter fitness test fails when the context is over 10,000 characters, for an empty workspace
and for a 40-item board with 3,000-character goals and standards.

The acceptance scenarios, restated:

1. An empty workspace at the head: the context is at most 10,000 characters and names the CLI
   path and the planner charter's path.
2. A workspace with 40 open items: the context stays under 10,000 characters and says how many
   items it left out.

## How this fails

1. A charter grows (`_way.md`, or the Decisions and Done sections) until the fixed part leaves the
   board little room. The board then shows few items, and the planner orients from `wuwei status`.
   The fitness test asserts at least 10 of 40 items show, so that growth fails a test first.
2. The board has no item line left to drop (only andon lines, or every item already dropped), so
   trimming stops before the whole fits. The final cut at 10,000 then ends the text mid-line and
   can drop the left-out count. The cap holds; the count can be lost. A test holds the cap with 30
   long andon lines, and asserts the rules still come whole before them. On a board with an item
   left to drop the cut never fires (fix round 2): the trim measures the final string itself, so
   it stops only under 10,000 characters with the left-out line whole.
3. The planner trusts the inlined rules and never reads `planner.md`, so it misses rules such as
   the model table or the gate order. The pointer line says to read it before the first plan pass,
   and `/wuwei-run` already reads goals and standards at step 2. A planner that skips it is the
   residual risk; the cap leaves no room to inline the charter (8,708 characters alone).

## Clarifications

### Session 2026-10-18

- Q: Why not inline a trimmed `planner.md`? A: Its two largest sections (Running the work, 3,681
  characters; Model and effort, 3,311) would leave the board under 2,000 characters. A pointer
  with the absolute path costs one line, and the planner reads the file once.
- Q: Why leave goals and standards out? A: Together they could take 6,000 characters. The
  `/wuwei-run` skill reads both files at its step 2, and the pointer names their folder. The
  promise lists what the planner needs at start; goals and standards are needed at a plan pass.
- Q: Why a final cut at 10,000? A: It holds the cap when the board has no item line left to
  drop (see How this fails 2).
- Q: Which items are dropped? A: The last lines. `board.compute` lists owed replies first, then
  each repository in name order with its items highest score first. In a one-repository workspace
  the lowest scores go first; across repositories, the last repository's lowest items go first.
  Andon lines at the top always stay. Ranking the whole board by score would change `board.py`,
  outside this item's files; the left-out line and `wuwei status` cover the rest.
- Q: Does this change any door? A: No. Only `session_start` changes; the route corpus differential
  shows no route, guard or payload moving.

### Session 2026-10-19 (fix round 2)

- Q: Why no room constant? A: Two rounds tested a 9,900 room, and its power to catch a change
  hung on path lengths: the plugin path appears three times in the context and the workspace root
  once, so a mutant to 10,000 or 9,990 passed at 21 and 51 of 200 root lengths. The trim now
  measures the final string (rules, pointer line, board and the left-out line it would carry)
  and drops the last item while that string is 10,000 characters or more. No number is left to
  tune, so the tests can push a board to exactly 9,999 and 10,000 characters at any path length.
- Q: What is an item line? A: A line that starts with `- <item id> ` for an item on the board,
  the shape `board.text` writes. The trim drops from the last such line to the end, so an item
  goes whole with the lines its title's newlines make, and the count is one per item.

## Composition with PR #1146 (models-record)

PR #1146 edits `hook.py` in `pre_tool`, `subagent_stop`, `_verdict_problem` and `post_tool`, and
`planner.md` rules 1, 4 and 7. This item edits only `session_start` and no charter. The hunks do
not overlap, and since `planner.md` is no longer inlined, its growth no longer adds to the session
context. Whichever lands second rebases without a conflict in `hook.py`; the vendored copy is
rebuilt with `setup.vendor('.')`.

## Requirements

- FR-001: `session_start` returns at most 10,000 characters of `additionalContext`.
- FR-002: the context names the CLI path, the `planner.md` path, and holds `_way.md` and the
  Decisions and Done sections of `_common.md`.
- FR-003: a board cut to fit says how many items it left out, as its last line, whole ("1 more
  item" in the singular).
- FR-004: runtime lines grow by at most 6 (the item's budget); 6 after fix round 2.

## Assumptions

- The 10,000 cap is the harness's; overturned if a live SessionStart shows the full text inline.
- Goals and standards are read by `/wuwei-run`, so leaving them out of the session start loses no
  rule; overturned if a planner session plans without reading them.
- A Codex session start has no smaller cap than Claude Code's; overturned by a Codex doc or a live
  run that shows one.
- The cap is counted in Python code points (`len` of a `str`). The harness's own unit is
  unmeasured. If it counts UTF-16 units, as a JavaScript string length does, a board with emoji
  or other astral characters in titles or andon reasons can be longer there than here (40 titles
  of 200 emoji: 9,875 code points, 13,875 UTF-16 units). The harness then shows its file path and
  2,000-character preview, the mode main is always in. Overturned by a harness doc or a live run
  that names the unit.
- A title or andon reason may hold a newline, since `plan.add` and `board.andon` do not refuse
  one. Only a line in an item's own shape (`- <item id> `) counts, so a reason line that starts
  with `- ` no longer moves the trim. A reason line that copies a real item's id and a space
  still reads as that item; refusing newlines at input would change `plan.py` and `board.py`,
  outside this item. Overturned if a real andon reason carries such a line.

Rollback: revert the commit; the hook then injects the full charters again.
