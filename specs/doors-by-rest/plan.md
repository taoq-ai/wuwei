# Implementation Plan: every code-host route to a door meets that door

**Branch**: `claude/doors-by-rest` | **Spec**: `specs/doors-by-rest/spec.md`

## Summary

Replace the merge regex and `GUARDED_API` in `guards.gh_command` with one route table read after a
small `gh api` argument reader that follows gh's flag parser. Send REST creates through the
`gh pr create` path, refuse REST branch writes, repository deletes and door mutations in GraphQL,
read `gh pr new` as `gh pr create`, and add the MCP file tools to `guards.DOORS` under `push`.

## Technical Context

Python 3.11 stdlib, pytest. Runtime is 2,960 of 3,000 lines on main 40a966b; the estimate is +18
and the cap leaves +40.

## Constitution Check

- I. Stdlib only: yes, `re`, `json` and `pathlib`.
- II. Evidence over steps: the create and merge doors read the same evidence; only more routes
  reach them.
- III. An auditor: no new door. New refusals cover branch writes and merges that skip a PR.
- V. Test first: every new test ran red before the change.
- VI. Budgets: no config key; runtime +36 lines, under the cap.

## Design

- `cli/wuwei/guards.py`
  - `API`: (endpoint pattern, methods, door) rows for create, merge, push, delete and rules,
    matched with `re.fullmatch` on the normalized endpoint. `REPO` is `repos/([^/]+/[^/]+)` so an
    unfilled `{owner}/{repo}` still reaches the merge door, which then cannot read the PR and
    stays shut.
  - `API_FLAG` and `_api(args, cwd)`: read `--method`, `--field`, `--raw-field`, `--input`,
    `--header`, `--jq`, `--template`, `--preview`, `--hostname`, `--cache` with `=` or a separate
    value, and short `-X -f -F -H -q -t -p` with an attached, `=`-joined or separate value after
    any `-i`. The last method wins. `-F k=@file` reads the file; `--input` adds head, base and
    body from its JSON. POST when a field or `--input` is given and no method is. The endpoint
    loses `https://api.github.com`, a leading `/`, trailing `/` and a query; `{owner}` and
    `{repo}` come from `origin(cwd)`.
  - `MUTATIONS`: the GraphQL mutation names refused, matched as whole words in the `query` field.
  - `PUSHED`: the push refusal text, shared by `git_push`, the REST push row and the MCP tools.
  - `gh_command`: `gh pr create` and `gh pr new` build (repo, head, base, body); the api branch
    builds the same tuple for the create row; one block calls `create_door` and the PR standard
    note.
  - `DOORS['push']` and a `pre_tool` branch: the MCP file tools are refused when their branch is
    empty or a default branch, after the leak check.
- `charters/shepherd.md` Raise 1 names the REST create route; `bin/wuwei agents build`.
- `SECURITY.md`: a paragraph on what the `gh api` reader covers and what it does not.
- `tests/fixtures/routes.json`: 15 routes from the acceptance and the charter.
- Re-vendor `.claude/` with `setup.vendor('.')`.

## Verification

- Each spelling the reader claims was sent by gh 2.89.0 to a logging HTTP proxy
  (`GH_HOST=github.localhost`, `HTTP_PROXY` at a local server) and the method, path and body gh
  sent were compared with what `_api` reads.
- A main-versus-head run of `guards.bash` over 153 commands (the corpus, door, leak, infra,
  ledger, hook and every `gh api` route the runtime, charters and skills use).

## Rollback

Revert the PR's single commit; no data, config or ledger change, so the revert restores main's
reader. A seat that adopted the REST create route goes back to `gh pr create`.
