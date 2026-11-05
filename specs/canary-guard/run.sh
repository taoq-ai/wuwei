#!/usr/bin/env bash
# The canary-guard probe, part (b), for the owner to run: each Bash case of cases.tsv (probe.py report writes it) runs
# under real bash in its own case folder below <scratch folder>, with a sudo stub on PATH that honours -D and runs the
# rest unprivileged. A case "ran the door" when .wuwei/canary changed (content, mode, type or presence); a hole is such
# a case the head passes. Case folders are made and removed under <scratch folder>.
#
#   bash specs/canary-guard/run.sh specs/canary-guard/cases.tsv <scratch folder>
set -uo pipefail
tsv=$1 base=$2
mkdir -p "$base/bin"
printf '#!/bin/sh\nif [ "$1" = -D ]; then cd "$2" || exit 1; shift 2; fi\nexec "$@"\n' > "$base/bin/sudo"
chmod +x "$base/bin/sudo"
look() { (cd "$1" && ls -l .wuwei/canary 2>&1; cat .wuwei/canary 2>&1); }
total=0 ran=0 holes=0 named=0
while IFS=$'\t' read -r id verdict door json; do
  case_dir="$base/case-$id"
  rm -rf "$case_dir"
  mkdir -p "$case_dir/.wuwei/x%2F" "$case_dir/.wuwei/x" "$case_dir/x%2F" "$case_dir/x" "$case_dir/src"
  printf 'wuwei-canary-probe\n' > "$case_dir/.wuwei/canary"
  : > "$case_dir/a.txt"
  before=$(look "$case_dir")
  command=$(python3 -I -c 'import json, sys; print(json.loads(sys.argv[1]))' "$json")
  (cd "$case_dir" && PATH="$base/bin:$PATH" bash -c "$command" < /dev/null > /dev/null 2>&1)
  total=$((total + 1))
  if [ "$before" != "$(look "$case_dir")" ]; then
    ran=$((ran + 1))
    [ "$door" = 0 ] && named=$((named + 1)) && echo "a %xx name reached the canary $id: $command"
    [ "$verdict" = pass ] && holes=$((holes + 1)) && echo "hole $id: $command"
  fi
  chmod -R u+rwx "$case_dir" 2> /dev/null
  rm -rf "$case_dir"
done < "$tsv"
echo "generated $total; ran the door (the canary changed) $ran; holes (changed while the head passes) $holes; %xx names that reached it $named"
