#!/bin/sh
# The config-door probe, part (b), run by hand: each Bash case in cases.tsv (written by probe.py report) runs under real
# bash in a fresh copy of a workspace. A case reaches the door when it changed .wuwei/config.toml or .wuwei/plan.json,
# or ran the wuwei stub with a call that writes (wuwei config <key>, wuwei plan add, done, park, ...). A hole is a case
# that reached the door while the head's guard passes it for a seat. sudo -D and env -C are stubs on PATH that change
# folder and run the rest, so no case needs root or a GNU env. The wuwei stub stands on PATH, behind python3 -m wuwei
# and behind .wuwei/executable, and only logs; it never writes the plan or the config.
# Usage: sh specs/config-door/run.sh <a folder that does not exist yet>; it deletes the folder when done.
set -u
[ $# -eq 1 ] && [ ! -e "$1" ] || { echo "usage: sh $0 <a folder that does not exist yet>" >&2; exit 2; }
cases=$(cd "$(dirname "$0")" && pwd)/cases.tsv
mkdir -p "$1/bin" "$1/py/wuwei" && out=$(cd "$1" && pwd) || exit 2
printf '#!/bin/sh\n[ "$1" = -D ] && { cd "$2" || exit 1; shift 2; }\nexec "$@"\n' > "$out/bin/sudo"
printf '#!/bin/sh\n[ "$1" = -C ] && { cd "$2" || exit 1; shift 2; }\nexec /usr/bin/env "$@"\n' > "$out/bin/env"
cat > "$out/bin/wuwei" <<'STUB'
#!/bin/sh
# wuwei's own argv rules: config <key> [<value>] sets a key; plan [options] <action> writes for these actions
[ "${1-}" = -- ] && shift
kind=read
case "${1-}" in
config) [ $# -gt 1 ] && kind=write ;;
plan) shift
    while [ $# -gt 0 ]; do
        case $1 in
        --reason) shift 2 ;;
        -*) shift ;;
        add|park|drop|done|restore|run|session|tier|approve) kind=write; break ;;
        *) break ;;
        esac
    done ;;
esac
echo "$kind" >> "$PROBE_LOG"
STUB
printf 'import os, sys\nos.execv(%s, [%s, *sys.argv[1:]])\n' "'$out/bin/wuwei'" "'$out/bin/wuwei'" > "$out/py/wuwei/__main__.py"
: > "$out/py/wuwei/__init__.py"
chmod +x "$out/bin/sudo" "$out/bin/env" "$out/bin/wuwei"
total=0 reached=0 holes=0 tab=$(printf '\t')
while IFS="$tab" read -r id verdict command; do
    total=$((total + 1)) dir=$out/case-$id
    mkdir -p "$dir/.wuwei" "$dir/tool" "$dir/x/.wuwei" "$dir/x/tool"
    printf 'repos = ["acme/app"]\n' > "$dir/.wuwei/config.toml"
    printf '{"items": []}\n' > "$dir/.wuwei/plan.json"
    printf 'src\n' > "$dir/src.txt"
    for d in "$dir" "$dir/x"; do printf '%s\n' "$out/bin/wuwei" > "$d/.wuwei/executable"; ln -s "$out/bin/wuwei" "$d/tool/wuwei"; done
    cp "$dir/.wuwei/config.toml" "$dir/config.orig" && cp "$dir/.wuwei/plan.json" "$dir/plan.orig"
    (cd "$dir" && PATH="$out/bin:$PATH" PYTHONPATH="$out/py" PROBE_LOG="$dir/ran" bash -c "$command") </dev/null >/dev/null 2>&1
    if ! cmp -s "$dir/config.orig" "$dir/.wuwei/config.toml" || ! cmp -s "$dir/plan.orig" "$dir/.wuwei/plan.json" \
            || grep -q write "$dir/ran" 2>/dev/null; then
        reached=$((reached + 1))
        [ "$verdict" = pass ] && holes=$((holes + 1)) && echo "HOLE $id: $command"
    fi
    rm -rf "$dir"
done < "$cases"
echo "cases $total, reached the door (changed a file or ran a writing wuwei call) $reached, holes $holes"
rm -rf "$out"
