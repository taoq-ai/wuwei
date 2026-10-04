# Implementation Plan: read-only MCP tools by any word, unknown tools follow the posture, Slack writes take the draft path

**Branch**: `469-mcp-reads` | **Spec**: `specs/469-mcp-reads/spec.md` | **Research**:
`specs/469-mcp-reads/research.md` (the recorded tool lists and the verb review)

## Summary

One name classifier and one unmatched-tool helper in `cli/wuwei/guards/outward.py` replace
the inline first-word read test and the bare config hint; the Slack default in
`workspace.SCHEMA` gains the issue's verbs; the MCP guard's draft refusal names its channel.
Everything stays inside `_check`, the one function both outward guards route through.

## Technical Context

Python 3.11+, stdlib only. Files changed: `cli/wuwei/guards/outward.py`,
`cli/wuwei/workspace.py` (one string), `tests/test_outward.py`, `tests/test_hooks.py`,
`docs/site/security.md`, `docs/site/configuration.md`. No new module, no new dependency, no
new top-level import in the guard (`re` and `PAYLOAD` are already imported).

## Constitution Check

- I stdlib only: yes.
- II exits: reads 0; writes with no rule 2 with a reason; unknown 0 or 2 by the outward area;
  a name that cannot be printed safely 2 with the payload family; errors still fall to the
  existing `except` and exit 2.
- III one behaviour, one function: `tool_kind()` classifies, `_unmatched()` decides; both called
  from `_check` only.
- IV test first: every behaviour has a failing test task before its implementation task.
- V ponytail: reuse `_check`'s flow, `workspace.posture`, `workspace.day_dir`,
  `watch.records`, `state.append_event` and the default `nudge` tier in `signal.classify`.
  No new config key, no status or signal change, no read allowlist.
- VII security: the filled-in line is built only from a name matching
  `mcp__[A-Za-z0-9_-]+`, so it cannot carry a quote into the owner's shell. The approval
  tier stays owner-only. `outward.unknown_tool` is not a free event kind, so `wuwei event`
  refuses it (`commands/event.py` `FREE_KINDS`).

## Design

### 1. `cli/wuwei/guards/outward.py`: word lists and `tool_kind(tool)`

Module level, after `NATIVE_TOOLS`:

```python
# #469: name words of an unmatched MCP tool; tests pin both lists.
WRITES = frozenset((
    'send', 'post', 'reply', 'add', 'create', 'update', 'delete', 'remove', 'set', 'put',
    'patch', 'write', 'upload', 'schedule', 'publish', 'invite', 'kick', 'archive', 'join',
    'leave', 'react', 'pin', 'star', 'edit', 'move', 'assign', 'merge', 'close', 'open',
    'submit', 'approve', 'comment', 'message', 'dm',
    'save', 'notify', 'draft', 'respond', 'push', 'fork', 'request', 'dismiss', 'mark',
    'manage', 'run'))
LEADING = ('get', 'list', 'search', 'read', 'find', 'fetch', 'query', 'describe', 'view', 'lookup')
READS = frozenset(LEADING + (
    'history', 'replies', 'info', 'members', 'users', 'channels', 'conversations', 'threads',
    'permalink', 'profile', 'count', 'status', 'exists'))


def tool_kind(tool):
    """'read', 'write' or 'unknown' for an MCP tool by the words of its name (#469)."""
    server, _, name = tool[5:].rpartition('__')
    words = [word.lower() for word in re.split(r'[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])', name) if word]
    if words and (words[0] in LEADING
                  or len(words) > 1 and words[0] in server.lower() and words[1] in LEADING):
        return 'read'  # main's leading-read test first: get_message stays a read (spec A1)
    if WRITES.intersection(words):
        return 'write'
    return 'read' if READS.intersection(words) else 'unknown'
```

Split before lowercasing (main lowercases first, which hides camelCase). The leading test is
main's lines 88-94 unchanged in meaning.

### 2. `_check`: the first unmatched branch

Replace lines 86-95 (the inline `server, words, reads` block) with:

```python
            if isinstance(tool, str) and tool.startswith('mcp__'):
                if tool_kind(tool) == 'read':
                    return CLEAN, ''
```

The `elif` for non-MCP names stays as is.

### 3. `_check`: the second unmatched branch and `_unmatched`

Replace lines 106-107 with `return _unmatched(tool, root, config, policy)` under the same
`if not channels:`. New private function below `_check`:

```python
def _unmatched(tool, root, config, policy):
    """#469: a tool no rule matches, inside a workspace: reads pass, writes refuse with the
    config line, unknown names follow the outward area level in check_lint only."""
    from wuwei import workspace
    found = tool_kind(tool)
    if found == 'read':  # reached only when the scope's config differs from the cwd's
        return CLEAN, ''
    if not re.fullmatch(r'mcp__[A-Za-z0-9_-]+', tool):
        return UNRUN, f'outward: invalid MCP tool name; {PAYLOAD}'
    server = tool[5:].rpartition('__')[0].lower()
    line = (f"bin/wuwei config set outward.tool_patterns "
            f"'[{{pattern = \"{tool}\", channel = \"{server}\"}}]'")
    if found == 'write':
        return UNRUN, f'outward: no outward.tool_patterns rule matches write tool {tool}; run {line}, then retry'
    if policy is outward.check_tier:
        return CLEAN, ''
    name, levels = workspace.posture(config)
    if levels['outward'] == 'block':
        return UNRUN, f'outward: unknown MCP tool {tool}, not a read or a write by its name; if it writes, run {line}'
    if levels['outward'] == 'warn':
        from wuwei import state, watch  # Only now: watch stays off every other hook path.
        # ponytail: reads the day's events per call of an unknown tool; two racing first
        # calls may both record. Keep a per-day set in state if that shows in latency.
        if not any(row['kind'] == 'outward.unknown_tool' and row['payload'].get('tool') == tool
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
            state.append_event('outward.unknown_tool', {
                'tool': tool, 'posture': name,
                'reason': f'outward: unknown MCP tool {tool} passed under {name}; if it writes, run {line}'}, root)
    return CLEAN, ''
```

Notes for the builder:

- `server` is empty for a name without a second `__` (`mcp__x`); the line then has
  `channel = ""`, which `config check` refuses. Such a name cannot come from Claude Code;
  leave it.
- A non-MCP tool reaches `_unmatched` only in the scope-differs edge; it fails the name
  check and exits 2, as main's bare hint did.
- Under strict the hook adds `posture: outward = block (set security.areas.outward)`
  because the refusal comes from `check_lint` (spec A3). Do not move it to `check_tier`.
- Errors inside (`watch.records` on a corrupt stream, a failed append) raise `ValueError` or
  `OSError` into `_check`'s existing `except`: exit 2, fail closed, as `hook.posture` does
  when it cannot record a warning.

### 4. `_check`: the draft refusal names the channel

Replace the last line of the `try` (`return policy(inputs, root, config, channels)`) with:

```python
        result = policy(inputs, root, config, channels)
        if result == (FINDINGS, outward.APPROVAL_REQUIRED):
            return FINDINGS, (f'outward: channel {next(iter(channels))} needs owner approval; '
                              'write it as a draft for the owner to send')
        return result
```

`wuwei why last refusal` splits on the first `; ` and prints `rule: outward: channel slack
needs owner approval` and `fix: write it as a draft for the owner to send`. The ports
(`registry.outward_operation`, `pr_actions`) compare against `outward.APPROVAL_REQUIRED`
and do not pass through `_check`, so they are unchanged.

### 5. `cli/wuwei/workspace.py:187`: the Slack default

```python
{"pattern": r"mcp__.*slack.*__.*(send|post|reply|schedule|update|add_message|add_reaction|react|chat_post|delete|edit|upload|invite|kick|archive|pin|star).*", "channel": "slack"},
```

Verbatim from the issue. The Linear and GitHub defaults stay: research.md shows every
recorded read passes and every recorded write either matches (draft path) or is refused
with the config line.

### 6. Docs

- `docs/site/security.md`, after the `unparsed` paragraph: one paragraph. An MCP tool no
  `outward.tool_patterns` rule matches is a read when its name has a read word and no write
  verb (or starts with get, list, search, read, find, fetch, query, describe, view or
  lookup), a write when it has a write verb, and unknown otherwise. A write is refused with
  the `bin/wuwei config set outward.tool_patterns` line for that tool; an unknown tool passes
  under `observe` and `guarded` with one `outward.unknown_tool` nudge per tool per day and is
  refused under `strict` with the same line. Note that setting the list replaces the
  built-in rules.
- `docs/site/configuration.md:383`: the description adds "an unmatched MCP tool is a read,
  a write or unknown by the words of its name (see security)".

## What must not change

- `cli/wuwei/outward.py` (`APPROVAL_REQUIRED`, `check_tier`, `check_lint`, `classify`) and
  every adapter port.
- `cli/wuwei/commands/hook.py`, `cli/wuwei/guards/__init__.py` (`AREAS`, `OWNER_ONLY`,
  `MODULES`), `cli/wuwei/signal.py`, `cli/wuwei/commands/status.py`,
  `cli/wuwei/commands/event.py`.
- The order in `_check`: owner markers, the Bash branch, native tools, rule matching, then
  the name heuristic. Rules still win over names.
- The Linear, GitHub, Notion and Atlassian defaults.
- Top-level imports of `cli/wuwei/guards/outward.py` (`test_guard_modules_defer_heavy_imports`).

## Tests (all in-process except the import test)

`tests/test_outward.py`, reusing the `configured` fixture and `payload()`:

- `test_name_words` (table over `tool_kind`): the edge cases in spec Edge Cases, `get_message`
  read, `slack_readwrite` unknown, plus `assert 'add' in WRITES and 'history' in READS`.
- `test_recorded_server_tools`: the research.md lists as a module constant
  `RECORDED = {'slack': {...}, ...}`; for each tool, both guards under the fixture's guarded
  posture: reads `(0, '')`; writes either a draft (`check_tier` code 1 with `needs owner
  approval`) or code 2 with `config set outward.tool_patterns` and the tool name; no write
  gives `(0, '')` from `check_tier` and `check_lint` both.
- `test_probe_tools` (hook level, parametrized over `observe`, `guarded`, `strict`): set
  `[security] posture` in the fixture's config.toml, run `commands.hook.run` with each probe
  as in `test_hook_integration`; payload text `A technical claim.` and `channel_id` `C1`
  for the two writes. Expected exits: five reads 0; `conversations_add_message` and
  `slack_post_message` 2 with `a draft for the owner to send` and `slack` in stderr;
  `mcp__acme__frobnicate` 0 under observe and guarded, 2 under strict with the filled-in
  line.
- `test_unknown_tool_recorded_once`: guarded, two hook calls for `mcp__acme__frobnicate`, one
  `outward.unknown_tool` event with `tool`, `posture` `guarded` and the line in `reason`;
  `outward` area `off` records none; area `block` under guarded refuses.
- `test_unknown_tool_outside_workspace`: no workspace, `(0, '')`, no `.wuwei` created.
- `test_unmatched_write_names_the_line`: `mcp__acme__send_email` gives code 2 from both
  guards in every posture, the reason holds the exact line with `channel = "acme"`, and no
  reason anywhere contains `configure outward.tool_patterns for this write tool`.
- `test_invalid_mcp_name`: a payload with tool `mcp__acme__send'x` gives 2 and the payload
  family text.
- `test_why_shows_channel_and_draft`: after the hook refuses
  `mcp__slack__conversations_add_message`, `main(['why', 'last', 'refusal'])` prints a line
  with `channel slack` and one with `a draft for the owner to send`.

Existing rows to update in `tests/test_outward.py` (intended changes; keep every other row):

- `test_send_or_draft` line 130: assert `a draft for the owner to send` (drop `deliver as`).
- `test_real_mcp_write_names`: `mcp__slack__edit_message` 2 -> 1 (Slack default matches
  `edit`); `mcp__unknown__target_lookup` 2 -> 0 (read word); `mcp__unknown__anything`
  2 -> 0 (unknown passes `check_tier`); the code-2 assertion becomes `'config set
  outward.tool_patterns' in result[1] and tool in result[1]`.
- `test_service_prefixed_mcp_reads`: `mcp__x__slack_read_thread` 2 -> 0;
  `mcp__slack__slack_readwrite` 2 -> 0; `mcp__x__readwrite` 2 -> 0 (`check_tier` passes
  unknown names).

Found while building (intended consequences, not in the first draft of this plan):

- `tests/test_outbound.py` `test_guard_tiers_and_bypasses`: the draft substring becomes
  `a draft for the owner to send` (same change as `test_send_or_draft`).
- `tests/test_signal_status.py` `test_emitted_kinds_have_intended_tiers`: the new kind
  `outward.unknown_tool` is listed with tier `nudge`; `signal.py` itself is unchanged.
- `docs/site/security.md`: the docs reader test refuses "the owner" in pages, so the new
  paragraph says "a draft you send yourself".

`tests/test_hooks.py`: `test_hook_imports_no_unused_stdlib` gains a third case, `mcp-read`:
inside a workspace, the bash payload with `tool_name` `mcp__slack__conversations_history`
and `tool_input` `{"channel": "C1"}`; deny is the workspace set plus `wuwei.watch`. On main
it fails on the return code (the hook refuses the read with exit 2); after the classifier
lands it must pass with the deny set unchanged, which is the "import graph unchanged" check.
If main's MCP path already loads a module in the workspace deny set, record that in the
build notes and keep only `wuwei.watch` added to what main loads; do not widen the set.

## Risks

- Substring alternations in the Slack default (`pin`, `star`, `react`, `edit`) can match a
  read such as `pins_list`; none is in the recorded lists. Tighten with a test if a real
  server shows one.
- Under guarded an unknown write (`transitionJiraIssue`) now passes with a nudge where main
  refused it. This is the issue's posture design; strict keeps refusing.
