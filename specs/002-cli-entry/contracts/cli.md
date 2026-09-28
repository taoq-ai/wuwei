# CLI contract

Invoke `PYTHONPATH=<plugin root>/cli python3 -P -m wuwei [arguments]` or
`<plugin root>/bin/wuwei [arguments]`.

- `--version`: manifest version and newline on stdout, exit 0.
- `--help`: argparse help on stdout, exit 0.
- Missing command, unknown command, invalid arguments: diagnostic on stderr, exit 2.
- Command result: integer 0 clean, 1 findings, 2 could not run.
- Command exceptions and invalid results: command name and reason on stderr, exit 2.

Modules whose names start with `_` are helpers and are skipped during discovery.
Each other module in `cli/wuwei/commands/` exposes `register(subparsers)`. It adds a parser
and sets `func` to a callable accepting the parsed argparse namespace and returning
one of `wuwei.exits.CLEAN`, `FINDINGS`, or `UNRUN`. Commands returning UNRUN print their
own reason. New modules require no shared registry edit. No demo commands ship.
