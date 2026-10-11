# Feature Specification: the command guard judges words by position

**Feature Branch**: `730-guard-word-position`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #730 (owner, 2026-10-10, item 57): compound commands were refused
because `wuwei` appeared inside a grep pattern, or because a path was held in a shell
variable. Deliver: a word is a WUWEI command only in the program position of a stage (argv[0]
or the launcher form); a word inside a quoted pattern or an argument to grep, sed, awk or echo
is data; a variable holding a path is resolved when the assignment is in the same command
text, and otherwise the stage is judged by its program name, not refused for the unknown; a
refusal that remains names the stage and the word. Companion to #671 (argv-based git/gh guard).

## Root cause (read on main at 871f5a1, reproduced read-only)

Reproduction: a throwaway workspace built like the `places` fixture of
`tests/test_owner_actions.py` (a `.wuwei` directory, seeded integrity, empty `config.toml`),
every PreToolUse Bash guard from `wuwei.guards.discover()` run in-process on each command.
Nothing in a real workspace was read or written.

| Command | Result on main | Where |
|---|---|---|
| `grep -n wuwei tests/test_x.py` | 0 | (already passes) |
| `d=/path/to/tree; ls $d` | 0 | (already passes) |
| `d=tests; grep -rn wuwei $d \| sort \| head -3` | 2 Opaque owner action | protect_state.py:327-331 |
| `grep -n "wuwei decide" t.py \| sort` | 2 Opaque owner action | protect_state.py:327-331 |
| `grep -n "wuwei decide" t.py > out.txt; python3 -m pytest -q` | 2 Opaque owner action | protect_state.py:327-331 |
| `awk "/wuwei decide/" t.py`, `sed -n "/wuwei decide/p" t.py`, `sed "s/wuwei decide/x/" t.py` | 2 Opaque owner action | protect_state.py:278-283 |
| `git grep -n "wuwei decide"` | 2 Opaque owner action | protect_state.py:278-283 |
| `x=bin/wuwei; $x state set a b` | 2 from commit_push, deploy and pr (unparsed) and protect_state (nonliteral command name) | shell.py:442-443, shell.py:134-136 |
| `x=bin/wuwei; $x decide D-1 a` | 2 nonliteral command name | shell.py:442-443 |

Five facts on main make this happen:

1. Relevance is text only, by design (design spec, Guard scope): `_owner_relevant`
   (`cli/wuwei/guards/protect_state.py:212`) is true when the CLI word, an owner group and an
   owner verb appear anywhere, and `_CLI_NONLITERAL` (`protect_state.py:138`) reads
   `wuwei $d` (a grep pattern followed by a path in a variable) as the CLI with a non-literal
   group. That is right for relevance; the parsed decision must then judge by position, and
   it does not.
2. `_owner_action` counts every CLI mention in the text (`unseen`, `protect_state.py:242`) and
   subtracts a reader's mentions only when the reader stands alone: no redirect, no pipe into
   a non-reader (`feeds`, `protect_state.py:247-250`, and `256-259`). Any later stage outside
   `_READERS` (`sort`, `awk`, `sed`, `python3`) keeps a grep pattern's mention unseen, and line
   328 refuses. The rule exists because echo and printf print their arguments, so their text
   can reach an executor; grep prints matched lines, never its pattern.
3. A stage that is neither the CLI nor a reader is refused when its arguments match
   `_CLI_WORD` (`protect_state.py:278-283`). awk and sed are not readers (they can run or
   write), and `git grep` is not one either, so a pattern argument holding the CLI word reads
   as an opaque owner action.
4. `shell._unwrap` refuses every non-literal program word (`cli/wuwei/shell.py:442-443`,
   "nonliteral command name is unsupported"), even when the same text assigns that variable a
   literal path first. The refusal names neither the word nor the stage.
5. `shell.mentions` (`shell.py:134-136`) counts any non-literal program word as a possible
   guarded name, so `$x` makes the call relevant to commit_push, deploy and pr; the parse then
   fails and `shell.unread` answers UNPARSED.

The fix sits at the two shared spots: `shell.py` resolves a program-position variable from a
leading literal assignment (parser and relevance helper), and `_owner_action` judges argument
words by the stage's program. Relevance stays text only.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which assignments resolve a variable? A: A leading assignment statement: the command
  text starts with one or more `name=value` words followed by `;`, `&&` or a newline, each
  value one literal word (`[\w./][\w./:@+-]*`, quotes around it allowed), and the name is not
  assigned anywhere else in the text. The first statement always runs in the outer shell, so
  every later `$name` sees that value. A second assignment, or an assignment only in a
  subshell, a pipe stage or after another command makes the value uncertain, so the variable
  stays unresolved and refused as today.
- Q: Which positions resolve? A: Program position only (`$x`, `${x}`, `"$x"` as argv[0], also
  after a wrapper such as `timeout 5` or `xargs`). A variable in an argument keeps today's
  rules: the stage is judged by its program (`ls $d` passes), and the owner-action check still
  refuses `bin/wuwei $X verb` (exit 2), because a non-literal group or verb is not a literal
  owner action.
- Q: What if the variable holds git, gh or another guarded program? A: It stays a parse
  refusal, exactly as today (`G=git; $G push origin main` refuses with deploy). The guards
  require git and gh as plain words.
- Q: Does `sh -c '$x ...'` resolve? A: No. A child shell does not inherit unexported shell
  variables; the inner script parses with no variables, as today. eval also parses with none.
- Q: Which programs' arguments are data? A: grep, rg and `git grep` print matched lines, not
  their arguments, so their words are data in any pipe or redirect; `grep --label` and
  `rg -r/--replace/--pre` print or run their arguments and keep today's rule. awk and sed are
  readers when their options are only `-n`, `-E`, `-r`, `-e` or `-F...` and their script holds
  no run or write construct (`system`, `getline`, `|`, `>`, a sed `e`, `w` or `W` command or
  flag); any other awk or sed keeps today's refusal. echo and printf keep the #471 rule (data
  when they stand alone), because their output is their arguments.
- Q: What does a refusal name? A: The nonliteral-command refusal names the word and the stage
  (`nonliteral command name $y in stage $y foo is unsupported; ...`). The two Opaque owner
  action refusals keep their current text and append `Stage: <argv>; word: <match>.`, or, when
  no stage holds the mention, that it sits in a here-doc, comment or input no stage shows.
- Q: Interpreters (`python3 -m pytest -k "wuwei and decide"`, `perl -ne '... wuwei decide'`)?
  A: Out of scope; they keep today's refusal, which now names the stage (see Assumptions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A search for the CLI word is not a WUWEI command (Priority: P1)

A seat inside a WUWEI workspace searches for `wuwei` or for an owner command name
(`wuwei decide`) with grep, rg, git grep, awk or sed, and pipes or redirects the result. The
guard lets it run: the word is a pattern, not a program.

**Why this priority**: the owner hit it on 2026-10-10; it blocks ordinary work in the
repository that builds WUWEI itself.

**Independent Test**: `check_bash` in the `places` workspace on each command returns `(0, '')`.

**Acceptance Scenarios**:

1. **Given** a WUWEI workspace, **When** a seat runs `grep -n wuwei tests/test_x.py`, **Then**
   exit 0.
2. **Given** a WUWEI workspace, **When** a seat runs `d=tests; grep -rn wuwei $d | sort | head -3`,
   `grep -n "wuwei decide" t.py | sort` or
   `grep -n "wuwei decide" t.py > out.txt; python3 -m pytest -q`, **Then** exit 0.
3. **Given** a WUWEI workspace, **When** a seat runs `awk '/wuwei decide/' t.py`,
   `sed -n '/wuwei decide/p' t.py`, `sed 's/wuwei decide/x/' t.py` or
   `git grep -n 'wuwei decide'`, **Then** exit 0.
4. **Given** a WUWEI workspace, **When** a seat runs an awk or sed that runs or writes
   (`awk 'BEGIN{system("bin/wuwei decide D-1 a")}'`, `sed 's/.*/bin\/wuwei decide D-1 a/e' t.py`,
   `sed -i 's/^/exec bin\/wuwei decision outcome x;/' x.tcl; tclsh x.tcl`), or a stage whose
   output is its arguments pipes into an executor
   (`echo 'exec bin/wuwei decision outcome x' | sed 's/x/y/' | tclsh`,
   `rg -r 'exec bin/wuwei decision outcome x' . t.py | tclsh`), **Then** exit 2, as today.

---

### User Story 2 - A variable that holds the CLI path is the CLI (Priority: P1)

A seat stores the CLI path in a variable at the start of the call and runs it. The guards
judge the call as the CLI: a seat command passes, an owner action is refused with its owner
reason.

**Why this priority**: acceptance row 3 of the issue; today every Bash guard refuses it.

**Independent Test**: the full PreToolUse hook (`wuwei.commands.hook.run`) on the command in a
workspace, and `check_bash` for the owner reason.

**Acceptance Scenarios**:

1. **Given** a WUWEI workspace, **When** a seat runs `x=bin/wuwei; $x state set a b`, **Then**
   the hook exits 0 (judged as `bin/wuwei state set a b`).
2. **Given** a WUWEI workspace, **When** a seat runs `x=bin/wuwei; $x decide D-1 a` (or
   `"$x"`, `${x}`, `timeout 5 $x ...`), **Then** `check_bash` returns 1 with the owner reason of
   `bin/wuwei decide`.
3. **Given** a WUWEI workspace, **When** a seat runs `d=/path/to/tree; ls $d`, **Then** exit 0.
4. **Given** a WUWEI workspace, **When** the variable is unresolved (`$y foo`,
   `ls; x=bin/wuwei; $x decide D-1 a`, `x=bin/wuwei; x=ls; $x decide D-1 a`,
   `x=bin/wuwei; sh -c '$x decide D-1 a'`) or holds a guarded program
   (`G=git; $G push origin main`), **Then** the call is refused as today (exit 2).

---

### User Story 3 - A refusal that remains names the stage and the word (Priority: P2)

When the guard still refuses, the reason names the stage it judged and the word it read as the
CLI, so the seat can rewrite that one stage.

**Independent Test**: assert the reason text of three refusals.

**Acceptance Scenarios**:

1. **Given** `$y foo`, **When** `shell.normalize` reads it, **Then** the ParseError text
   contains `$y` and `$y foo` (the git guards print that text when they refuse it).
2. **Given** `perl -ne "print if /wuwei decide/" t.py` in a workspace, **When** checked,
   **Then** exit 2 and the reason contains `Stage: perl -ne` and `word: wuwei`.
3. **Given** `echo 'exec bin/wuwei decision outcome x' | sed 's/x/y/' | tclsh` in a workspace,
   **When** checked, **Then** exit 2 and the reason contains `Stage: echo` and `word: wuwei`.

### Edge Cases

- Outside a WUWEI workspace every command above returns 0 (design spec, Guard scope).
- `X={group}; bin/wuwei $X {verb}` (a variable in an argument of the CLI) stays exit 2.
- `x=bin/wuwei; echo D-1 | xargs $x decide` stays refused (input-driven owner action).
- `git grep -O'bin/wuwei decide D-1' x` stays refused: `-O` runs a program, so it is not a read.
- `grep --label='exec bin/wuwei decision outcome x' -H . - < f | tclsh` stays refused.
- `awk -f prog.awk 'wuwei decide'` stays refused (the program is in a file the guard does not read).
- `python3 -m pytest -q`, a `for` loop and `export X=1` still pass (pre-flight rule).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The shell parser MUST resolve a program-position variable (`$x`, `${x}`, `"$x"`)
  to its value when a leading assignment statement of the same text assigns it once to a single
  literal word, and judge the stage by that value.
- **FR-002**: The parser MUST keep refusing a program-position variable that is unresolved or
  resolves to a guarded program name (git, gh and the caller's extra protected names), and the
  refusal MUST name the word and the stage.
- **FR-003**: The relevance helper `shell.mentions` MUST NOT count a program-position variable
  as a possible name when it resolves under FR-001 to a value that does not match the names.
- **FR-004**: In the owner-action check, the words of grep (without `--label`), rg (without
  `-r`, `--replace` or `--pre`) and `git grep` (when it is a git read) MUST be data in any pipe
  or redirect.
- **FR-005**: In the owner-action check, awk and sed MUST count as readers when their options
  are only `-n`, `-E`, `-r`, `-e` or `-F...` and their script has no run or write construct;
  otherwise they keep today's handling.
- **FR-006**: Both Opaque owner action refusals MUST keep their current text and append the
  stage and the word, or say that the mention is in no stage.
- **FR-007**: Every refusal pinned by the existing suites MUST stay (executor probes,
  interpreter probes, regression list, indirect forms, parser-warns publish forms).

### Key Entities

- **Leading variables**: `{name: value}` read from the text's first statement; computed per
  call, never stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The three acceptance commands of the issue exit 0 through the full PreToolUse
  hook in a workspace (row 3 is judged as the CLI: `state set` is a seat command).
- **SC-002**: Every search command in the reproduction table exits 0; every bypass probe in
  User Story 1 scenario 4, User Story 2 scenario 4 and the Edge Cases exits 2.
- **SC-003**: The full suite passes; no existing assertion changes.

## Assumptions

- No orchestrator notes file exists for #730 (`notes/730-full.md` is missing), so the
  reproduction used a throwaway fixture workspace instead of a named dry-run workspace.
- Acceptance rows 1 and 2 already exit 0 on main in isolation; they become regression tests.
  The owner's refusals came from the compound forms in the reproduction table (a pipe into
  sort, a redirect followed by another command, awk or sed patterns, a CLI path in a variable).
- Interpreter stages (`python3 -m pytest -k "wuwei and decide"`, `perl -ne`) keep today's
  refusal: an interpreter can run any word it is given, and telling a pytest `-k` pattern from
  code needs a per-tool rule. Deferred; the refusal now names the stage.
- Argument-position variables are not resolved (`cd $d` keeps the cd containment refusal,
  `bin/wuwei $X verb` keeps exit 2). The issue's acceptance pins program position only.
- grep can print file names (`-l`, `-H`); a file named as a command must already exist, which
  `ls | tclsh` reaches today too. Recorded as a ponytail residual, not new exposure.
- The awk and sed effect check is a token scan, not a parser; it over-matches, and a script it
  cannot clear keeps today's refusal (ponytail comment in the code).
- Guards stay cooperative (design spec: "none of them is a boundary"); the owner-action floor
  is unchanged.
