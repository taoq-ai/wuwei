# Plan: an owner setting allows admin-bypass merges (#1290)

- `cli/wuwei/ws.py`: `allow: []` in `DEFAULTS`; `config` keeps only a list of strings; `write_config`
  omits an empty `allow`. `set_config` already parses a comma list for a list key.
- `cli/wuwei/guards.py` `gh_command`: the `--admin` deny applies only when `admin-merge` is not in
  `allow`; otherwise the call falls through to `merge_door`, which holds every safety gap.
- `cli/wuwei/evidence.py` `gaps`: the unnamed merge-block gap is raised only when `admin-merge` is
  not in `allow`.
- Docs: constitution VI (seven keys, 3.6.0), design 11 and principle 8, reference (command and key
  table), philosophy, README, SECURITY, `charters/_way.md` (the refuses line), the CLI help and the
  upgrade message.
- Vendored copies under `.claude/wuwei/` match the tree.
- Runtime: +1 line (3,950 of 4,000).
- Seat refusal of `wuwei config allow ...` and of config.toml edits is the existing config door; a
  corpus line is added to `OWNED_WRITES`.
