# Implementation Plan: Publish notices (SECURITY.md, CONTRIBUTING.md, NOTICE credits)

**Branch**: `307-publish-notices` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

Docs and packaging only. Add `SECURITY.md` and `CONTRIBUTING.md`, extend `NOTICE` with one
entry per borrowed project and concept, add `.specify/LICENSE` (spec-kit MIT text), end
`README.md` with `## Acknowledgements`, add `SECURITY.md` to the two release file lists, and
pin it all with tests in `tests/test_docs.py`. Licence facts and URLs are in
[research.md](research.md).

## Technical Context

- Python 3.11+, pytest dev-only. No runtime change: nothing under `cli/` or `adapters/`.
- Tests: `python -m pytest -q` from the repository root. The release-asset test already
  builds the asset in-process with a fake signer; reuse it, do not build a second time.

## Constitution Check

- I (stdlib only): no runtime code. Pass.
- III (one behaviour, one test): each new file is pinned by one test; the manifest
  assertion joins the existing release-asset test. Pass.
- IV (test first): every task pair below is test then change. Pass.
- V (ponytail): no NOTICE parser, no data file of credits, no helper. The README check is a
  regex over two strings. Pass.
- Constraints: no emojis, no em-dashes, no absolute paths in any new file. Pass by test.

## Changes

### `scripts/build-release.py` (line 18)

Add `'SECURITY.md'` to the root file tuple:
`for name in ('README.md', 'LICENSE', 'NOTICE', 'SECURITY.md', 'pyproject.toml'):`.
`integrity.write_manifest` inventories the stage, so `MANIFEST.sha256` picks it up with no
other change.

### `scripts/headless_e2e.py` (line 148)

Add `'SECURITY.md'` to the copied root files so the scratch source the rehearsal builds from
still has every file `build-release.py` copies. Without it `prepare()` raises
`FileNotFoundError` and `test_scratch_build_and_observer_preserve_hook_results` fails.
Do not merge the two lists into a shared constant (out of scope; they already differ for
`docs`).

### `SECURITY.md` (new, root)

Short sections, plain prose:

1. `# Security policy`
2. `## Supported versions`: only the latest release receives fixes; upgrade first.
3. `## What counts`: the four in-scope classes from the spec (guard bypass reachable through
   the normal tools by a cooperating agent or an injected instruction; a forgeable record a
   guard, sweep or policy trusts; a manifest or integrity bypass; a credential leaked into a
   seat environment or an event).
4. `## What does not count`: in design spec 9.1 words. The guards are cooperative mistake
   prevention and never an isolation boundary; a determined process running as the owner's
   user with a shell can forge any local file and is out of scope; the hard boundaries are
   the code host's protected refs, required checks, required reviews and publication
   credentials kept out of seat environments. Link `docs/site/security.md` and the design
   spec section 9.1 (`docs/specs/2026-09-24-wuwei-design.md`).
5. `## How to report`: GitHub private vulnerability reporting (the repository's Security
   tab, "Report a vulnerability"); never a public issue, PR or discussion. Include: WUWEI
   version, OS and Python version, the guard or command, the exact tool input, expected and
   actual exit code, and whether it needs a cooperating agent, an injected instruction or
   neither.
6. `## What to expect`: an acknowledgement, an assessment against the scope above, a fix in a
   release with a published advisory, and credit in the advisory if the reporter wants it.
   No response-time promise (single maintainer; see Assumptions).

No email address anywhere. Relative links are fine: `docs/` ships in the asset.

### `CONTRIBUTING.md` (new, root)

Under about 40 lines. Points at `AGENTS.md` and `.specify/memory/constitution.md` for the
rules instead of repeating them, then the essentials: one issue is one spec-kit feature
(`specify`, `plan`, `tasks`, `implement`, skills in `.agents/skills/`); test first; stdlib-only
runtime and pytest dev-only; the review bar (suite green, an adversarial review covering
correctness, security and over-engineering with no open blocking findings, conventional
commits); no emojis and no em-dashes; run `python3 -m pytest -q`; regenerate the hero with
`python3 scripts/build-hero.py` after changing it and commit both SVGs; vulnerabilities go
through `SECURITY.md`, not issues. Avoid phrasing that `calibrate.INSTRUCTION_LIKE`
(`cli/wuwei/calibrate.py` line 32) flags.

### `.specify/LICENSE` (new)

The upstream spec-kit `LICENSE` verbatim (MIT, `Copyright GitHub, Inc.`), fetched from
`https://github.com/github/spec-kit/blob/main/LICENSE`. Byte-for-byte except a trailing
newline.

### `NOTICE`

Keep lines 1 to 4. Then, in plain text (Apache NOTICE convention, no Markdown):

```
This product includes or builds on the work below.

Third-party code

GitHub Spec Kit
  Source: https://github.com/github/spec-kit
  Licence: MIT, Copyright GitHub, Inc. Full text in .specify/LICENSE.
  Used: the vendored .specify/ templates and scripts (spec-kit 1.0.13.dev0) and
  .agents/skills/speckit-*, the development workflow for this repository.

Projects whose ideas or tools WUWEI uses (no code copied)

<Name>
  Source: <url>
  Licence: <licence, copyright line where the licence has one>
  Used: <what was taken, with the design spec section>
...

Concepts (credited by author and source)

<Name>
  Source: <url>
  Author: <author, work>
  Used: <where>
```

Entries and their facts come from research.md, in its row order. An entry the builder
cannot confirm on the day reads `Licence: credit, licence not verified`. Every `https://`
URL in NOTICE is a Source URL; no licence-file URLs (those go in the PR body).

### `README.md`

Append after line 161 a final `## Acknowledgements` section: one sentence saying WUWEI builds
on the work below and that `NOTICE` has the licences, then one bullet per NOTICE entry, same
order, as `[Name](<same Source URL>): what WUWEI took (licence).` Concepts in the same list
after the projects. Optionally add to the Development section one line: contributing guide
at `https://github.com/taoq-ai/wuwei/blob/main/CONTRIBUTING.md` and security reports per
[SECURITY.md](SECURITY.md). No relative link to `CONTRIBUTING.md` (not shipped; see spec
Problem 6).

### `tests/test_docs.py`

Three new tests and one added assertion. Module constants and imports already exist
(`ROOT`, `re`, `integrity`).

1. `test_security_policy_scope_and_channel`: reads `SECURITY.md`, flattens whitespace, and
   asserts the phrases `cooperative mistake prevention`, `isolation boundary`,
   `a determined process running as the owner's user with a shell`,
   `private vulnerability reporting`, `latest release`, `docs/site/security.md`, and the four
   in-scope markers (`injected instruction`, `forge`, `manifest`, `credential`); asserts no
   `@` email pattern (`re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)` is None).
2. `test_contributing_points_at_the_rules`: reads `CONTRIBUTING.md`; asserts `AGENTS.md`,
   `.specify/memory/constitution.md`, `python3 -m pytest -q`, `scripts/build-hero.py`,
   `SECURITY.md`, `test first` (case-insensitive) and `stdlib`; asserts
   `calibrate.instruction_like(text) == []` (import from `wuwei`).
3. `test_notice_credits_match_readme_acknowledgements`: reads `NOTICE` and `README.md`;
   `section = readme.split('\n## Acknowledgements\n', 1)[1]` (assert the split finds it) and
   assert `'\n## ' not in section` (it is the last section); `urls = re.findall(r'https://[^\s)]+', notice)`;
   `missing = [u for u in urls if u not in section]`; `assert urls and not missing, missing`.
   Also assert the spec-kit lines: `.specify/LICENSE` contains `Copyright GitHub, Inc.` and
   `Permission is hereby granted`, and NOTICE contains `.specify/`, `.agents/skills/speckit-`
   and `.specify/LICENSE`. Also assert each of the names `Spec Kit`, `autoharness`,
   `ralph-starter`, `humanizer`, `Model Context Protocol`, `MCP Apps`, `release-please`,
   `ZIRAN`, `WSJF`, `RICE`, `two-way door` appears in NOTICE (case-insensitive).
   Hygiene: for `SECURITY.md`, `CONTRIBUTING.md`, `NOTICE` and `.specify/LICENSE`, assert no
   `\N{EM DASH}` and no emoji (no character with `ord(c) >= 0x1F000`).
4. In `test_release_asset_ships_every_linked_doc` (line 366), add
   `assert {'LICENSE', 'NOTICE', 'SECURITY.md'} <= listed`.

Absolute paths are already covered by `tests/test_hygiene.py::test_tracked_text_has_no_machine_paths`
once the files are tracked; no new check.

## What must not change

- Nothing under `cli/`, `adapters/`, `hooks/`, `charters/`, `agents/`, `templates/`.
- `LICENSE` (Apache-2.0) and NOTICE lines 1 to 4.
- The existing README sections and their text (tests at `tests/test_docs.py` lines 24, 39,
  127 and 452 pin them); only the new section is appended.
- The vendored spec-kit files themselves; only `.specify/LICENSE` is added.
- `docs/site/security.md`: SECURITY.md links it rather than duplicating it, so
  `test_guard_boundaries_are_stated_once` is unaffected.
- No GitHub settings change, no `gh` call. Private vulnerability reporting is enabled by the
  owner.

## PR body

List each research.md "Checked at" URL with the licence found, plus the date checked.
