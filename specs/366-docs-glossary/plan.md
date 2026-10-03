# Implementation Plan: A glossary, plain-word interview options and one newcomer walkthrough

**Branch**: `366-docs-glossary` | **Date**: 2026-10-03 | **Spec**: `specs/366-docs-glossary/spec.md`

## Summary

Docs plus two string-level code changes. One `## Glossary` section at the top of
`concepts.md`, linked from the first prose use of each term on the README, the docs index and
the daily path. The interview table keeps its labels, ids and effects; only headers,
questions and option descriptions are rewritten so the effect comes first and the term
follows in brackets. `goals edit` / `voice edit` print one success line (F25). `daily.md`
gains the output of a clean setup and a clean first plan. All checks live in existing test
files; one shared `GLOSSARY` tuple in `tests/test_docs.py` drives the glossary, link and
interview checks.

## Technical Context

Python 3.11 stdlib, pytest for tests. No new modules, no new runtime helper, no new
dependency. Docs are Jekyll today (`.html` links); #392 moves them to MkDocs after this
issue, so link checks accept `.html` and `.md`.

## Constitution Check

- I stdlib only: yes, string edits and one `print`.
- II three-state exits: unchanged; the new line prints only on the `CLEAN` path.
- III one behaviour, one function: the success line lives in `_owner_edit.run`, the one
  shared flow for goals and voice.
- IV test first: every change below has its failing test first (tasks.md).
- V ponytail: no glossary module, no generated docs, no label aliases; the term list is a
  test constant because no runtime code needs it.
- Style: no em-dashes, no emojis; humanizer checklist on every new sentence.

## Changes

### 1. `tests/test_docs.py` (new constant and three tests)

Add near the top:

```python
# Issue #366: the glossary terms in concepts.md order, each with the word forms that count as a use.
GLOSSARY = (('Seat', r'seats?'), ('Gate', r'gates?'), ('Sentinel', r'sentinels?'),
            ('Shepherd', r'shepherds?'), ('Steward', r'stewards?'), ('CAP', r'cap'),
            ('Envelope', r'envelopes?'), ('Tier', r'tiers?'), ('Soak', r'soak'),
            ('Delta', r'deltas?'), ('Park', r'park(?:s|ed|ing)?'),
            ('Carry', r'carr(?:y|ies|ied|ying)'), ('Nudge', r'nudges?'), ('Page', r'pages?'),
            ('Digest', r'digests?'), ('Unmeasured', r'unmeasured'), ('Mandate', r'mandates?'),
            ('Trust surface', r'trust surfaces?'), ('Host terminal', r'host terminals?'))


def _prose(text):
    """text with fenced and inline code, HTML tags and link targets blanked; offsets kept."""
    return re.sub(r'```.*?```|`[^`\n]*`|<[^>]+>|(?<=\])\([^)]*\)',
                  lambda m: ' ' * len(m[0]), text, flags=re.S)
```

Anchor rule (GitHub, kramdown and MkDocs agree): `term.lower().replace(' ', '-')`.

Tests (names matter for the `-k` filters in spec.md):

- `test_concepts_opens_with_the_glossary`: `section = page.split('\n## ', 2)[1]`; assert it
  starts with `Glossary\n`; `re.findall(r'^### (.+)\n\n((?:.+\n)+)', section, re.M)` gives
  the entries; their titles equal the `GLOSSARY` titles in order; each body has at most two
  lines.
- `test_glossary_words_link_at_first_use`: for `README.md`, `SITE / 'index.md'`,
  `SITE / 'daily.md'`: find the first `rf'\b{pattern}\b'` match (re.I) in `_prose(text)`;
  if there is one, it must lie inside a `\[([^\]]*)\]\(([^)]*)\)` match of `text` whose
  target ends with `concepts.html#<anchor>` or `concepts.md#<anchor>`
  (`re.search(rf'concepts\.(?:html|md)#{anchor}$', target)`). Fail message: page, term and
  40 characters around the match.
- `test_interview_options_lead_with_plain_words`: import `wuwei.interview`; words are the
  `GLOSSARY` patterns plus `re.escape` of `('floor', 'control plane', 'control-plane',
  'deploy.deny', 'one-way')`; for each row, check `header`, `question` and every choice
  description: the text before the first `(` has no `rf'\b{word}\b'` match (re.I). Also
  assert the gates Light description starts with
  `Small low-risk changes get one reviewer agent` and the Standard and Full descriptions
  contain `three reviewer agents`.
- `test_daily_shows_a_clean_first_day`: section 2 of `daily.md`
  (`split('\n## 2. ', 1)[1].split('\n## ', 1)[0]`) has a ```` ```text ```` block containing
  each of `SETUP_OUTPUT = ('plugin integrity: clean', 'Interview answers:',
  'Applied the setup and recorded .wuwei/calibration.json', 'Still owed:',
  'Next: /wuwei plan')`; section 3 likewise contains each of `('goals: 1 goal saved (G-1)',
  'planned 1/1', 'planned item(s) queued')`. Drift check: each of `('plugin integrity: clean',
  'Interview answers:', 'and recorded .wuwei/calibration.json', 'Still owed:',
  'Next: /wuwei plan', 'planned item(s) queued')` occurs in the joined text of
  `ROOT.glob('cli/wuwei/**/*.py')` (sources today: `commands/init.py:127`,
  `commands/config.py:177,210`, `commands/setup.py:263`, `commands/next.py:87`), so a later
  change to those lines fails here and the builder of that change updates daily.md.

### 2. `tests/test_owner_edits.py`

- New in-process test `test_goals_and_voice_edit_say_what_they_saved(tmp_path, monkeypatch,
  capsys)`: `workspace(tmp_path)`, `monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))`,
  call `wuwei.__main__.main([...])`:
  goals file with `target: 2` -> `0` and stdout `goals: 1 goal saved (G-1)\n`; same file
  again -> `goals: 1 goal unchanged (G-1)\n`; a voice file `## internal\n- max_length: 90\n`
  -> `voice: saved\n`.
- Extend `test_invalid_goals_leave_history_and_target_unchanged`: `assert result.stdout == ''`.

### 3. `cli/wuwei/commands/_owner_edit.py` (F25)

In `run`, replace

```python
        promotion.owner_edit(root, name, text)
        return CLEAN
```

with the result kept and one line printed:

```python
        saved = 'saved' if promotion.owner_edit(root, name, text) else 'unchanged'
        if name == 'goals':
            from wuwei.goals import parse
            ids = list(parse(text))
            print(f"goals: {len(ids)} goal{'s' * (len(ids) != 1)} {saved} ({', '.join(ids)})")
        else:
            print(f'voice: {saved}')
        return CLEAN
```

`owner_edit` already returns `True` when it wrote and `False` when nothing changed
(`promotion.py:13-41`) and already validated `text` with the same `parse`, so the second
parse cannot raise. Nothing else in the command changes.

### 4. `cli/wuwei/interview.py` (strings only)

Do not change any label, id, scope, `free` entry or effect dict. Change these strings:

| Row | Field | New text |
|---|---|---|
| (module) | `SOAK` | `'only where the repository declares merge_deploys = false'` |
| merge | question | `'Who merges pull requests in {repo}?'` |
| merge | Owner merges | `'You merge every pull request yourself.'` |
| merge | Auto, 30 min soak | `f'WUWEI merges once checks and reviews pass, 30 minutes after the last push or approval (soak); {SOAK}.'` |
| merge | Auto, 2 hour soak | same with `2 hours` |
| gates | header | `'Reviewers'` |
| gates | question | `'How many reviewer agents check each change in {repo}? (gate floor)'` |
| gates | Standard | `'Every change gets three reviewer agents: architecture, quality and security (standard floor).'` |
| gates | Full | `'Every change gets three reviewer agents and is recorded at the highest level (full floor).'` |
| gates | Light | `'Small low-risk changes get one reviewer agent, the rest three (light floor).'` |
| interrupt | Batch | `'Collect decisions that can wait and send them every two hours (digest).'` |
| interrupt | At once | `'Ask each decision that cannot be undone as soon as it is ready (one-way door).'` |
| interrupt | Morning only | `'Hold decisions that block nothing until the next morning plan (morning gate).'` |
| phone | question | `'What may messages to your phone say about a decision? (control plane)'` |
| avoid | Defaults only | `'Only the built-in list of words to avoid (voice profile).'` |
| signature | First name | `'Messages end with your first name (owner.name).'` |
| risk | question | `'Which other areas need extra care: three reviewers and your merge? (trust surface)'` |
| risk | Lead defaults | `'Only the built-in areas: auth, credentials, input parsing, scoping and permissions (lead charter).'` |
| manual | Deployment ban only | `'Only deploy commands, which agents never run (deploy.deny).'` |
| manual | Package publishing | `'Agents also never run npm publish, twine upload, cargo publish or gem push (deploy.deny).'` |
| posture | Observe | `'Records what it would refuse and lets the call through; records and owner-only actions still refuse. For a first week or a sandbox (observe posture).'` |
| posture | Guarded | `'Refuses changes to records, publishing and a changed plugin; warns on agents, outgoing text and MCP tools. For a real project (guarded posture).'` |
| posture | Strict | `'Refuses everything a guard would refuse. For a repository that deploys or shares credentials (strict posture).'` |

Everything else in the table already passes the check (verify with the new test). Gate
facts behind the gates texts: `dispatch.py:87-89` (effective tier is the higher of computed
and floor), `dispatch.py:98` (light runs `quality` only, the others `arch`, `quality`,
`security`). Trust surface facts: `charters/lead.md:14`, design 5.2 eligibility (a flagged
item never auto-merges) and `dispatch.py:52-54` (a flag raises the tier to standard).

### 5. `docs/site/concepts.md`

Insert after `[Home](index.html)` and before `## Roles`:

```markdown
## Glossary

The words the rest of these pages use, two lines each.

### Seat

One agent session with one job and its charter: the lead, a builder, a gate reviewer, the shepherd or the steward.
The planner starts seats as the day needs them; each stops when its job is done.

### Gate

A review of a change by an agent that did not write it: architecture, quality or security.
The morning gate is different: your approval of the day's plan before anything starts.

### Sentinel

The four reviewing roles: goal, architecture, quality and security.
Architecture, quality and security run as the gates on each change; the goal sentinel checks work against its goal.

### Shepherd

The seat that takes a pull request from raised to merged: reviewers, replies and CI fixes.
It merges only through the merge policy and never approves a pull request.

### Steward

The seat that watches the day for drift and loops, and compiles the retro at close.
It proposes rule changes; you promote the ones you want.

### CAP

How many build seats may run at once (`cap`, default 1).
The morning gate asks you to confirm it each day.

### Envelope

The day's working window: start time, end time and net build hours.
Work admitted during the day must fit the remaining build hours.

### Tier

Review tier: light (one reviewer agent) or standard and full (three), set per change from its size and risk.
Outbound tier: a message sent as you either goes out at once or waits as a draft for your approval.

### Soak

The wait after the last push or approval before WUWEI merges by itself (`merge.soak_minutes`, default 30).
During it you can stop the merge from your phone.

### Delta

The second review after a fix round: only the gates that asked for the fix look again.
After it the pull request is raised, or the item comes to you.

### Park

Stop work on an item for now, with a decision record that says why.
Close accepts a parked item once that decision is recorded.

### Carry

Move an unfinished item to tomorrow's plan, with a decision record that says so.
The next morning gate offers it again as carry-over.

### Nudge

A reminder that something needs you, but not right now: on the status line and in `bin/wuwei nudges`.
Nudges wait for you; pages interrupt.

### Page

An alert that interrupts you at once, even outside your working hours, for example a failed heartbeat probe.
It shows on the status line and reaches your phone.

### Digest

The 12-character code a host terminal command shows before it changes a file; type it to confirm.
Also the summary of waiting decisions sent every two hours when you choose Batch in the interview.

### Unmeasured

A check that could not run or could not read its source; WUWEI reports it and never counts it as clean.
On a first day some sources are unmeasured until you set them up, for example `meeting unmeasured`.

### Mandate

The block at the end of every seat brief: what the seat decides alone, what it decides and records, and what goes to you.
Seats do not ask you what their mandate lets them decide.

### Trust surface

Code where a mistake costs most: auth, credentials, input parsing, permissions, and the areas you add in the interview.
A change there gets three reviewer agents and is never merged without you.

### Host terminal

A terminal you type in yourself, outside Claude Code's agent tools.
Owner commands such as `bin/wuwei config set` refuse to run anywhere else.
```

Check each sentence against the code once more while writing; fix the text, not the test,
if a fact is off. Humanizer pass on the whole block.

### 6. `README.md`, `docs/site/index.md`, `docs/site/daily.md` (first-use links)

Run the new link test; for each failure either link the first prose use
(`[host terminal](docs/site/concepts.md#host-terminal)` in the README,
`[digest](concepts.html#digest)` on site pages) or reword a generic use that comes first.
Known generic first uses to reword (prototype run on main):

- README: `Releases carry a signed manifest` (verb, line 63) -> `Releases include ...`.
- index: `the linked pages describe the CLI` (line 60) -> `the other links describe ...`.
- daily: `Every command on this page is daily use` and `on the [recovery](recovery.html)
  page` (lines 10-11) -> `Every command here ...` and `... is on [recovery](recovery.html).`

Expected first uses to link on main (the prototype's list; recheck after the edits above):
README `morning gate` (30), `Review tiers` (32), `digest` (36), `planner seat` (53, a table
cell), `shepherd`, `steward`, `four sentinels` (61), `host terminal` (96); index `review
tiers` (13), `host terminal` (41), `digest` (49), `morning gate` (59); daily `host terminal`
(33), `gates` (43), `digest` (65), `approve-tier` (78, outbound tier), `nudge` (79), `seat
policy`, `CAP`, `envelope` (88), `carry-over` (89), `Delta` (120), `shepherd` (140), `mandate`
(164), `parks` (169), `page` (166), `unmeasured` (218). Do not touch `daily.md` lines 56-62
(#356 rewrites that paragraph); a term first used there gets its link at a later or earlier
use only if the test still passes, otherwise link it there.

### 7. `docs/site/daily.md` (clean output)

End of section 2 (after the paragraph that ends `[Configuration](configuration.html) lists
every key.`), add a short lead-in and this block, built from a real run (re-capture it on
your worktree before pasting; see "Capturing the output" below):

```text
Created <project>/.wuwei
{"statusLine": {"type": "command", "command": "<plugin>/bin/wuwei status --line"}}
Status line: put the "statusLine" key above in .claude/settings.json (this project) or ~/.claude/settings.json (every project).
Recommended publishing layout (design 4.5, 9.1):
  ...
Verify with: wuwei config check
plugin integrity: clean
Host: <platform>
claude: on PATH
gh: on PATH
ziran: missing
code host auth: set
free memory: <n> MiB

Merges: Who merges pull requests in acme/widget?
  1. Owner merges: You merge every pull request yourself.
  ...
> 1
...
--- config.toml
+++ config.toml (proposed)
...
+[[repos]]
+name = "acme/widget"
+path = "widget"
+default_branch = "main"
...
Interview answers:
- merge (acme/widget): Owner merges -> repos.0.merge.auto = false
...
- posture: Observe -> security.posture = "observe"
Approved calibration for .wuwei/calibration.json:
...
Review the setup above. To apply it, type:
<digest>
> <digest>
Applied the setup and recorded .wuwei/calibration.json
Credentials:
  ...
Owner:
  owner.name: not set; the outward lint refuses every outward message except replies in the owner DM
Posture: observe
  ...
Host protections:
  ...
Still owed:
  bin/wuwei config set owner.name '"<your name>"'
  bin/wuwei promote
Next: /wuwei plan
```

Then two sentences: it worked when you see `Applied the setup and recorded
.wuwei/calibration.json` and `Next: /wuwei plan`; `owner.name` and `bin/wuwei promote` under
`Still owed:` are normal on day one, and exit 1 with `missing` rows under `Host protections:`
means setup worked and the branch protections are still to set. It did not work when the
`Applied` line is missing (nothing was written; the reason is on the last line) or when
`Still owed:` lists `bin/wuwei config add-repo` (setup could not read a repository); see
[troubleshooting](recovery.html#troubleshooting). (Build correction: setup returns
`max(config check, mcp check)` after the apply, so exit 2 can follow a successful setup and
is not named as a failure sign. `approve-tier messages` on daily.md was reworded to
`messages that wait for your approval`, so daily.md has no prose use of tier left to link.)

End of section 3, add a lead-in (the planner asks the morning gate as cards; after you
approve it records the goals and the plan; you can run the last two commands yourself) and:

```text
$ wuwei plan propose .wuwei/days/<date>/lead.json
<project>/.wuwei/days/<date>/plan.md
$ wuwei goals edit --file .wuwei/days/<date>/goals.md
goals: 1 goal saved (G-1)
$ wuwei plan approve --items DIV-1 --goals-confirmed
$ bin/wuwei status --line
WUWEI pages 0 | nudges 0 | observe | watch off | planned 1/1 | meeting unmeasured
$ bin/wuwei next
dispatch: 1 planned item(s) queued, 0 of CAP 1 building; create the worktree for DIV-1, then ...
```

Then: it worked when `goals edit` says `saved`, the status line shows `planned 1/1` and
`bin/wuwei next` names the first item; `plan approve` prints nothing when it succeeds, and
`meeting unmeasured` only means no calendar is set up. It did not work when the status line
has no `planned` count after you approved, or a command exits 1 or 2 with a reason; see
[troubleshooting](recovery.html#troubleshooting).

### Capturing the output

Run the flow in-process with the `tests/test_setup.py` fixtures (`project`/`host` style:
one repository `acme/widget` with remote `git@github.com:acme/widget.git`, `ziran` hidden,
`sys.stdin.isatty` true, `interview.ask` returning the first choice of each question,
`Confirm()` for the digest), then `plan template` with one goal and one candidate `DIV-1`,
`plan propose`, `goals edit --file`, `plan approve`, `status --line`, `next` through
`wuwei.__main__.main`. Keep that script outside the repository (a scratch file importing
`tests/test_setup.py`); paste only the text, with every path, digest, date and memory figure
replaced by a `<...>` placeholder. The dev checkout prints a `page: plugin integrity: ...`
line where a signed release prints `plugin integrity: clean`; show the signed-release line.

## What must not change

- Interview labels, ids, scopes, `free` validators, effects, `describe`, `settings`,
  `record`, `widgets` and `ask` code; `tests/test_interview.py` passes unchanged.
- `goals edit` / `voice edit` failure paths, exit codes and stderr; the owner-edit guard.
- Existing headings and anchors on every page (`## Roles`, `## Review tiers`, `## 2. Configure`
  and the rest), the Jekyll front matter, the `[Home](index.html)` lines, `.html` link style.
- `daily.md` lines 56-62 (owned by #356), `configuration.md`, `reference.md`, skills, charters.

## Deferred

- `plan approve` success line, setup's single ready line (#360), one morning-gate question
  (#365): not this issue; their builders refresh the daily.md blocks.
- Glossary links on pages other than README, index and daily.
