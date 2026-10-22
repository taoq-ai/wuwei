Verdict: PASS
Gate: security
Item: flow-board
PR: taoq-ai/wuwei#1252
Head: a38050da6d9b79ec593a4c9e0ddafa63d0401d00
Confidence: medium

## Findings
- [low] cli/wuwei/board.py:135 blocks: no. limit() reads standards.md as strict UTF-8 and calls int() on an unbounded digit run. A Latin-1 byte or a 4301-digit `WIP limit:` line makes board.compute raise: the Stop reminder goes silent, SessionStart drops the board, and `wuwei status` and `wuwei report` crash. The hook records hook.error and fails open, and no door moves. Main already fails this way through evidence.review_place (strict UTF-8) whenever a ready PR is open; the head extends that to every board. Suggested fix: errors='replace', `[0-9]{1,6}`, or a try that returns the default.
- [low] cli/wuwei/board.py:135 blocks: no. The pattern `\bWIP limit:` matches anywhere in a line, not only on an owner's own line. A steward or role standards line that quotes the phrase (probe: `- sentinel-quality: a WIP limit: 0 note` reads as 0) sets the limit. Anchoring it like review_place (`^[-*\s]*`) would close this.
- [low] blocks: no. .wuwei/standards.md has no guard (guards.py protects only ledger and cache), and the steward writes it by design, so any seat can set either limit. Raising the limit removes only the advisory team row. Setting `WIP limit: 0` queues every item that has no PR, but the Stop still says "Left out: 6 waiting ... or the WIP limit", asks once to arm the watch, and the board shows each item as `queued ... WIP limit 0` [waiting]. The owner still hears about queued work, and no door decision moves. This is the existing trust model for standards.md.
- [low] cli/wuwei/hook.py:84 blocks: no. When crowded() raises (a non-UTF-8 standards.md), handle() fails open for Agent/Task, which is not a door. The launch passes as it would on main, but the model-table note from advise() is lost with it (hook.error recorded).
- [low] blocks: no. The builder's corpus count reads 294; tests/fixtures/routes.json holds 288 routes at both shas.

## Probes
- Route differential: the corpus sha256 is de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at main 1b8ef2b8 and at the head. All 288 routes went through hook.handle PreToolUse as Bash calls, plus 8 Agent/Task launches (plain, held item, Codex with no prompt, model departure), under 4 scenarios: 0 seats, 9 seats in the session, 9 seats with `WIP limit: 0` and `Seat ceiling: 0`, and 9 seats with limits of 999999. That is 1184 calls per sha. No permissionDecision moved (deny 217 and the rest the same at both shas). The only change is a new additionalContext note on 8 Agent/Task launches with 9 or more seats; the held-item deny is unchanged. With a model departure, the note is prepended to the advise note, and permissionDecision stays absent.
- Note text: crowded() and the team and queued gaps interpolate only ints (the seat count, the ceiling, busy, cap). They carry no ledger strings (session ids, roles). The ceiling can only show when seats >= ceiling, so the text stays bounded.
- Failure modes at the head (limit, Agent launch, ledger-write deny, Stop, SessionStart):
  - latin1: UnicodeDecodeError; the board is lost, as described above.
  - bigint: ValueError; the board is lost, as described above.
  - directory, symlink to /dev/null, symlink loop, FIFO: isfile is false and the default applies.
  - a 50 MB file: reads, and the last line wins.
  - Arabic-Indic digits: ignored, and the default applies.
  - a mode 000 file: unmeasured, because the probe ran as root.
  - The ledger-write door still denies in every case.
- Stop and SessionStart at main and head, 6 items, with and without a PR: main already goes silent on latin1 when a PR is open; the head is silent on latin1 and bigint either way. With WIP 0, the head still reminds and names the queued count.
- Mutants, each applied to both trees:
  - hook.py:87 `>=` to `>`: killed by test_a_launch_over_the_seat_ceiling_passes_with_a_note_and_one_under_it_has_none.
  - board.py:127 `busy > cap` to `>=`: killed by test_the_team_row_names_work_over_the_wip_limit_and_seats_over_the_ceiling.
- New tests at the head (pytest -k ceiling/wip/queue/stop_lists on test_hook and test_watch): 11 passed. The vendored .claude copy diff is identical to cli/ apart from the paths.
- Supply chain: no dependency, lockfile or workflow changed. The repo CI (tests.yml) runs no secret or SAST scanner, so scanners are unmeasured.
- Confidence medium: the probes are direct and cover both shas. Unmeasured: a mode 000 file (the probe ran as root) and scanner coverage.

## Residual risk
A malformed or adversarial .wuwei/standards.md now silences the Stop reminder and the SessionStart board in every state, not only when a PR is open. This is fail-open on advice, never on a door.
