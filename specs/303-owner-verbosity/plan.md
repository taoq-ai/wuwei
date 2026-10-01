# Implementation Plan: Verbosity levels for what the owner reads, and humanizer-checked text

**Branch**: `303-owner-verbosity` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

One config table `[owner.verbosity]` and one resolver `workspace.verbosity(config, surface)`
shape five owner surfaces. One formatter, `decision.present(identifier, fields, level)`, serves
the new `wuwei decision show`, the DM escalation, the reply echo and the new `more D-n` DM reply.
The report, the digest and the PR nudge read their own level at the one spot that builds their
text. The humanizer rule and its ten-line checklist go once into
`charters/_common-authoring.md`, which every generated agent embeds, plus one paragraph in the
planner skill. One tell table, `outward.TELLS`, feeds the non-blocking `style` finding on drafts
and decision records, the `ai_tells` metric and the template pinning test.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Testing**: pytest (dev only), in-process; fake chat transport and fixtures as in
`tests/test_control_plane.py` and `tests/test_remote.py`.
**Project Type**: CLI plugin (`cli/wuwei`), charters, skills, docs.
**Constraints**: no new module, no new dependency, no new blocking rule, no subprocess in core.
**Scale/Scope**: about 12 source files touched, all at existing functions.

## Constitution Check

- I Stdlib only: regexes and string formatting only. PASS.
- II Three-state exits: `decision show` exits 0 printed, 1 invalid record, 2 unreadable or
  symlinked record; `more` returns the transport's exit. PASS.
- III One behaviour, one function: `decision.present` is the only decision formatter;
  `outward.tells` is the only tell check; `workspace.verbosity` the only level resolver. PASS.
- IV Test first: every task pair in tasks.md is test then code. PASS.
- V Ponytail: no new module or abstraction; `_scored` is extracted from `evaluate` so `present`
  does not copy the scoring. PASS.
- VII Security: `more` goes through `remote.dm` (security check and outward lint) and honours
  `control_plane.content = "none"`; it only reads pending owner decisions. PASS.

## Changes

### `cli/wuwei/workspace.py` (config and the shared resolver)

- Add `LEVELS = ('brief', 'standard', 'full')` and `SURFACES = ('decisions', 'digest', 'nudges',
  'dm', 'report')` near `SCHEMA`.
- `SCHEMA['owner']` gains
  `"verbosity": {"default": (str, "brief", LEVELS), **{name: (str, "", ("", *LEVELS)) for name in SURFACES}}`.
  `_validate` already rejects unknown keys and values outside the tuple.
- Add next to `zone`:

  ```python
  def verbosity(config, surface):
      """The owner's level for one surface: its own setting, else owner.verbosity.default."""
      levels = config['owner']['verbosity']
      return levels[surface] or levels['default']
  ```

  Every caller already holds the loaded config, so the level is read once per command.

### `templates/workspace/config.toml`

After the `[owner]` block (before `[host]`):

```toml
[owner.verbosity]
default = "brief" # brief, standard or full: how much decisions, the digest, nudges, the DM and the report say to you.
# dm = "" # Per surface: decisions, digest, nudges, dm or report. Empty uses default.
```

### `cli/wuwei/decision.py` (the shared formatter)

- Extract lines 66 to 84 of `evaluate` (options table through the weighted scores) unchanged
  into `_scored(fields) -> (options, passing, wants, scores)`, where `options` are the
  `[id, description]` rows, `passing` the ids passing every must in option order, `wants` the
  Wants rows. `evaluate` calls it and keeps lines 85 to 95; its return value and every error
  message stay the same.
- Add `present(identifier, fields, level)` for validated fields (callers already ran
  `evaluate`):
  - `brief`, exactly these lines:
    1. `D-3: <Question>`
    2. one per option in record order: `<id>: <description> (score <n>)`, or
       `(score <n>, fails a must)` for an option not in `passing`;
    3. `Recommended: <id>, <reason>.` where, with `others` the passing ids other than the
       recommendation: no `others` gives `the only option that passes every must`; otherwise
       `other = max(others, key=scores.get)`; equal scores give `tied with <other> on score`;
       else the Wants row with the largest `weight * (score_rec - score_other)` gives
       `ahead of <other> on <criterion>`.
  - `standard`: the brief lines, then `Context: <first nonblank Context line>`,
    `Confidence: <c>. Reversibility: <r>.`, `Blast radius: <b>`, `Pre-mortem: <p>`,
    `Revisit: <v>`.
  - `full`: `identifier`, then one entry per name in `FIELDS` order, `Name: value`; a value that
    starts on the next line (the three tables) prints as `Name:` followed by its lines, with no
    trailing space.
  Brief keeps the option text `<id>: <description>` as a prefix, so the existing DM tests that
  look for `A: Implement fix` still hold.
- `lint`: after `evaluate`, `found = outward.tells(text)`; return
  `0, f'OK: {option} ({scores[option]})'` plus `'\nstyle: ' + ', '.join(found)` when `found`.
  Exit codes and the rejection path are unchanged. Import `outward` at module level (it imports
  only `exits` at load, so no cycle).

### `cli/wuwei/commands/decision.py` (`decision show`)

- `register`: add `show` with `id` and `--full` (`store_true`), `func=run`.
- Add `show(args) -> (code, message)`: `root = workspace.find_workspace()`,
  `path = today_path(args.id, root)`; a symlinked record or directory already makes
  `today_path` raise `record must belong to today`, which the CLI reports with exit 2 (built
  that way: a separate symlink check would be dead code); a read error returns
  `2, f'decision show: could not read {path}: {exc}'`; `evaluate` raising `ValueError` returns
  `1, f'decision show: {exc}'`. Level is `'full'` with `--full`, else
  `workspace.verbosity(workspace.load_config(root), 'decisions')`. Message is
  `present(args.id, fields, level)`, plus `\nFull record: wuwei decision show <id> --full` when
  the level is not `full`. No event, no state write.
- `run`: dispatch `show` through the existing `code, message` print.

### `cli/wuwei/control_plane.py` (DM decision text)

- `render(identifier, fields, content, level)`: `content == 'none'` returns today's
  `<id> options: A, B`; otherwise `decision.present(identifier, fields, level)`.
- Add `_level(root)`: `workspace.verbosity(workspace.load_config(root), 'dm')`.
- `escalate`: the widget branch (`transport is None`) renders at `_level(root)`; the transport
  branch renders at `_level(root)` and, when content is not `none` and the level is not `full`,
  appends `\nReply more <id> for the full record.` before `'\n' + HELP`.
- `poll_replies`: the echo lines render at `_level(root)`. `HELP` and `parse` are unchanged.

### `cli/wuwei/remote.py` (`more D-n`)

- `VOCABULARY`: `'Commands: plan, status, report, ask <question>, stop <session>, stop all. '
  'Decisions: approve D-n, option X on D-n, more D-n, drop it.'`
- `parse`: before the final `return None`, `more (d-[1-9][0-9]*)` returns
  `('more', <id upper-cased>)`.
- Add `NOT_PENDING = '{identifier} is not waiting on you.'` and
  `ON_HOST = 'The full record of {identifier} is on the host.'`.
- Add `more(root, identifier, *, transport=TRANSPORT)`: `decisions = control_plane.pending(root)`;
  not pending returns `_say(transport, root, NOT_PENDING..., 1)`; otherwise send
  `control_plane.render(identifier, decisions[identifier], control_plane._content(root), 'full')`
  with `transport.dm`; a lint refusal (exit 1) sends `ON_HOST` instead, as `escalate_new` does;
  return the send's exit.
- `handle`: after `verb, argument = command`, `if verb == 'more': return more(root, argument,
  transport=transport)`. `more` is not in `FACTOR`; the changed-sender refusal still applies.

### `cli/wuwei/listen.py` (PR nudge)

- `notify`: `level = workspace.verbosity(config, 'nudges')`. At `full`, when the event's
  `payload['fields']` is a nonempty list of strings, append ` (fields: a, b)` to the summary
  before the shepherd tail. `brief` and `standard` send today's line.

### `cli/wuwei/watch.py` (digest)

- `digest`: `level = workspace.verbosity(config, 'digest')`; each line is
  `- <id>: <option>` plus ` (decisions/<id>.md)` at `full`. Nothing else changes.

### `cli/wuwei/report.py` (report)

- `build`: `level = workspace.verbosity(workspace.load_config(root), 'report')`. Keep the four
  outcome lines as `(title, key)` pairs. At `brief` the first section is `## Changed` with the
  outcome lines whose `measured[key] != baseline[key]`, at most three, else `none`; Outcome,
  Quality by band and Process metrics are left out. At `standard` the output is byte-identical
  to today. At `full` it is today's output with ` (decisions/<id>.md)` after each Decisions
  answered line. Merged, Open at close, Parked, Decisions answered and Carry keep their headings
  at every level, so `remote.handle`'s `report` counts keep working.

### `cli/wuwei/outward.py` (tell table)

```python
# Structural tells from the humanizer skill (MIT, 3.1.0). A hit is a style finding, never a refusal.
TELLS = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in (
    ('not-x-but-y', r"\bnot (?:just|only|merely) [^.\n]{1,80}?\bbut\b|\bit['\u2019]?s not [^.\n]{1,60}?[,;] it['\u2019]?s\b"),
    ('closer', r"\b(?:that is the real win|that distinction matters|read that again|let that sink in|the message was clear)\b"),
    ('run-up', r"\b(?:let['\u2019]?s dive in|let['\u2019]?s break (?:this|it) down|here['\u2019]?s what you need to know|here['\u2019]?s the thing|without further ado)\b"),
    ('saying', r"\b(?:at its core|the real question is|what really matters|the heart of the matter)\b"),
    ('dash', r"\u2013| -- "),
    ('inflation', r"\b(?:plays? an? (?:key|crucial|vital) role|evolving landscape|setting the stage for|lasting legacy|the future looks bright)\b"),
    ('sales', r"\b(?:groundbreaking|breathtaking|nestled|renowned|must-visit|stunning|diverse array)\b"),
    ('stock-word', r"\b(?:delv(?:e|es|ed|ing)|tapestry|testament|showcas(?:e|es|ed|ing)|pivotal|meticulous(?:ly)?|intricate|intricacies|vibrant|garner(?:s|ed)?|bolstered|interplay)\b"),
    ('bold-label', r"(?m)^\s*(?:[-*]|\d+\.)\s+\*\*[^*\n]+\*\*"),
    ('chat-leftover', r"\b(?:i hope this helps|great question|you['\u2019]?re absolutely right|let me know if|would you like me to)\b|\b(?:certainly|of course)!"),
))


def tells(text):
    """Names of the tells in text, each kind once, in table order."""
    return [name for name, pattern in TELLS if pattern.search(text)]
```

`lint`, `classify` and the check functions are unchanged: the em-dash and emoji refusal stays
the only blocking writing rule.

### `cli/wuwei/drafts.py`

- `create`: the row gains `'style': outward.tells('\n'.join(texts))`. `read` ignores extra keys,
  so older rows stay valid.

### `cli/wuwei/metrics.py`

- `collect`: in the existing drafts loop, build `ai_tells = {row['id']: len(row['style'])}` for
  rows that carry `style`; then add `path.stem: len(outward.tells(text))` for each non-symlink
  `directory / 'decisions' / 'D-*.md'`. `event_metrics['ai_tells'] = ai_tells`. The report's
  process metrics and the retro's metrics print it through their existing JSON dump.

### `cli/wuwei/interview.py`

Append to `QUESTIONS`:

```python
{'id': 'verbosity', 'scope': 'workspace', 'header': 'Verbosity',
 'question': 'How much should decisions and messages to you say?',
 'choices': (
     ('Brief', 'The question, scored options and the recommendation; the rest on request.',
      {'owner.verbosity.default': 'brief'}),
     ('Standard', 'Also the context, reversibility, blast radius and pre-mortem.',
      {'owner.verbosity.default': 'standard'}),
     ('Full', 'Every field of each record.', {'owner.verbosity.default': 'full'})),
 'free': None},
```

`settings` maps it to `(('owner', 'verbosity'), 'default', level)`; `calibrate.settle` and
`apply` already add or replace it.

### `charters/_common-authoring.md` (the writing section) and `agents/*.md`

Append this section (numbered 1 to 10 under its own heading, as `test_charters` requires), then
run `bin/wuwei agents build` from the repository root outside a workspace and commit the nine
regenerated agents. Tools do not change, so the ZIRAN baseline does not change.

```markdown
## Writing for a person

Text written for a person (decision records, PR bodies and review comments, drafts, retro summaries, digests and briefing packs) is rewritten with the `humanizer` skill in embedded mode before it is saved or posted, when the skill is installed. Without it, check the text against this list. The CLI lint counts the mechanical tells as `style` findings; only an em dash or an emoji is refused.

1. Lead with the decision or the fact the reader needs; leave out background the reader already has.
2. State the point directly. Do not deny a claim nobody made so that the real point sounds larger.
3. Cut openers that announce the point and closing lines that repeat it.
4. Group items in threes only when there are three real items.
5. Join clauses with a comma, colon, period or parentheses, never with a dash or a double hyphen.
6. Keep ordinary facts ordinary: no claims of significance or legacy the evidence does not show.
7. Say what a thing is and does, without advertising adjectives.
8. Prefer the plain word to the showy one models overuse, and is, are or has to serves as or stands as.
9. No bold label on every list item and no decorative headings; write headings in sentence case.
10. Remove chat leftovers: greetings, praise, offers of more help and sign-offs around the content.
```

### `skills/wuwei-plan/SKILL.md`

One paragraph after the opening paragraph (keep it there so #302's mandate edits elsewhere in the
skill merge cleanly):

```markdown
Present a pending owner decision with the text `wuwei decision show D-n` prints; the owner asks for the rest with `--full` on the host or `more D-n` in the DM. Rewrite any text written for a person with the `humanizer` skill in embedded mode when it is installed; otherwise apply the checklist in `charters/_common-authoring.md` under Writing for a person.
```

### Docs

- `docs/site/configuration.md`: rows for `owner.verbosity.default` and the five surface keys in
  the owner table; the interview section lists the `verbosity` question.
- `docs/site/daily.md` section 5 and `docs/site/reference.md` (decision paragraph near line 93):
  `bin/wuwei decision show D-<n>` and `--full`.
- `docs/site/remote.md`: the new `VOCABULARY` text at its three places and `more D-n` in
  section 7.
- `docs/site/concepts.md`: a `## Writing for the owner` paragraph: the verbosity levels, the
  humanizer rule for seats, the non-blocking `style` finding and `ai_tells`, and the attribution
  "humanizer skill, version 3.1.0, MIT license".

## Test plumbing (existing tests that move with the change)

- `tests/test_remote.py` `escalation()` helper: build the expected text as
  `render(id, fields, 'summary', 'brief') + '\nReply more <id> for the full record.\n' + HELP`.
- `tests/test_control_plane.py`: `test_escalate_sends_summary` keeps its phrases; the
  `content = "none"` tests are unchanged.
- `tests/test_report_retro.py`: tests that read Outcome, Quality by band or Process metrics write
  `[owner.verbosity]\nreport = "standard"` into the fixture config (or assert the `full` form).
- `tests/test_interview.py::test_interview_on_the_terminal`: one more reply and 13 answers.
- `tests/test_docs.py` remote page phrases follow the new `VOCABULARY` automatically.

## What must not change

- `decision.evaluate`'s return shape and error messages, the decision lint's exit codes, record
  rejection events and the decision record format (no new field).
- `control_plane.parse`, `HELP`, `pending` and the `content = "none"` texts.
- `outward.lint`, `classify`, `check_tier`, `check_lint`: no new refusal; the em-dash and emoji
  refusal and its profile handling stay as they are.
- `brief.style.length` and seat briefs; the status line and its latency budget; `wuwei nudges`
  JSON; the retro layout apart from the metric in its JSON.
- `remote.dm`'s security check and lint before every send, and the second factor for `plan` and
  `ask`.
- Charter versions and the role charters other than `_common-authoring.md`.
