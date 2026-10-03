# Implementation Plan: reviewers from history, owner override, solo fall-through

**Branch**: `369-reviewers-history` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Every reviewer path (`pr raise`, `pr ping`, the new `pr reviewers`) already routes through
`shepherd._rank`. The fix lives there:

1. Resolve unmapped emails through `code_host.author_login` with a day cache; a "cannot
   resolve" answer skips the email with one silent `reviewer.unresolved` event.
2. Owner override (`shepherd.reviewers`, `repos.shepherd.reviewers`) returns before the
   ranking; `shepherd.reviewers_exclude` joins the existing author exclusion.
3. An empty result returns `[]` (solo) instead of refusing; `min_reviewers` refuses only a
   non-empty short list, naming the two ways out.
4. Downstream of `[]`: `raise_pr` and `post_review_request` print `reviewers: none (solo)`,
   request and post nothing; obligations skip `reviewer` and `channel-post` for that PR; the
   status line shows it.
5. The `gh pr create` guard's reason names the ways out and the hook drops the
   `no setting lowers it` line for that one reason.
6. `wuwei pr reviewers <ref> [--explain]`: a thin command over `select_reviewers`.

No new module, no new adapter operation, no new port parameter.

## Technical Context

Python 3.11+ stdlib; pytest for tests. The code host is reached only through the existing
`code_host.author_login` and `request_reviewers` operations; git only through
`vcs.authorship`. The cache and the event go through the shared state writer
(`state._write_state`, `state.append_event`).

## Constitution Check

- I stdlib: yes.
- II fail closed: only the adapter's explicit not-found answers (`author login
  unavailable`, `invalid author email`, or an empty login) skip an email; every other
  adapter failure or an error body still raises and exits 2.
- III one behaviour, one function: selection stays in `_rank`; `select_reviewers` stays the
  PR-ref entry point; `pr reviewers` only prints what `select_reviewers` returns.
- IV test first: tasks.md orders every test before its code.
- V ponytail: reuse `_rank`, `author_login`, `state._write_state`, the existing regex login
  check, the existing `requested == selected` verification, `obligations._not_applicable`'s
  skip mechanism, `status.line`. One inner `tally(rows)` closure serves both the ranking
  and the per-path explanation.
- VII security: `author_logins` is producer-owned state (every key is, by
  `state._protected`); `reviewer.unresolved` is reserved in `EVENT_PRODUCERS`. The event
  carries the email's local part only. New config keys name people, so they join
  `profiles.PRIVATE`.

## Changes, file by file

### `cli/wuwei/workspace.py` (SCHEMA)

- `shepherd`: add `"reviewers": [(str, None)]` and `"reviewers_exclude": [(str, None)]`.
- `repos` item: add `"shepherd": {"reviewers": [(str, None)]}`.

### `cli/wuwei/guards/__init__.py`

- Add, next to `OWNER_ONLY`:
  `REVIEWER_WAYS_OUT = "bin/wuwei config set shepherd.min_reviewers 0, or bin/wuwei config set shepherd.reviewers '[\"login\"]'"`
  and `NO_REVIEWER = 'PR create requires a named --reviewer in the same command; or ' + REVIEWER_WAYS_OUT`,
  with a one-line comment: the reason names its ways out, so it carries no posture line.

### `cli/wuwei/guards/pr.py`

- `create_check` (`:207-210`): return `1, NO_REVIEWER` (imported from `wuwei.guards`). The
  condition is unchanged.

### `cli/wuwei/commands/hook.py`

- `posture` (`:213-247`): import `NO_REVIEWER` with `level`; after `level(...)`,
  `if reason == NO_REVIEWER: line = ''`. Level and enforcement are unchanged (still block).

### `cli/wuwei/shepherd.py`

`_rank(root, config, repo, branch, paths, author, source_path=None, explain=None)`:

1. Override first: `override = repo['shepherd']['reviewers'] or config['shepherd']['reviewers']`.
   When non-empty: `selected = [l for l in override if l.casefold() != author.casefold()]`,
   append `shepherd.reviewers: <logins>` to `explain` when given, run the existing login
   regex check, return `selected`. No history read, no lead, no `min_reviewers`, no email
   verification.
2. Move the `no changed source paths for reviewer selection` refusal from both callers
   (`select_reviewers:98-99`, `raise_pr:285`) into `_rank`, after the override, as
   `merge.require(paths, ...)`.
3. `excluded = {author, *shepherd.reviewers_exclude}` casefolded; a login is counted when
   not in `excluded` and not ending `[bot]` (replaces the check at `:59`).
4. Email to login, inner `login_of(email)`: `shepherd.authors` first (unchanged); else the
   day cache `state.read_state(root).get('author_logins', {})` (read once per call); else
   `result = host.author_login(repo['name'], email, root=root)`:
   - exit 0, `data` a dict with no `message`/`errors` key and a non-empty str `login`:
     the login;
   - exit 0 with an empty or missing login, or exit non-zero whose reason contains
     `author login unavailable` or `invalid author email`: `None` (unresolved);
   - anything else: `raise ValueError(result.reason or 'author login unmeasured')`.
   New answers go to a local `fresh` dict and the in-memory cache.
5. Inner `tally(rows)`: the existing record validation (`:43-46`), `login_of`, skip `None`,
   apply the exclusion, return `counts`. The window loop calls
   `tally(merge.read(vcs.authorship, ..., paths, days, root=root))`; ranking, tie and break
   logic unchanged.
6. After the loop, when `fresh`: one `state._write_state(lambda d: d.setdefault('author_logins', {}).update(fresh), root, reserved=False)`,
   then `state.append_event('reviewer.unresolved', {'repo': repo['name'], 'author': email.split('@', 1)[0]}, root)`
   for each `fresh` email whose value is `None`.
7. Lead: appended when set, not the author and not excluded (casefold).
8. `if selected and len(selected) < min_reviewers: raise merge.Refused('fewer eligible reviewers than shepherd.min_reviewers; ' + REVIEWER_WAYS_OUT)`.
   An empty `selected` returns `[]` (solo).
9. Keep the login regex check. Verification (`:76-83`) narrows to logins that come from
   `shepherd.authors`: `emails = {row['login']: email for email, row in mapping.items()}`;
   for each selected login in `emails`, verify as today. Drop
   `reviewer needs a configured email` and the second lookup of host-resolved logins.
10. `explain` (a list, or None): when given, append `window: <days> days` (`all history`
    for 0), then one line per ranked login in rank order:
    `<login> <total>: <path> <n>, ...` with ` (selected)` when selected, where the per-path
    numbers come from `tally(merge.read(vcs.authorship, ..., [path], days, root=root))` for
    each path at the deciding `days`; then `<lead>: shepherd.lead_login (selected)` when the
    lead was added; then `unresolved: <local parts>` when any email in this ranking was
    unresolved.

`select_reviewers(root, ref, explain=None)`: drop the empty-paths refusal (now in `_rank`)
and pass `explain` through.

`post_review_request`: validity check (`:188-190`) keeps "is a list" and "no duplicates" and
drops `len(reviewers) < min_reviewers` (selection enforced it; the override bypasses it).
Request and verify only `if reviewers`. Keep the `pr_reviewers` write (also for `[]`). Then
`if not reviewers: print(obligations.SOLO); return 0` before the second gate and the post.

`raise_pr`: drop `merge.require(paths, ...)` at `:285`; after `print(ref)`,
`if not reviewers: print(obligations.SOLO)`. The `if reviewers:` request guard at `:298`
already exists.

### `cli/wuwei/obligations.py`

- `SOLO = 'reviewers: none (solo)'` (module constant; shepherd and status import it).
- `_not_applicable(config, recorded=None)`: after the `min_reviewers == 0` branch,
  `if recorded == []: return {'reviewer': SOLO, 'channel-post': SOLO}`. Its two callers
  (`_visibility` at `:153` and the sweep's `NOT APPLICABLE` print at `:253`) pass
  `data.get('pr_reviewers', {}).get(ref)`, so the sweep prints
  `<ref> NOT APPLICABLE reviewer: reviewers: none (solo)` and owes neither finding.

### `cli/wuwei/commands/status.py`

- `snapshot`: `result['solo'] = any(row == [] for row in data.get('pr_reviewers', {}).values())`.
- `line`: `if data.get('solo'): parts.append(SOLO)` after the `prs N changed` part.

### `cli/wuwei/commands/pr.py`

- New subparser `reviewers` with `ref` and `--explain` (store_true), help
  `Show the reviewers pr ping would request`. `run_reviewers`: `lines = [] if args.explain else None`;
  `selected = shepherd.select_reviewers(workspace.find_workspace(), args.ref, explain=lines)`;
  print each line, then `reviewers: <logins>` or `SOLO`; return 0. `merge.Refused` prints
  and returns 1; `shepherd.ERRORS` prints `reviewer selection unmeasured: <reason>` and
  returns 2.

### `cli/wuwei/state.py`

- `STATE_PRODUCERS['author_logins'] = 'wuwei pr raise, ping or reviewers'`.

### `cli/wuwei/commands/event.py`

- `EVENT_PRODUCERS['reviewer.unresolved'] = 'wuwei pr raise, ping or reviewers'`.

### `cli/wuwei/signal.py`

- Add `'reviewer.unresolved'` to `SILENT`.

### `cli/wuwei/profiles.py`

- `PRIVATE`: add `'shepherd.reviewers'`, `'shepherd.reviewers_exclude'`, `'repos.shepherd'`.

### `templates/workspace/config.toml`

- In the commented `[[repos]]` example, after the `# [repos.merge]` block:
  `# [repos.shepherd]` and `# reviewers = ["reviewer"] # Replaces shepherd.reviewers for this repository.`
- `[shepherd]`, right after `lead_login`:
  `reviewers = [] # Code host logins requested instead of the history ranking and the lead.`
  and `reviewers_exclude = [] # Code host logins never picked from history, the lead included.`
- `min_reviewers` comment: add that a repository with no other author raises with no
  reviewer.
- `[shepherd.authors]` comment: an unmapped email is resolved through the code host; one it
  cannot resolve is skipped.

### Docs

- `docs/site/configuration.md`: rows `shepherd.reviewers` and `shepherd.reviewers_exclude`
  right after `shepherd.lead_login`; row `repos.shepherd.reviewers` after the `repos.gates`
  rows; add `[repos.shepherd]` to the Sections table's workspace row; update the
  `shepherd.min_reviewers` row (solo fall-through, the two ways out) and the last sentence
  of the `shepherd.authors` row (skipped with `reviewer.unresolved`, never a refusal).
- `docs/site/reference.md`: in "Raising a PR", one paragraph on how reviewers are chosen
  (history, override, exclude, solo `reviewers: none (solo)`) and `bin/wuwei pr reviewers
  REF [--explain]`; the `bin/wuwei pr` command row description gains "shows its
  reviewers"; in the posture paragraph, note that the missing-reviewer refusal of
  `gh pr create` names its ways out and carries no posture line; in "Watch state", the
  `reviewers: none (solo)` part of the status line.

## Must not change

- The ranking itself: windows, top two, tie rule, author and `[bot]` exclusion, lead.
- `shepherd.authors` precedence and the host verification of its logins
  (`test_unverified_reviewer_login_refuses_request` keeps passing).
- Fail closed on adapter failures other than the explicit not-found answers.
- `min_reviewers` refusing a non-empty short list; `min_reviewers = 0` behaviour.
- The `gh pr create` guard condition and its block level; other `pr` guard reasons keep
  their `owner-only action; no setting lowers it` line.
- `_mentions` and the channel post; `outward.py` review-ping matching.
- The `pr_reviewers` producer and `pr.reviewers_selected` event.

## Existing tests whose expectation changes (rewrite, do not delete coverage)

- `test_zero_reviewers_names_minimum`: empty history, no lead now returns `[]` (solo). Keep
  a `min_reviewers` refusal test via `test_configured_minimum_two_requires_two`, which now
  also asserts the ways-out text.
- `test_unmapped_author_names_email_and_key`: now skipped with one event; selection is
  `['lead']`.
- `test_empty_code_host_login_names_email_and_key`: raise exits 0, solo, one event for
  `builder`.
- `test_owner_handle_case_differs_from_code_host_login`: owner still excluded
  case-insensitively; raise now exits 0 solo with `pr_reviewers[ref] == []`.
- `tests/test_pr_guards.py` table rows with hint `reviewer` keep passing (the new reason
  contains it).
