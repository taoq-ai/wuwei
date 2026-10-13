# Research decisions

- Decision: add the narrow fallback in protect_state.check_bash. Rationale: every
  Bash guard invocation routes there and the generic UNPARSED reason is explicitly
  downgraded by hook.enforce. Alternative rejected: broad fail-closed parsing would
  reverse #839 for unrelated calls; extending shell substitution parsing grows scope.
- Decision: inspect options after wrapper normalization. Existing normalize unwraps
  sh -c, env and xargs; _wuwei_action recognizes bin paths and Python module launchers.
  No independent shell parser is needed.
- Decision: rely on the guard instead of authenticating parent names. The shipped
  hooks/hooks.json, bin/wuwei and commands/hook.py supply no private runner signal.
  Environment and payload fields are caller-controlled; parent identity is not an
  authenticated event channel. The task expressly allows documenting this fallback.
- Decision: preserve full-pipeline workspace scoping. A root is not always found
  from cwd when an explicit --workspace selects another directory; detection must
  not require a second root discovery after the dispatcher has established scope.

- Review finding: Python options with separate values caused _wuwei_action to
  stop before -m wuwei. Reproduced four forms in full-pipeline tests before fixing
  the existing option walk. One fix round, followed by a delta review.
