# Implementation Plan: an owner/repo#N reference in a brief never fails registration with Not Found

**Branch**: `740-brief-issue-ref` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

The #606 rule ("a `pr` lookup that failed with HTTP 404 means not a pull request") moves from
an inline regex in `outward._pr_context` into one helper, `references.not_found(reason)`.
`brief.write`'s counterpart loop calls the same helper: a counterpart read that fails becomes
one `Warning:` header line instead of a refusal, except a non-404 failure under `strict`,
which still refuses. No port, adapter or fake changes.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. Tests are in-process with the recording fake
code host (`tests/fakes/code_host.py`), the existing `day` fixture in `tests/test_brief.py`
and the `configured` fixture in `tests/test_outbound.py`. No network, no `gh`.

## Constitution Check

- I (stdlib): unchanged.
- II (exits, fail closed): a failed read is never reported as a pull request head; the
  warning line names the reason. Under `strict` a non-404 failure stays exit 2.
- III (one behaviour, one function): the not-found rule lives in `references.not_found`
  only; `brief` and `outward` both call it.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new port operation (spec A1), no new config key, no change to `pr state`
  (spec A2). One helper of one line, one `try` in `brief.write`.
- VII (security, posture): below `strict` the brief no longer refuses on optional evidence;
  under `strict` the refusal for an unreadable counterpart stays (design 9.1).
- Design spec: no conflict; no 9.2 row (spec A5).

## Design

### 1. `cli/wuwei/references.py` (shared helper)

```python
def not_found(reason):
    """#606, #740: a code host lookup that answered HTTP 404 (an issue number, or no access)."""
    return '(HTTP 404)' in str(reason)
```

`str(reason)` accepts both a `Result.reason` string and the `ValueError` `brief.read`
raises. The match text is the one `github._run` already produces and
`tests/test_code_host.py::test_pr_not_found_names_the_404` pins.

### 2. `cli/wuwei/outward.py`, `_pr_context` (lines 304 to 308)

Replace `re.search(r'\(HTTP 404\)', str(result.reason))` with
`references.not_found(result.reason)` (import `from wuwei import references` at the call
site, as the function already imports `registry` locally). Nothing else in the condition
changes: still only `result.exit == UNRUN`, a bare reference (`match[2]`) and no
`pull_number`. Update the `#606` comment to name the helper.

### 3. `cli/wuwei/brief.py`, `write` (lines 528 to 532)

Read the posture once before the loop and wrap the existing read:

```python
strict = workspace.posture(config)[0] == 'strict'
for repo in config['repos']:
    for other in sorted(set(re.findall(re.escape(repo['name']) + r'#[0-9]+', body))):
        if other != pr:
            host = host or registry.load('code_host', config)
            try:
                header.append(f'Counterpart {other} head (no-cache): {json.dumps(read(host.pr, other, root=root))}')
            except ValueError as exc:
                # #740: a ticket is an issue, which the pulls endpoint 404s on (#606); a
                # reference is optional evidence, so it never refuses below strict.
                if strict and not references.not_found(exc):
                    raise
                header.append(f'Warning: {other} is no pull request the host could read ({exc}); '
                              'kept as a reference')
```

`from wuwei import references` joins the existing top-level import line in `brief.py`
(`registry, security, sessions, state, workspace`). `Refused` is a `ValueError` subclass but
`read` never raises it, so the `except` changes nothing for policy refusals.

### What must not change

- The `--pr` read (`PR head (no-cache)`, line 506 to 507): still refuses on any failure.
- The successful counterpart line, byte for byte (FR-004).
- `adapters/code_host/github.py`, `adapters/code_host/none.py`, `tests/fakes/code_host.py`,
  `cli/wuwei/registry.py` `PARAMETERS`: no new operation (FR-006).
- `pr_actions.evaluate` and `pr state` (spec A2).
- The #606 outward table in `tests/test_outbound.py`: every row keeps its result (FR-005).
- The redaction of the adapter reason (`github._run`); `brief` adds no response body.

### Tests

`tests/test_brief.py`, using the existing `day` fixture with a `[[repos]]` row
(`name = "acme/widget"`, `path = "tree"`, `default_branch = "main"`) written to
`.wuwei/config.toml` as `test_repo_default_branch` does:

- 404 for `acme/widget#24` (the exact `github.pr` reason string): exit 0; brief file has
  `Warning: acme/widget#24 is no pull request the host could read (` and the body
  `Ticket: acme/widget#24`; a `brief written` event; with `tickets` set in state for `X`
  (`{'id': 'acme/widget#24'}`), `why.live(root, 'X', ...)` or
  `main(['why', 'X', '--json'])` shows the ticket.
- Successful counterpart (`Result(0, {...})`): the `Counterpart acme/widget#7 head (no-cache):`
  line is present with the JSON, and no `Warning:` line.
- HTTP 401 reason: exit 0 with the warning under the default posture; with
  `[security]\nposture = "strict"` in config, exit 2, the reason on stderr, no brief file and
  no `brief written` event.
- 404 under `strict`: exit 0 with the warning line.

`tests/test_outbound.py`: the existing #606 parametrized test is the regression check for the
outward call site; no new outward test. One direct unit assertion for `references.not_found`
(404 reason true; 401 reason false; a `ValueError` carrying the 404 reason true) goes into
`tests/test_brief.py` next to the brief tests, so no new test file.

## Files

| File | Change |
|---|---|
| `cli/wuwei/references.py` | add `not_found(reason)` |
| `cli/wuwei/outward.py` | `_pr_context` calls `references.not_found` |
| `cli/wuwei/brief.py` | counterpart read: warning below strict, 404 never refuses |
| `tests/test_brief.py` | the tests above |

No `research.md`, `data-model.md`, `contracts/` or `quickstart.md`: no new entity, port or
command surface.
