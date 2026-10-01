# Implementation Plan: Docs sweep (#294)

**Branch**: `294-docs-sweep` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

A docs-only sweep with two lasting tests. The tests read the real sources (the `--help`
output, the template and `workspace.SCHEMA`), so they live in `tests/test_docs.py` next to
the existing key coverage test and reuse its header regex. The pages get the smallest edits
that make the new assertions pass and the pages agree: one `## Commands` table in
`reference.md`, one section map in `configuration.md`, one `## What ships today` list in the
README, short new sections in `concepts.md`, one or two sentences each elsewhere, and four
additions to the hero generator. No runtime code and no template change.

## Technical Context

- Python 3.11+, pytest dev-only. Run `python -m pytest -q` from the repository root with the
  interpreter the task names (the system `python3` here has no pytest).
- Docs are GitHub Pages markdown under `docs/site/` (kramdown ids: `## Review tiers` is
  `#review-tiers`) and the README rendered on GitHub (same id rule).
- The hero is generated: edit `scripts/build-hero.py`, run `python3 scripts/build-hero.py`,
  keep both SVGs in the diff. `test_hero_files_match_their_generator` pins them.

## Constitution Check

- I stdlib only: no runtime change. Pass.
- III one behaviour, one test: each new assertion group is one test function. Pass.
- IV test first: every page change has a failing test task before it (tasks.md). Pass.
- V ponytail: reuse the key test's regex, no new helper module, no template change, no
  generated docs. Pass.
- Constraints: no em-dashes, no emojis, no absolute paths in pages or tests. Pass.

## Changes

### `tests/test_docs.py` (tests first)

Add `import os, subprocess, sys`. New tests, each small:

1. `test_reference_lists_every_cli_command(tmp_path)`: run
   `[sys.executable, '-P', '-m', 'wuwei', '--help']` with
   `env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')}`, `cwd=tmp_path` (the pattern in
   `tests/test_dashboard.py` line 17); assert exit 0; commands are
   `re.search(r'\{([a-z,-]+)\}', stdout)[1].split(',')`. Section is
   `reference.split('\n## Commands\n', 1)[1].split('\n## ', 1)[0]`; listed is
   `re.findall(r'^\| `bin/wuwei ([a-z-]+)`', section, re.M)`. Assert
   `set(listed) == set(commands)` with the message `(missing, extra)`.
2. `test_configuration_names_every_config_section`: template sections with the same regex as
   `test_every_template_config_key_is_documented` (`^\s*#?\s*\[\[?([\w.]+)\]\]?\s*$`), plus
   `{name for name, rule in workspace.SCHEMA.items() if isinstance(rule, (dict, list))}`.
   Missing is each name for which neither `` `[name]` `` nor `` `[[name]]` `` is in
   `configuration.md`; assert `not missing, missing`. Hoist the header regex to a module
   constant `TABLE = re.compile(...)` and use it in both tests (the only refactor).
3. `test_site_pages_and_links`: replace the hard-coded `pages` tuple with
   `sorted(p.stem for p in SITE.glob('*.md') if p.stem != 'index')`; keep every other
   assertion.
4. `test_readme_first_day_and_shipped_areas`: for README the `## Quick start` section and for
   `index.md` the `## Start here` section, assert the order
   `init .` < `bin/wuwei calibrate` < `calibrate --interview` < `/wuwei plan`, and that
   `config promote` is in both. README section `## What ships today` sits between
   `## What WUWEI is and is not` and `## How WUWEI compares` and contains each link:
   `docs/site/daily.md`, `docs/site/security.md`, `docs/site/concepts.md#review-tiers`,
   `docs/site/remote.md`, `docs/site/concepts.md#cockpit-and-board`,
   `docs/site/configuration.md#calibration`, `docs/site/reference.md#heartbeat`,
   `docs/specs/2026-09-24-wuwei-design.md`.
5. `test_cruise_mode_is_designed_not_built`: for README and every `docs/site/*.md`, split
   into paragraphs on blank lines; every paragraph matching `cruise` (case-insensitive),
   except a heading line such as `## Decision classes and cruise levels`, has
   `not built` in its whitespace-flattened text. Also assert `cruise` appears in the README
   ships section, in `concepts.md` and in `configuration.md` (so the test is not vacuous).
6. `test_concepts_and_daily_cover_shipped_mechanisms`: `concepts.md` has the headings
   `## Review tiers`, `## Decision classes and cruise levels`, `## Sessions`,
   `## Listener`, `## Heartbeat`, `## Cockpit and board`; `daily.md` step 3 (the text
   between `3. Gates:` and `4. Fix round:`) contains `` `tier` ``, and section 5 contains
   `phone answers`.
7. `test_security_integrity_and_cross_links`: `security.md` and `docs/integrity.md` each
   contain `plugin.json` and `mcp check`; `recovery.md` contains `(rehearsal.html)` and
   `rehearsal.md` contains `(recovery.html)`.
8. `test_shipped_things_are_not_called_planned`: a table of `(path, stale phrase)`:
   `configuration.md` `MCP scanning (#35)` and `Planned planner rotation`;
   `reference.md` `will set \`remote\``; `charter-overrides.md` `**Planned:**`; `README.md`
   `interactive day planner`. Assert each phrase is absent.
9. `test_hero_shows_the_current_day`: for both SVGs, the words `Calibrate`, `interview`,
   `tier`, `Phone`, `DM`, `heartbeat` are in the file; `len(read_bytes()) < 20000`; the
   `<desc>` text and the README `alt` attribute contain (case-insensitive) `calibrat`,
   `tier`, `phone`, `heartbeat`; every class used in a `class="..."` attribute, except the
   modifier `slow`, appears as `.<class>` inside the
   `@media (prefers-reduced-motion:reduce){...}` rule.

Existing tests stay as they are; they already pin the phrases this sweep must keep
(`test_readme_compares_with_other_tools`, `test_entry_guides_install_signed_release...`,
`test_guard_boundaries_are_stated_once`, `test_calibration_is_documented_between_configure_and_plan`,
`test_release_asset_ships_every_linked_doc`).

### `docs/site/reference.md`

Insert `## Commands` right after the opening paragraph (before `## Lead plan JSON`): one
sentence ("Every command `bin/wuwei --help` prints; `bin/wuwei <command> --help` shows its
options."), then a table `| Command | What it does | More |` with one row per command in
help order, `` `bin/wuwei <command>` `` spelled as the help spells it (`fast-checks`,
`git-hook`). "What it does" is the help line, made into a sentence. "More" links the section
that already describes it where one exists, for example `calibrate` to
`configuration.html#calibration`, `listen` and `remote` to `remote.html`, `heartbeat` to
`#heartbeat`, `sessions` to `#sessions`, `board` and `dashboard` to
`concepts.html#cockpit-and-board`, `state` to `recovery.html`, `hook` to
`#hook-latency-budget`. Internal plumbing commands (`hook`, `git-hook`, `payload`, `event`)
say they are called by hooks or seats, not by the owner.

Line 128: replace "Only `planner` and `adhoc` are set today: the control plane (#65) will
set `remote`, and nothing sets `seat-host` yet." with "Only `planner` and `adhoc` are set
today; nothing sets `remote` or `seat-host` yet."

### `docs/site/configuration.md`

- After the opening paragraph, add `## Sections`: a short table `| Section | Keys under |`
  naming every section as `` `[name]` `` (array of tables as `` `[[repos]]` ``), grouped
  per row by the heading that documents them, each row linking that heading:
  `[[repos]]`, `[repos.merge]`, `[repos.gates]`, `[prioritisation]`, `[discovery]`,
  `[tracker]`, `[tracker.states]`, `[security]` to Workspace and repositories; `[owner]`,
  `[host]`, `[build]`, `[memory]`, `[retro]`, `[metrics]`, `[consolidation]`, `[codex]`,
  `[watch]`, `[sessions]`, `[listen]`, `[responder]`, `[steward]`, `[pr]`, `[shepherd]`,
  `[shepherd.authors]` to Host, build and memory (check each key's actual heading and link
  where its table rows are); `[adapters]`, `[chat]`, `[control_plane]`, `[scanner]`,
  `[scanner.mcp]`, `[calendar]`, `[brief]`, `[brief.style]` to Adapters and brief; `[voice]`,
  `[voice.sources]` to Owner voice; `[boundary]`, `[environments]`, `[deploy]` to
  Boundaries and deployment; `[outward]`, `[outward.max_length]`, `[outbound]` to Outward
  text and outbound tiers. One last row: `[decisions.cruise]`, cruise mode, "designed in
  design spec 5.8.1, not built; `bin/wuwei config check` refuses it today as an unknown
  key". Do not insert a heading between `## Calibration` and `## Owner interview`.
- Lines 170 to 171: delete "MCP scanning (#35) and role audits (#36) remain deferred." and
  point to `### MCP registry checks (S3)` and `security.html#s1-reviewed-role-grants-in-ci`
  instead, or just delete the sentence.
- Line 93: "Planned planner rotation, off by default." becomes "Scheduled planner rotation,
  off by default."

### `docs/site/concepts.md`

Six short sections in the page's voice, two to five sentences each, each linking the page
with the detail:

- `## Review tiers`: `dispatch next` computes LIGHT, STANDARD or FULL at an item's first gate
  from the diff, flags, track, `repos.gates.floor` and an optional lead `tier`; LIGHT runs the
  quality sentinel only, STANDARD and FULL run arch, quality and security; a lower lead tier
  is refused and recorded; the action carries `tier`. Link `configuration.html` (repos.gates)
  and `reference.html`.
- `## Decision classes and cruise levels`: designed in design spec 5.8.1 (#282), not built
  (#283): decisions would carry a class and the CLI would answer some at levels L0 to L3.
  Today every owner decision goes to the owner. Link the design spec on GitHub the way the
  page already links it (`https://github.com/taoq-ai/wuwei/blob/main/docs/specs/...`).
- `## Sessions`: the registry from hooks, roles, claims, stale, take-over and rotation.
  Link `reference.html#sessions` and `daily.html#long-sessions`.
- `## Listener`: `bin/wuwei listen` polls the inbound source into the inbox, the responder
  wakes the planner, commands only from the pinned owner with a second factor where needed.
  Link `remote.html` and `configuration.html#running-the-listener`.
- `## Heartbeat`: the watch runs fixed probes each tick, health on the status line, one page,
  behaviour drift, dead-man ping. Link `reference.html#heartbeat`.
- `## Cockpit and board`: `bin/wuwei dashboard` serves the read-only day board on loopback;
  the plugin's MCP server runs `bin/wuwei board` and offers the `wuwei_board` tool, declared
  in the signed `plugin.json`. Link `daily.html#6-close`.

### `docs/site/daily.md`

- Step 4.3: one sentence: at the first gate `dispatch next` also returns the item's `tier`;
  LIGHT asks for the quality gate only, STANDARD and FULL for all three.
- Section 5: one or two sentences: a decision answered in the Slack DM is recorded as
  evidence, `status --line` counts it as `phone answers 1`, and `bin/wuwei decision outcome`
  in a host terminal records it.

### `docs/site/index.md`

- The page list stays complete; refresh descriptions: reference ("every CLI command, JSON,
  decisions, heartbeat, sessions and hook latency budget", keep the words `latency budget`),
  configuration ("every section and key"), concepts (add tiers, sessions, listener,
  heartbeat).
- "Start here": between `init .` and `/wuwei plan`, add `bin/wuwei calibrate` with
  `bin/wuwei config promote` and `bin/wuwei promote`, then `bin/wuwei calibrate --interview`
  in a host terminal, linking `daily.html`.

### `docs/site/security.md`, `docs/integrity.md`

- `security.md`, ZIRAN integration paragraph: one sentence: the plugin's own board MCP
  server is declared in the signed `.claude-plugin/plugin.json`, so integrity covers it and
  the registry gate (`bin/wuwei mcp check`) reports it as covered; every other server,
  including one declared inline in another plugin's `plugin.json`, is measured.
- `docs/integrity.md`: one sentence where the manifest scope is described: the manifest
  covers `.claude-plugin/plugin.json` and with it the board server it declares; `bin/wuwei
  mcp check` therefore does not scan that server.

### `docs/site/recovery.md`, `docs/site/rehearsal.md`, `docs/site/charter-overrides.md`

- `recovery.md`: one line under the intro: before a release, the
  [release rehearsal](rehearsal.html) drives a real day; its failures point back here.
- `rehearsal.md`: one line: when a run leaves state and evidence disagreeing, see
  [recovery](recovery.html).
- `charter-overrides.md` line 15: replace the `**Planned:**` line with the shipped fact: the
  steward runs at sweeps, at close and every `steward.every_tool_calls` tool calls through
  `/wuwei plan`, and its proposals land through `bin/wuwei promote` like any other.

### `README.md`

- `alt` text (line 5): add the calibrate station, the tier on the gates, the phone and the
  heartbeat.
- "What WUWEI is and is not" line 21: drop "The current release includes the CLI, role
  charters and interactive day planner."; the next section says what ships.
- New `## What ships today` after it: one bullet per area, one link each (the links in test
  4), plus one sentence: "Designed, not built: cruise mode, graduated autonomy per decision
  class (design spec 5.8.1)." linking `docs/specs/2026-09-24-wuwei-design.md`. Only link
  files that ship in the release asset (`docs/`, `skills/`, ...); never `specs/`.
- Comparison: WUWEI row gains "risk-tiered gates" in its unit-of-work or enforcement cell
  only if it fits the row; "Where WUWEI is worse" hooks bullet becomes "Hooks add 40 to 100 ms
  per tool call depending on hardware (40 to 50 ms CPU p95 on an M-series Mac)". Keep the
  section under 70 lines and every phrase `test_readme_compares_with_other_tools` pins.
- Quick start: after `init`, add calibrate (`bin/wuwei calibrate`, read the report,
  `bin/wuwei config promote` and `bin/wuwei promote` in a host terminal), then
  `bin/wuwei calibrate --interview` in a host terminal, then `/wuwei plan`.

### `scripts/build-hero.py` and `docs/assets/hero-{dark,light}.svg`

Add, do not move. Existing nodes, paths, `Tok` timelines, palette, viewBox and ids stay.
Suggested anchors below were checked against the current geometry; render both SVGs (open
them in a browser) and nudge only the new elements until no label overlaps a node, label or
path.

1. Calibrate station: a pill node (`Calibrate`, about 124 by 40, `panel` fill, `accent`
   stroke) centred on the memory path where it approaches Plan, at about `bez(*mem, 0.85)`
   (near (266, 463)); the memory token passes behind it like the main nodes. An owner link
   in `links` (warm dashed, from the owner's lower left to the pill's right edge) labelled
   `interview`, label near (430, 490), and a `pulse` on the `MEM` timeline shortly before it
   reaches the pill (for example `MEM.t * 0.8`; `window` asserts keep it inside the cycle).
2. Tier on the gate markers: a muted caption under the bottom marker, about
   `(GX, R[1] + LANE + 30)`, reading `tier: one gate or three`. Token A already takes the
   middle lane alone (LIGHT) and token B fans to three (STANDARD/FULL).
3. Phone: a pill node `Phone` (about 96 by 36, `warm` stroke and text, like Owner) above the
   owner near (545, 362), a short warm dashed link to the owner, and a warm dashed link to
   Review labelled with `DM` (for example `answered from the DM`), with a `pulse` on an
   existing token timeline after the owner's decision pulse (for example
   `B_.events['review'] + 1.2`).
4. Heartbeat: a second ring rect with class `beat` and a CSS keyframe giving a short double
   flash once per cycle (for example `.beat{animation:beat 6s ease-out infinite}`), and a
   `heartbeat` label in a second cut in the ring (for example bottom left, like the
   `Guards at action time` cut). Add `.beat` to the reduced-motion rule
   (`.tok,.pulse,.beat{display:none}` or `animation:none`).
5. `<desc>`: add one sentence each for calibrate and the interview, the tier, the phone and
   the heartbeat. Keep the `<title>`.
6. Run `python3 scripts/build-hero.py`; both SVGs change; both stay under 20000 bytes.

## What must not change

- `cli/`, `adapters/`, `templates/workspace/config.toml`, `skills/`, `charters/`.
- Every phrase an existing test pins: the comparison section, the install block order in
  README and `index.md`, the security 9.1 phrases, the calibration and interview headings and
  order in `configuration.md` and `daily.md`, the heartbeat and latency phrases in
  `reference.md`, the remote runbook.
- `docs/site/remote.md` needs no change (it is current and pinned by its own test).
- The hero's existing geometry and token timings, its two palettes, `role="img"`, the
  title and the `Plan`, `Build`, `Review`, `Close` labels.

## Risks

- A README link to `specs/` would fail `test_release_asset_ships_every_linked_doc`
  (release ships `docs/`, not `specs/`).
- `index('/wuwei plan')` on the whole README would hit the new ships section first; the
  order test reads only the quick start section.
- `## Commands` must be one section; a `### ` subheading inside it is fine, a `## ` one ends
  the parse.
