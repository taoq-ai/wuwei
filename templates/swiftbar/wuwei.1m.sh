#!/bin/sh
# SwiftBar plugin. Set WUWEI_WORKSPACE to the initialized workspace directory.
unknown() {
    printf '● | color=gray\n---\nUnknown\n'
    printf 'wuwei SwiftBar: %s\n' "$1" >&2
    exit 2
}

[ -n "${WUWEI_WORKSPACE:-}" ] || unknown 'WUWEI_WORKSPACE is not set'
command -v python3 >/dev/null 2>&1 || unknown 'python3 is unavailable'
[ -f "$WUWEI_WORKSPACE/.wuwei/executable" ] || unknown 'workspace executable pointer is missing'
wuwei_bin=$(cat "$WUWEI_WORKSPACE/.wuwei/executable") || unknown 'workspace executable pointer is unreadable'
[ -x "$wuwei_bin" ] || unknown 'workspace executable is unavailable'
cd "$WUWEI_WORKSPACE" || unknown 'workspace is unavailable'
python3 -P -c '
import json
import subprocess
import sys

try:
    result = subprocess.run([sys.argv[1], "status", "--json"],
                            capture_output=True, text=True, timeout=2)
    if result.returncode:
        raise ValueError(f"status exited {result.returncode}")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("status must be an object")
    pages = data["pages"]
    nudges = data["nudges"]
    if any(type(value) is not int or value < 0 for value in (pages, nudges)):
        raise ValueError("counts must be nonnegative integers")
except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
    print("● | color=gray\n---\nUnknown")
    print(f"wuwei SwiftBar: invalid status: {exc}", file=sys.stderr)
    sys.exit(2)

color = "red" if pages else "orange" if nudges else "green"
print(f"● | color={color}\n---\nPages: {pages}\nNudges: {nudges}")
' "$wuwei_bin"
