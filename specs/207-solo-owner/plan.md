# Implementation Plan: Solo owner without reviewers or chat

**Branch**: `207-solo-owner` | **Spec**: `specs/207-solo-owner/spec.md`

## Technical Context

Python 3.11+ stdlib runtime, pytest for tests. Existing ports only: `vcs.authorship`, `code_host.author_login`, `code_host.request_reviewers`. No new module, port, config key or dependency.

## Constitution Check

- Stdlib only, three-state exits: unchanged. A failed fallback lookup stays exit 2; the `min_reviewers >= 1` refusal stays exit 1.
- One behaviour, one function: the not-applicable rule lives in one helper in `obligations.py`, read by `_visibility`, which already serves the sweep, the day close and the merge policy.
- Test first: every change below has a failing test task before it.
- Simplicity: five small edits at the shared spots; no wrapper, no flag beyond the existing `shepherd.min_reviewers`.
- Security: no guard loses a check except the two the issue names (reviewer flag on create, reviewer and channel-post visibility), each gated on an owner-only config value. `config.toml` is already refused to agent tools.
- Design spec conflict (raised, not resolved silently): 4.1 says `gh pr create` refuses when "no reviewer named in the same action". This owner issue narrows that to `shepherd.min_reviewers > 0`. The design spec is not edited; the owner may amend 4.1 and 4.2.

## Changes

### 1. Config schema: `cli/wuwei/workspace.py`

Line 78: `"min_reviewers": (int, 1, 1)` becomes `(int, 1, 0)`. Default stays 1. `_validate` then reports `expected integer >= 0` for negatives.

### 2. Author fallback: `cli/wuwei/shepherd.py`, `_rank`

- Load `host = registry.load('code_host', config)` at the top of `_rank` (it is loaded at line 66 today; move it, do not load twice).
- Keep a per-call dict `resolved = {}` (email to login). For an email not in `mapping`: if not yet resolved, call `merge.read(host.author_login, repo['name'], email, root=root)['login']`; on any `ERRORS` exception raise `ValueError(f'shepherd.authors has no mapping for {email}: {exc}')` so the message still names the key and the email and the exit stays 2. Require the resolved login to be a non-empty `str` (else the same ValueError).
- Build `emails` for the verification loop from both `mapping` and `resolved`, so a fallback login selected as reviewer is verified by the existing loop instead of failing `reviewer needs a configured email`.
- Do not change window ranking, tie handling, lead handling, the `min_reviewers` refusal, the login regex or the verification loop.

### 3. Empty reviewer set on raise: `cli/wuwei/shepherd.py`, `raise_pr`

Lines 285-287: run `request_reviewers` and its verification only `if reviewers:`. `state.record_pr(..., reviewers=reviewers)` still records `[]`. `_rank` only returns `[]` when `min_reviewers = 0`, because it refuses below the minimum.

### 4. PR create guard: `cli/wuwei/guards/pr.py`, `create_check`

Lines 203-206: a present `--reviewer` must still be well formed; an absent one is refused only when `config['shepherd']['min_reviewers'] > 0`. Sketch:

```python
reviewers = values(found, '--reviewer', '-r')
named = reviewers and all(part.strip() and not part.strip().startswith('-')
                          for value in reviewers for part in value.split(','))
if not named and (reviewers or config['shepherd']['min_reviewers']):
    return 1, 'PR create requires a named --reviewer in the same command'
return gate_check(root, cwd, config)
```

Everything before it (repo, head and environment overrides, opaque create) and `gate_check` are unchanged.

### 5. Visibility rule: `cli/wuwei/obligations.py`

- New helper next to `_visibility`:

```python
def _not_applicable(config):
    """Visibility findings the owner's config makes impossible to owe."""
    reasons = {}
    if config['shepherd']['min_reviewers'] == 0:
        reasons['reviewer'] = reasons['channel-post'] = 'shepherd.min_reviewers = 0'
    elif config['adapters']['chat'] == 'none':
        reasons['channel-post'] = 'adapters.chat = "none"'
    return reasons
```

- `_visibility(ref, pr, reviews, data, me, directory, config)`: compute `skip = _not_applicable(config)`; `reviewer` is owed only when no reviewer is found and `'reviewer' not in skip`; `channel-post` is owed only when not posted and `'channel-post' not in skip`. The verdict check is unchanged.
- `evaluate`: pass `config` to `_visibility` (it is already loaded whenever there are refs), and after the OWED lines of an open PR print `f'{ref} NOT APPLICABLE {finding}: {reason}'` for each item of `_not_applicable(config)`. Counts are unchanged.

### 6. Merge policy call site: `cli/wuwei/merge.py`

Line 273: pass `config` (already in scope) as the new last argument to `obligations._visibility`. No other merge change.

### 7. Template and docs

- `templates/workspace/config.toml`: `min_reviewers` comment states that 0 is a solo owner (no reviewer requested, the owner merges). The `[shepherd.authors]` comment states that an unmapped email is resolved through the code host before refusing.
- `docs/site/configuration.md`: `shepherd.min_reviewers` row states `0` behaviour (raise and `gh pr create` need no reviewer; reviewer and channel-post obligations not applicable). `shepherd.authors` row states the code-host fallback. `adapters.chat` row states that with `none` the channel-post obligation is not applicable.

## Test fixtures that change (and why)

- `tests/test_shepherd.py` fixture `author_login` does a dict lookup that raises `KeyError` for unknown emails. Make it return `Result(2, reason='author login unavailable')` for unknown emails so `test_unmapped_author_names_email_and_key` exercises the new fallback failure path and still asserts the same message.
- Three existing fixtures use the default `adapters.chat = "none"` while asserting that `channel-post` is owed. A simulation of the chat-none rule against the current suite fails exactly these 14 tests, and no others:
  - `tests/test_obligations.py` fixture `case`: `test_visibility_table` rows `held`, `prose`, `no_url`, `bad_url`, `no_mentions`, `wrong_mentions`, `wrong_pr`; `test_channel_post_stays_owed_without_producer`; two rows of `test_mentions_cover_requests_or_fallback_authors`.
  - `tests/test_merge.py` fixture `case`: `test_policy_preconditions[visibility-channel-post]`.
  - `tests/test_watch.py::test_sweep_one_summary_with_counts_and_dead_watch` (3 rows; `visibility_owed == 2` is `channel-post` plus `verdict`).
  Each of these tests the channel-post rule with chat configured, so add `[adapters]\nchat = "slack"` to that fixture's config (for `test_watch.py`, append it inside the one test and merge it with the existing `scanner="ziran"` append into a single `[adapters]` table, since TOML rejects a repeated table). `registry.load` is monkeypatched in all three, and none of these paths loads the chat port. Do not change their expected values.
- `tests/test_stop.py::test_stop_table[visibility-1]` keeps exit 1 through the `verdict` obligation; no change.

## Must not change

- `shepherd.min_reviewers` default (1) and `tests/test_docs.py::test_shepherd_settings_are_visible_in_template_and_site`.
- The `min_reviewers >= 1` refusal in `_rank` and its message.
- `gate_check`, `_recorded_gates`, the other `create_check` refusals, `api_check`, merge, review and approval refusals.
- Reply obligations (`_replies`), the verdict obligation, `_check_empty_day`, the acknowledgement ledger.
- `post_review_request`, `_mentions`, `ping_gate`, `pr_actions` (see Deferred in the spec).
- `channel_posts` stays producer-only; nothing new is added to `state.RESERVED`.

## Verification

Run the targeted test file after each red and green step, then `python -m pytest -q` from the repository root. Check changed files for em-dashes and emojis.
