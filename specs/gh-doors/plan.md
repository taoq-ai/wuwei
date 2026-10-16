# Implementation plan: gh-doors

**Spec**: `specs/gh-doors/spec.md`
**Item**: gh-doors, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main 23625f3 holds
  2,992 after ci-not-started (#1106).
- `guards._flags(args, valued)` already reads argv as pflag does; `_draft` and `_repo_number` use
  it. `TRUE` holds pflag's true spellings.
- `guards._api` reads `gh api` argv into method, endpoint, fields and draft; `alone` says the
  command is one plain `gh` call, so the `--input` file WUWEI reads is the one gh reads.
- The allowlist spike prototyped rules (a), (b) and (c) on e34586d at +2, +5 and +2 lines.

## Design

1. Merge: `valued = (VALUED | PR_VALUED) - {'m', 'r'}`; `on(name)` is the last value pflag gives
   the bool flag (`None` or a `TRUE` spelling is on). `on('admin')` refuses; `on('auto')` goes to
   `merge_door`. `_repo_number` takes the same `valued`.
2. `_api` adds `query`: in a plain call, the `--input` file's whole text with `unicode_escape`
   decoding, appended to any `-f query=`. Only when there is data, so a GET stays a GET.
3. `_api` returns `unread`: an `--input` path, or a `-F`/`--field` `query=@` path, that is not
   read in a plain call (stdin, missing, empty, or another cwd).
4. `gh_command`: graphql with `unread` is refused in one line; a write method on
   `repositories/...` is refused naming `repos/<owner>/<repo>`.
5. `_read` answers blank for `-`, which gh reads as stdin.
6. The `alone` expression drops `len(segments(command) or ()) == 1`: a command whose every word
   matches `[\w./=@:-]+` has no control operator, and `gh_command` is reached only for a command
   `segments` parsed, so `shlex.split` cannot raise there.

Line cost: +8 runtime lines (2,992 to 3,000), inside the +8 budget.

## Constitution check

Stdlib only, no new dependency, no config key, no new door (refusals on the existing ones), test
first, at the line budget.

## Test plan

Tests in `tests/test_guards.py` with the code host stubbed (`cloud`, `not_started` fixtures), run
red on 23625f3, then green. Real execution: gh 2.89.0 with `http_unix_socket` pointed at a logging
server for each gh api shape; the merge shapes on a pflag v1.0.6 mirror. The route corpus probe on
main and head.
