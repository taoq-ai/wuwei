#!/bin/sh
# The config-door probe, part (b), run by hand: each Bash case in cases.tsv (written by probe.py report) runs under real
# bash in a fresh copy of a workspace, and the runner reports which cases changed .wuwei/config.toml or .wuwei/plan.json.
# A hole is a case that changed a file while the head's guard passes it for a seat. sudo -D and env -C are stubs on PATH
# that change folder and run the rest, so no case needs root or a GNU env.
# Usage: sh specs/config-door/run.sh <a folder that does not exist yet>; it deletes the folder when done.
set -u
[ $# -eq 1 ] && [ ! -e "$1" ] || { echo "usage: sh $0 <a folder that does not exist yet>" >&2; exit 2; }
cases=$(cd "$(dirname "$0")" && pwd)/cases.tsv
mkdir -p "$1/bin" && out=$(cd "$1" && pwd) || exit 2
printf '#!/bin/sh\n[ "$1" = -D ] && { cd "$2" || exit 1; shift 2; }\nexec "$@"\n' > "$out/bin/sudo"
printf '#!/bin/sh\n[ "$1" = -C ] && { cd "$2" || exit 1; shift 2; }\nexec /usr/bin/env "$@"\n' > "$out/bin/env"
chmod +x "$out/bin/sudo" "$out/bin/env"
total=0 changed=0 holes=0 tab=$(printf '\t')
while IFS="$tab" read -r id verdict command; do
    total=$((total + 1)) dir=$out/case-$id
    mkdir -p "$dir/.wuwei" "$dir/x"
    printf 'repos = ["acme/app"]\n' > "$dir/.wuwei/config.toml"
    printf '{"items": []}\n' > "$dir/.wuwei/plan.json"
    printf 'src\n' > "$dir/src.txt"
    cp "$dir/.wuwei/config.toml" "$dir/config.orig" && cp "$dir/.wuwei/plan.json" "$dir/plan.orig"
    (cd "$dir" && PATH="$out/bin:$PATH" bash -c "$command") </dev/null >/dev/null 2>&1
    if ! cmp -s "$dir/config.orig" "$dir/.wuwei/config.toml" || ! cmp -s "$dir/plan.orig" "$dir/.wuwei/plan.json"; then
        changed=$((changed + 1))
        [ "$verdict" = pass ] && holes=$((holes + 1)) && echo "HOLE $id: $command"
        echo "changed $id (seat at head: $verdict): $command"
    fi
    rm -rf "$dir"
done < "$cases"
echo "cases $total, changed a file $changed, holes $holes"
rm -rf "$out"
