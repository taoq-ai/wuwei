# CLI contract

Invoke `<plugin root>/bin/wuwei [arguments]`.

The shim unsets PYTHONEXECUTABLE and execs `python3 -I -P -S` (isolated mode, no `site`).
Isolated mode ignores PYTHON* environment settings except PYTHONEXECUTABLE on macOS,
excludes user site-packages, and implies -P. Passing -P explicitly enforces Python 3.11+:
older interpreters reject it with usage exit 2. `-S` (#346) skips the `site` import: the
stdlib-only CLI needs no site-packages or `.pth` files. PATH remains trusted for interpreter selection.
It explicitly prepends `<plugin root>/cli` and `<plugin root>` to sys.path, removes
those bootstrap arguments, and runs the installed wuwei module as __main__ via runpy.
The working directory and inherited import paths cannot shadow plugin or stdlib modules.
Arguments (including spaces and quotes), stdin hook payloads, and exit statuses pass
through unchanged. Missing python3 or the plugin's cli/wuwei directory reports exit 2.

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

Dispatch loads the module matching the typed command, mapping hyphens to underscores
(for example, `scan-probe` loads `scan_probe.py`). If that module is absent or does not
register the typed command, dispatch falls back to full discovery. Top-level help also
uses full discovery; `--version` imports no command modules.
