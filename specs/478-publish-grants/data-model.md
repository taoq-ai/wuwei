# Data model: grants

## Day state: `grants` (producer-owned)

Today's `state.json`, keyed by the decision id of the card.

```json
"grants": {
  "D-3": {
    "action": "deploy",
    "target": "repo:fixture-org/app",
    "rule": "deploy.workflows",
    "command": "gh workflow run 'Deploy Production' -R fixture-org/app --ref main",
    "item": "fix-login",
    "seat": "wuwei:builder",
    "planned": false,
    "answered": null,
    "spent": false
  }
}
```

| Field | Written by | Values |
|---|---|---|
| `action` | `grants.ask` | `deploy`, `release`, `publish` |
| `target` | `grants.ask` | `repo:<org>/<name>` |
| `rule` | `grants.ask` | the deploy rule, or `planned` |
| `command` | `grants.ask` | redacted one-line command; `null` for a planned row |
| `item`, `seat` | `grants.ask` | the claimed item or `null`; the agent type or `main session`; `null` seat for a planned row |
| `goal` | `grants.plan` | planned rows only |
| `planned` | `grants.ask` | `true` when written by `plan propose` |
| `answered` | `owner_outcome` only | `null`, then one option id: `keep`, `once`, `today`, `always` (refusal card) or `today`, `ask`, `keep` (planned card) |
| `spent` | `grants.gate` (`once` only) | `false`, then `true` on the one use |

Transitions: `answered` goes from `null` to an option once (`owner_outcome` refuses a second
answer, as for every decision). `spent` goes from `false` to `true` once, under the state lock,
only for `answered == 'once'`.

A row grants:

- `today`: while `close_requested` is false.
- `once`: while `spent` is false.
- `always`: never from the row; the `[grants]` line grants, outside strict.
- `keep`, `ask`, `null`: never.

## Config: `[grants] standing`

```toml
[grants]
standing = [
  {action = "deploy", target = "repo:fixture-org/app", scope = "always", decision = "D-3", date = "2026-10-04"},
]
```

`target` may hold glob characters (`repo:fixture-org/*`); matching is `fnmatchcase(target,
line.target)` with the same `action`. Written only by `owner_outcome` for an `always` answer
(owner edit frame, the answer is the confirmation) or by the owner in a host terminal; removed
by `wuwei grants revoke <n>` (1-based, in file order). Ignored under strict.

## Events

| Kind | Payload |
|---|---|
| `grant.asked` | `id`, `action`, `target`, `planned` (with the state write) |
| `grant.used` | `decision`, `action`, `target`, `scope`, `session`, `item` |
| `grant.revoked` | `decision`, `action`, `target` |

The answer itself is the existing `decision.decided` event.
