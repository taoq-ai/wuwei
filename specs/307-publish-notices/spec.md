# Feature Specification: Publish notices: SECURITY.md, CONTRIBUTING.md and a NOTICE that credits every project and concept WUWEI borrows from

**Feature Branch**: `307-publish-notices`
**Created**: 2026-10-02
**Status**: Ready
**Input**: GitHub issue #307, "docs(publish): SECURITY.md, CONTRIBUTING.md and a NOTICE that credits every project and concept WUWEI borrows from". Preparation for making the repository public (#42). Depends on none. Owner decisions 2026-10-02: "Add it" (SECURITY.md) and "nice to add the notice to all the projects and concepts we borrow, just to be fair towards others".

## Problem (reproduced)

Reproduced read-only on `main` (b420c12, release 0.10.0) in this worktree. Nothing fails today
because nothing checks for these files.

1. No `SECURITY.md` and no `CONTRIBUTING.md` at the repository root (`ls` reports both
   missing). A guard bypass has no private reporting path, and contributors have no entry
   point besides `AGENTS.md`.
2. `NOTICE` (4 lines) holds only the WUWEI copyright and the Apache-2.0 pointer. It credits
   none of the projects the design spec says WUWEI adapts: autoharness (design spec 6.8),
   ralph-starter (5.3, "Build loop"), the humanizer checklist (`charters/_common-authoring.md`
   lines 17 to 30), or the vendored spec-kit files.
3. The vendored GitHub Spec Kit files (`.specify/` templates and scripts, spec-kit version
   `1.0.13.dev0` per `.specify/init-options.json`, and `.agents/skills/speckit-*`) carry no
   copy of their MIT licence. `find .specify -iname '*licen*'` finds nothing; the skills only
   say `author: "github-spec-kit"` in their frontmatter. MIT requires the copyright and
   permission notice in all copies or substantial portions, so the repository is not
   compliant once public.
4. `README.md` ends at line 161 with the Development section (`See the [design](...) and
   [NOTICE](NOTICE).`); there is no Acknowledgements section.
5. `scripts/build-release.py` line 18 copies `README.md`, `LICENSE`, `NOTICE` and
   `pyproject.toml` into the signed asset; `SECURITY.md` is not shipped. The rehearsal
   builder `scripts/headless_e2e.py` line 148 keeps its own copy of that file list and feeds
   it to the same build, so the two lists must change together or
   `test_scratch_build_and_observer_preserve_hook_results` breaks.
6. `tests/test_docs.py` line 366, `test_release_asset_ships_every_linked_doc`, already fails
   any relative README link whose target is not in `MANIFEST.sha256`; any relative link the
   new README text adds must therefore point at a shipped file.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A researcher can report a guard bypass privately (Priority: P1)

Someone who finds a way past a guard reads `SECURITY.md`, learns whether it counts, and
reports it privately through GitHub instead of opening a public issue.

**Why this priority**: the owner's first condition for going public.

**Independent Test**: a docs test reads `SECURITY.md` and asserts its scope and reporting
phrases.

**Acceptance Scenarios**:

1. Given the repository root, when a reader opens `SECURITY.md`, then it lists what counts:
   a guard bypass a cooperating agent or an injected instruction can reach through the
   normal tools; a forgeable record that a guard, sweep or policy trusts; a manifest or
   integrity bypass; a credential leaked into a seat environment or an event.
2. Given `SECURITY.md`, then it states, in design spec 9.1 wording, that the guards are
   cooperative mistake prevention and never an isolation boundary, and that a determined
   process running as the owner's user with a shell is out of scope, and it links the
   security page for detail.
3. Given `SECURITY.md`, then it names GitHub private vulnerability reporting as the channel,
   says not to open a public issue, lists what to include (version, steps, the guard and the
   input, expected and actual exit), states that only the latest release is supported, and
   says what the reporter can expect (acknowledgement, a fix in a release, credit if wanted).

### User Story 2 - Every borrowed project and concept is credited (Priority: P1)

A reader of `NOTICE` or the README finds each project and idea WUWEI builds on, with name,
link, licence and what was taken.

**Why this priority**: the owner asked for it explicitly, and MIT requires the spec-kit
notice.

**Independent Test**: a docs test compares `NOTICE` against the README Acknowledgements
section and checks the spec-kit licence copy.

**Acceptance Scenarios**:

1. Given the repository root, then `NOTICE` exists and `README.md` ends with an
   `## Acknowledgements` section linking each credited project.
2. Given `NOTICE`, then each third-party entry gives name, source URL, licence (or "credit,
   licence not verified" when it could not be verified) and what WUWEI took, covering:
   GitHub Spec Kit, autoharness, ralph-starter, humanizer (and Wikipedia's "Signs of AI
   writing" it is based on), the Model Context Protocol, MCP Apps, release-please and ZIRAN
   as projects; WSJF, RICE, and one-way and two-way doors as concepts credited by author and
   source.
3. Given the docs test, when a URL in `NOTICE` is missing from the README Acknowledgements
   section, then the test fails naming it.
4. Given the vendored spec-kit directories, then the full upstream MIT licence text with
   `Copyright GitHub, Inc.` is in the repository and `NOTICE` names `.specify/` and
   `.agents/skills/speckit-*` and points at that licence file.

### User Story 3 - A contributor knows the workflow (Priority: P2)

A first-time contributor opens `CONTRIBUTING.md` and finds the per-issue flow and the bar
without re-reading the whole design.

**Why this priority**: useful for the public repository, not a compliance item.

**Independent Test**: a docs test asserts the pointers and commands in `CONTRIBUTING.md`.

**Acceptance Scenarios**:

1. Given `CONTRIBUTING.md`, then it points at `AGENTS.md` and
   `.specify/memory/constitution.md` instead of repeating them, and states briefly: the
   spec-kit flow per issue, test first, stdlib-only runtime, the review bar (tests green and
   an adversarial review with no open blocking findings), no emojis and no em-dashes, how to
   run the suite (`python3 -m pytest -q`) and the hero generator
   (`python3 scripts/build-hero.py`), and that vulnerabilities go through `SECURITY.md`.

### User Story 4 - The signed asset carries the notices (Priority: P1)

**Why this priority**: an installed plugin must carry its licence, notice and reporting
policy (#245 list).

**Independent Test**: the existing release-asset test builds the asset with a fake signer.

**Acceptance Scenarios**:

1. Given the built asset, then `NOTICE`, `SECURITY.md` and `LICENSE` are listed in
   `MANIFEST.sha256`.
2. Given the headless rehearsal scratch build, then it still builds (its file list includes
   `SECURITY.md`).

### User Story 5 - The PR shows its sources (Priority: P2)

**Acceptance Scenarios**:

1. Given the PR body, then it lists the URL checked for each licence (the table in
   `research.md` is the source).

### Edge Cases

- A project whose licence cannot be confirmed from the project itself at build time: the
  NOTICE entry says "credit, licence not verified" and still appears in the README.
- A concept (WSJF, RICE, doors) has no licence: the entry names author and source and
  says "concept, no code or text copied".
- The Model Context Protocol repository is licensed per content type (Apache-2.0 for new
  code, MIT for legacy contributions, CC-BY-4.0 for documentation): the entry says so rather
  than picking one.
- ralph-starter's site names `multivmlabs/ralph-starter` while GitHub serves
  `rubenmarcus/ralph-starter`; the entry uses the URL GitHub serves at build time.
- ZIRAN and WUWEI share an owner; ZIRAN is still credited, as a tool used in CI.
- `CONTRIBUTING.md` is read by `bin/wuwei calibrate` as a convention file in target
  repositories (`cli/wuwei/calibrate.py` line 22); its text must not trip the
  instruction-like patterns at line 32 (no "ignore previous instructions" style phrasing).
- README must not add a relative link to a file the asset does not ship (`CONTRIBUTING.md`
  is not shipped), or `test_release_asset_ships_every_linked_doc` fails.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `SECURITY.md` MUST exist at the root with the in-scope list, the out-of-scope
  statement and the reporting process of User Story 1, using the design spec 9.1 phrases
  "cooperative mistake prevention", "isolation boundary" and "a determined process running
  as the owner's user with a shell", and linking `docs/site/security.md`.
- **FR-002**: `SECURITY.md` MUST name "private vulnerability reporting" as the only channel
  and contain no personal email address.
- **FR-003**: `CONTRIBUTING.md` MUST exist with the content of User Story 3, short, pointing
  at `AGENTS.md` and the constitution.
- **FR-004**: `NOTICE` MUST keep its current WUWEI header and add one entry per credited
  project and concept with name, URL, licence and copyright line where one exists, and what
  was taken; projects first, then concepts.
- **FR-005**: The full upstream GitHub Spec Kit MIT licence text MUST be committed at
  `.specify/LICENSE`, and the NOTICE entry MUST name `.specify/`, `.agents/skills/speckit-*`
  and `.specify/LICENSE`.
- **FR-006**: `README.md` MUST end with `## Acknowledgements`: one line per NOTICE entry
  with the same link, what was taken and the licence, then a sentence pointing at `NOTICE`.
  Every URL in `NOTICE` MUST appear in that section.
- **FR-007**: `scripts/build-release.py` and `scripts/headless_e2e.py` MUST add
  `SECURITY.md` to their root file lists; `LICENSE` and `NOTICE` stay.
- **FR-008**: Tests in `tests/test_docs.py` MUST pin FR-001 to FR-007; the NOTICE-to-README
  check MUST fail naming each NOTICE URL missing from the README section.
- **FR-009**: No new file may contain an em-dash, an emoji or an absolute local path.
- **FR-010**: No runtime code under `cli/` or `adapters/` changes. GitHub settings (private
  vulnerability reporting, branch protection) are not changed by this feature.

### Key Entities

- **NOTICE entry**: name, URL, licence or "licence not verified" or "concept", copyright line
  when the licence has one, what WUWEI took and where it lives.
- **Acknowledgements section**: the README's last `##` section, mirroring the NOTICE entries.

## Success Criteria *(mandatory)*

- **SC-001**: `python3 -m pytest -q` passes with the new docs tests, and each new test fails
  on `main` before the change.
- **SC-002**: Removing any one URL from the README Acknowledgements section makes the docs
  test fail with that URL in the message.
- **SC-003**: The built asset's `MANIFEST.sha256` lists `LICENSE`, `NOTICE` and `SECURITY.md`.
- **SC-004**: Every licence named in `NOTICE` matches the licence file of the project at the
  URL recorded in `research.md`, checked on the day the PR is opened.

## Assumptions

- The vendored spec-kit licence goes in `.specify/LICENSE` (one file, next to the bulk of
  the vendored files). The ten `.agents/skills/speckit-*` directories are covered by the
  NOTICE entry pointing at it rather than ten copies. Overturned if a reviewer reads MIT as
  requiring a copy inside each directory.
- autoharness, ralph-starter, MCP, MCP Apps, release-please and ZIRAN contributed ideas or
  are used as tools; no code was copied from them, so their licences are credited, not
  reproduced. Only spec-kit code is vendored. The humanizer checklist in the charters is a
  condensed paraphrase, so it is credited, not reproduced.
- Licence facts in `research.md` were checked on 2026-10-02; the builder re-checks each URL
  before writing and marks any it cannot confirm as "credit, licence not verified".
- `SECURITY.md` promises an acknowledgement and a fix in a release, not a response time: the
  project has one maintainer, and a missed promise is worse than none.
- `SECURITY.md` states "latest release" rather than a version number so it does not drift
  with every release.
- `CONTRIBUTING.md` is not shipped in the asset (not in the #245 list, not useful to an
  installed plugin). README therefore mentions it by its GitHub URL, not a relative link.
- Enabling GitHub private vulnerability reporting and branch protection are owner-side
  repository settings made outside this change (the orchestrator notes say branch
  protection is already on); `SECURITY.md` only documents the channel.
- The NOTICE-to-README check compares URLs (`https://...`) because the URL is the stable
  identity of an entry; names may be phrased differently in the two places.
- Commit author emails in history are the owner's accepted choice (owner, 2026-10-02) and
  out of scope.
