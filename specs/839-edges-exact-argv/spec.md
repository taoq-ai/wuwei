# Feature Specification: exact argv only on the irreversible edges; one edges module; integrity warns at session start

**Feature Branch**: `b6-edges` (feature directory `specs/839-edges-exact-argv/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #839, part 17 of the #789 deletion pass: "refactor(guards): exact argv only on
the irreversible edges; one edges module; integrity warns at session start".

## Context

The base is main plus part 15 (#837): one switch, `guards.enforce`, with `guards.FLOOR` and
`guards.LOG_ONLY` in `cli/wuwei/guards/__init__.py`. Part 16 (#838) lands before this part, on
the batch 5 branch: an outward MCP send is local (a #727 local tool, or a call whose every
destination is the owner's own surface), allowed (an exact name in `outward.allow`) or refused,
in `guards/outward.check_send`, on the floor.

Today three Bash guards (`guards/commit_push.py`, `guards/deploy.py`, `guards/pr.py`, about
1,330 lines) run every relevant Bash call through `shell.py` (1,174 lines). `shell.py` has two
halves:

- `normalize`, a conservative simple-command parser, and the reader set (`READ_ONLY`, `reads`,
  `snippet_write`), which the state-file guard, the verdict guard, the honeytoken check,
  `sessions.owner_step_call` and the hook's refusal target also use;
- the opaque-command machinery: `mentions` (obfuscated and constructed names), `script_path`
  and `script_text` (reading the scripts a call runs), `is_opaque` (interpreter snippets),
  `classify` and its lenient walk (`_cut`, `_simple`, `_strip`, `Shape`), `unread`,
  `unreadable` and `constructed`. The hook adds an `opaque: <what>` warning and a
  `resolved: <command>` line on top.

The guards refuse far more than the edges: commit and push identity, push to the default branch,
push before fresh fast checks, `--no-verify`, hook path config, hook pointer removal, gh
aliases, unknown gh subcommands, GraphQL, a missing reviewer on `gh pr create`, the gate check
at `gh pr create`, repository environment overrides, a shepherd seat naming "merge", and every
call they could not parse. The models then reason about how to phrase a command so the parser
accepts it (the "write it to a file and run bash <file>" hint, the `resolved:` lines). That is
process reasoning the owner wants gone (#789).

The integrity guard refuses every tool call while the cached plugin verdict fails, with a
pass-through for the #831 reconfirm card.

## What changes

Guards match exact argv on the irreversible edges only, in one module, `guards/edges.py`:

| Edge | Exact argv (per command segment) | `guards.enforce = false` | The refusal names |
| --- | --- | --- | --- |
| Host merge | `gh pr merge ...`; a `gh api` write to `repos/<o>/<r>/pulls/<n>/merge` or `repos/<o>/<r>/merges` | blocks (floor) | `bin/wuwei merge <pr>` |
| Approve | `gh pr review` with `--approve` or `-a`; a `gh api` write to `.../pulls/<n>/reviews` with the field `event=APPROVE` | blocks (floor) | a comment review, and `bin/wuwei merge <pr>` |
| Admin | `gh pr merge --admin`; a `gh api` write to branch protection or rulesets | blocks (floor) | `bin/wuwei merge <pr>` |
| Force push | `git [global options] push` with `--force*`, `--mirror`, a short flag cluster holding `f`, or a `+` refspec | logged | a new commit and `git push origin HEAD:refs/heads/<branch>` |
| Deploy | design 4.7 by argv: `deploy.deny`, a marked workflow dispatch or rerun, `gh release create`, a tag push, a push to a configured environment branch, deployment or environment API writes, the built-in deploy verbs | blocks (floor) | the Owner step card of that exact command (#816) |
| Outward send | part 16's `check_send`, moved here unchanged | blocks (floor) | the `config set outward.allow ... --add` line and its card |
| PR raise | `gh pr create` from a recorded item worktree, or naming that item's branch with `--repo` and `--head`, when the item links no PR | logged | `bin/wuwei pr raise ... --item <item>` |

Parsing is `shlex` per command segment. Segments split at `;`, `&&`, `||`, `|`, `&`, `(`, `)`,
newlines and redirections. Leading `NAME=value` words and `env` (its options and assignments)
are unwrapped; `sh`, `bash`, `zsh`, `dash` and `ksh` with `-c` are unwrapped by splitting the
script the same way. Here-doc bodies are skipped, so text written to a file is never a command.
A call the guard cannot split (unbalanced quotes, an unterminated here-doc, nesting past the
cap) is logged as `guard.would_refuse` with the `UNPARSED` reason and runs.

Everything else is recorded by the traces recorder and refused by none of these guards.

Integrity becomes a SessionStart warning only: the PreToolUse integrity guard goes. The
SessionStart guard already prints its findings as context and never refuses. The #831 reconfirm
card (`wuwei integrity reconfirm` through `sessions.needs_owner`, and the doctor fix
`integrity-reconfirm`) stays; with no PreToolUse refusal left, its pass-through needs no branch.

The seat launch contract (brief, role, name, unmodified brief, unchanged head, clean gate tree)
keeps blocking with `guards.enforce` on. CAP, the host seat ceiling, free memory and the ticket
check only log; part 15 already made that so, and this part adds a test row for each.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each edge is refused by exact argv, and only the edge (Priority: P1)

**Why this priority**: the issue's first acceptance line, and owner constraint (b): a merge
outside policy and a PR raised outside WUWEI are real process errors.

**Independent Test**: `tests/test_edges.py`, one table per edge with three kinds of rows:
refused, allowed (a near miss with the same program), and `guards.enforce = false` through the
hook.

**Acceptance Scenarios**:

1. **Given** a workspace, **When** a Bash call runs `gh pr merge 7`, `gh pr merge 7 --squash`,
   `GH_REPO=o/r gh pr merge 7`, `env -i gh pr merge 7`, `bash -c 'gh pr merge 7'`,
   `cd x && gh pr merge 7`, `/usr/bin/gh pr merge 7` or
   `gh api -X PUT repos/o/r/pulls/7/merge`, **Then** it is refused and the reason starts with
   `merge policy` and names `bin/wuwei merge`.
2. **Given** `gh pr view 7`, `gh pr checks 7`, `gh api repos/o/r/pulls/7/merge` (a GET), or a
   commit message or PR body that contains the words `gh pr merge`, **Then** it passes.
3. **Given** `gh pr review 7 --approve`, `gh pr review -a 7` or
   `gh api repos/o/r/pulls/7/reviews -f event=APPROVE`, **Then** it is refused; the reason starts
   with `PR approval` and names `bin/wuwei merge`. `gh pr review 7 --comment -b ok` passes.
4. **Given** `gh pr merge 7 --admin` or a write to `repos/o/r/branches/main/protection` or
   `repos/o/r/rulesets`, **Then** it is refused; the admin reason starts with `admin merge` and
   names `bin/wuwei merge`; the protection reason starts with `branch protection`.
5. **Given** `git push --force`, `git push -f origin x`, `git push -uf origin x`,
   `git push --force-with-lease origin x`, `git push origin +x`, `git push --mirror` or
   `git -C repo push --force origin x`, **Then** it is refused and the reason names
   `git push origin HEAD:refs/heads/`. `git push origin x`, `git push origin HEAD:x` and
   `git fetch --force` pass.
6. **Given** a `deploy.deny` pattern, a marked workflow (`gh workflow run deploy.yml`),
   `gh release create v1`, `git push origin v1.2.0`, `git push --tags`, a push to a branch that
   matches `environments`, `terraform apply` or `gh api -X POST repos/o/r/deployments`, **Then**
   it is refused naming its Owner step card, and the owner's recorded Yes on that card lets that
   exact command through (#816, unchanged). `gh workflow run ci.yml` (unmarked) and
   `terraform plan` pass.
7. **Given** `gh pr create --title t --body b` in a recorded item worktree whose item links no
   PR, or `gh pr create --repo o/r --head <item branch>` from anywhere in the workspace, **Then**
   it is refused, and the reason starts with `pr raise: ` and names
   `bin/wuwei pr raise ... --item <item>`. In a worktree that is no recorded item's, or for an
   item that already links a PR, it passes.
8. **Given** an MCP write through a tool that is neither on `outward.allow` nor local, **Then**
   it is refused as part 16 specifies, now by `guards/edges.check_send`.
9. **Given** `guards.enforce = false`, **When** each refused row above runs through the hook,
   **Then** merge, approve, admin, branch protection, deploy and outward send still block (the
   floor, constitution VII), and force push and the recorded-item `gh pr create` each record
   one `guard.would_refuse` and pass.

---

### User Story 2 - No guard refuses a command because it could not read it (Priority: P1)

**Why this priority**: the issue's second acceptance line.

**Independent Test**: `tests/test_edges.py`, `tests/test_protect_state.py`,
`tests/test_hooks.py`.

**Acceptance Scenarios**:

1. **Given** a Bash call naming `git` or `gh` that `shlex` cannot split (an unbalanced quote),
   **When** the hook runs with `guards.enforce` true or false, **Then** it passes and records one
   `guard.would_refuse` with the `UNPARSED` reason.
2. **Given** `for r in a b; do git -C $r push origin main; done`,
   `python3 -c "import subprocess; subprocess.run(['git','push','-f'])"`, `bash deploy.sh` or
   `x=gh; $x pr merge 7`, **Then** no edge guard refuses it: a ceiling the code host and the
   credential layout hold (design 9.1).
3. **Given** a call that `shell.normalize` cannot parse and that names a state file, **When** the
   state-file guard runs, **Then** it returns `UNPARSED` and the hook logs it; a parsed write to
   `state.json` is still refused (records floor).
4. **Given** a top-level `cd` out of the workspace, **Then** it is logged with `WORKSPACE_ROOT`,
   as today.
5. **Given** a refused Bash call, **Then** the hook adds no `resolved:` line, and no
   `opaque: <what>` warning is recorded.

---

### User Story 3 - The refusals name the way through (Priority: P1)

**Why this priority**: the issue's third acceptance line.

**Independent Test**: `tests/test_edges.py` asserts each reason;
`tests/test_invariants.py::test_reason_corpus_has_no_wall` reads every reason in `edges.py`.

**Acceptance Scenarios**:

1. **Given** a merge, approve or admin refusal, **Then** its reason contains `bin/wuwei merge`.
2. **Given** a force push refusal, **Then** it contains `git push origin HEAD:refs/heads/`.
3. **Given** a deploy refusal, **Then** it is the `publish: ` text with the Owner step card of that
   exact command.
4. **Given** the reason corpus, **When** the wall check runs with enforce on and off, **Then** no
   edge reason is a wall.

---

### User Story 4 - Integrity warns at session start and never refuses a tool call (Priority: P1)

**Why this priority**: named in the issue title; the owner keeps plugin integrity as a warning
(pass plan, owner constraints).

**Independent Test**: `tests/test_integrity.py`, `tests/test_hooks.py`.

**Acceptance Scenarios**:

1. **Given** a cached integrity verdict that fails, **When** a PreToolUse hook runs for Bash,
   Write or an MCP tool, **Then** no integrity refusal is produced.
2. **Given** a failing integrity check, **When** SessionStart runs, **Then** the hook exits 0,
   and its additional context and stderr carry the integrity reason, which names the reconfirm or
   reinstall step.
3. **Given** a development checkout that needs reconfirmation, **When** the planner runs
   `bin/wuwei integrity reconfirm`, **Then** the Owner step card is printed and the owner's Yes
   lets the same command run (#831, unchanged).

---

### User Story 5 - The seat launch contract keeps blocking (Priority: P2)

**Why this priority**: owner constraint (b) and the "process control kept" table.

**Independent Test**: `tests/test_enforce.py` rows.

**Acceptance Scenarios**:

1. **Given** `guards.enforce = true`, **When** a seat launch has no logged brief, a role or name
   mismatch, a modified brief, a changed head or a dirty gate tree, **Then** it is refused.
2. **Given** `guards.enforce = true`, **When** a launch hits CAP, the host seat ceiling, the free
   memory floor (or free memory is unmeasured) or a missing ticket, **Then** it records
   `guard.would_refuse`, passes, and the session is shown the warning (#660).

---

### Edge Cases

- A quoted argument that contains an edge's words (`git commit -m "gh pr merge"`,
  `gh pr comment 7 --body "never git push --force"`) is one argv word, never a segment.
- A here-doc body (`cat > notes.md <<'EOF'`, a line `gh pr merge 7`, `EOF`) is skipped.
- `$(gh pr merge 7)` unquoted is split by the `(` and `)` punctuation into its own segment and
  refused. Inside double quotes or backticks it is one word: a ceiling, named in a `ponytail:`
  comment and held by the code host's protected base branch and the credential layout (9.1).
- A path-qualified program (`/usr/bin/git`, `./bin/gh`) matches by its basename.
- The `gh` global `-R` and `--repo` before the subcommand are skipped; the `git` global options
  `-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace` (each with its value) and `--no-pager`
  are skipped.
- `git push --delete origin x` and `git push origin :x` are not force pushes; the code host
  protects its refs.
- A call outside every workspace returns 0 before any parsing (design 9.1 scope).
- The watch heartbeat's `git push --force origin main` probe is still refused (the hook exits 2):
  heartbeat refusals are always enforced.
- Canary and honeytoken egress and owner disposition markers through `gh` bodies and body files
  stay refused on the records floor: `security.gh_outbound` runs for each `gh` segment that
  writes text.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cli/wuwei/guards/edges.py` holds the Bash edges and the outward send check. Its
  `GUARDS` are `check_bash` (merge, approve, admin, branch protection, force push, recorded-item
  `gh pr create`, the `gh` body scan), `check_deploy` (deploy) and `check_send` (part 16,
  moved).
- **FR-002**: matching is exact argv per segment, as What changes says; relevance is a plain word
  search on the raw text before any parsing; a call outside a workspace returns 0.
- **FR-003**: a call `edges` cannot split returns `(2, shell.UNPARSED)`; the hook logs it in both
  settings. No edge refusal depends on a parse failure.
- **FR-004**: `guards/commit_push.py`, `guards/deploy.py` and `guards/pr.py` stop being guards:
  `deploy.py` becomes `edges.py`; `commit_push.py` moves to `cli/wuwei/commit_push.py` as the
  library that the native Git hooks, `pr act` and dispatch use, without `GUARDS`; `pr.py` is
  deleted, and `gate_check` with `_recorded_gates` moves to `cli/wuwei/merge.py`.
- **FR-005**: `shell.py` loses `mentions`, `script_path`, `script_text`, `is_opaque`, `classify`,
  `unread`, `unreadable`, `constructed`, `UNKNOWN_GIT`, `PUBLISHERS` and their private helpers.
  It keeps `normalize`, `operands`, the reader set, `inline_code`, `git_kind`, `known_cli`,
  `_cd_target`, `_cwd`, `_text`, `WORKSPACE_ROOT` and `UNPARSED`.
- **FR-006**: the hook drops the opaque warning, the unknown git branch, the `PUBLISH` tuple and
  the `resolved:` line; it keeps logging `UNPARSED` and `WORKSPACE_ROOT` once per call.
- **FR-007**: `guards.FLOOR` holds `edges.check_deploy` and `edges.check_send` in place of
  `deploy`, `pr` and `outward.check_send`; merge, approval, admin and branch protection stay on
  the floor by their reason prefix (`guards.MERGE`). Force push and `gh pr create` are off the
  floor.
- **FR-008**: the PreToolUse integrity guard goes; `guards.MODULES['integrity']` is
  `{'SessionStart': None}`.
- **FR-009**: `protect_state.check_bash` and the verdict guard stop calling `shell.classify`;
  `security.reads_honeytoken` stops calling `shell.mentions`.
- **FR-010**: design spec 4.1, 4.5, 9.1 and 9.2, constitution II, and the duplicated unparsed
  paragraph in `docs/site/security.md` say what the code does.

### Key Entities

- **Segment**: one simple command after splitting and unwrapping: its argv and the directory a
  literal `cd` earlier in the call left it in.
- **Edge**: an action WUWEI cannot take back (design 9.2), matched by exact argv.

## Success Criteria *(mandatory)*

- **SC-001**: `tests/test_edges.py` has one table per edge with refused, allowed and enforce-off
  rows, and passes.
- **SC-002**: no module under `cli/` calls a deleted `shell.py` function (grep in tasks T015).
- **SC-003**: `guards/` has no `commit_push.py`, `deploy.py` or `pr.py`; about 450 lines of
  `shell.py` go.
- **SC-004**: no PreToolUse refusal comes from the integrity guard.
- **SC-005**: the touched test files pass; CI is the gate.

## Assumptions

1. **The floor wins over "logged with enforce off"** for floor edges. The issue asks each edge
   table for a "logged with enforce off" row; constitution VII and part 15 keep merge, approve,
   admin, deploy and outward send blocking in both settings. The enforce-off row of those tables
   asserts the block; force push and `gh pr create` assert the log.
2. **Deploy keeps design 4.7's list**, by exact argv. The issue names `deploy.deny` and workflow
   argv; 4.7 also names releases, tag pushes, environment branch pushes, the deployment API and
   the built-in deploy verbs, and dropping them would open a hole the owner did not ask for. What
   goes is the parse machinery and the code-host PR lookup: a `gh pr merge` is refused by the
   merge edge whatever its base, and `bin/wuwei merge` checks `merge_deploys` and environment
   bases (`merge.check`).
3. **The merge refusal no longer runs `merge.check` in the hook.** Every session `gh pr merge` is
   refused naming `bin/wuwei merge`, which runs the policy and asks the Owner step card when it
   must. This takes a code-host call off the hook path.
4. **Branch protection stays with admin** (design 9.2, row Admin).
5. **The `gh` body scan stays** (records floor): `edges.check_bash` calls `security.gh_outbound`
   for each `gh` segment that writes text, as `pr.action` does today.
6. **Unreadable input to the state-file guard is logged, not refused.** The issue says no guard
   refuses a command because it could not parse it. A parsed write to a state file stays refused
   (records floor); an unparsed one is logged. The state files' mode 0444 and the CLI as their
   only writer remain the local checks until part 23.
7. **Removed refusals with another home**: identity, default-branch push, fast checks before push
   and `--no-verify` stay in the native Git hooks (`wuwei git-hook`, unchanged here); fast checks
   before handoff live in `build.next_action` and `dispatch.next_step`; the reviewer rule and the
   gate check before raising live in `bin/wuwei pr raise --item`.
8. **gh aliases, GraphQL and constructed names are not parsed.** They are ceilings the code
   host's protected refs and the credential layout hold (design 9.1); exact argv is cooperative
   mistake prevention, as 4.5 says.
9. **`commit_push.py` moves rather than splits**: its library half has eight importers, and a
   module left in `guards/` without guards would still be imported by `discover()` or need an
   empty `MODULES` row.
10. **No config key is retired**: `deploy.*`, `environments`, `shepherd.min_reviewers`,
    `shepherd.reviewers` and `worktree.git_hooks` are still read. `workspace.RETIRED` is unchanged.
11. **Part 16 lands first.** If its `check_send` lands under another name, the move keeps that
    behaviour and the floor key follows the new home.

## Deferred

- `docs/site/reference.md` (the posture paragraph near line 376, the latency table near 452) and
  `docs/site/daily.md:260` ("the PR guard"): part 24 rewrites the site.
- The native Git hooks (`wuwei git-hook`) and `fast_checks`: part 23.
- The MCP launch gate in `agent_launch.check_mcp`: part 18.
