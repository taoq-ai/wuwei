# Spec: a seat's command naming the records passes only for a reader (records-writers)

## In my words

The records rule in `guards.bash` lists writer programs (`tee`, `cp`, `rm`, `sed -i` and a few
more). Any other program that writes passes. At 8fc0d49b, 96 of 104 seat writer x target shapes
passed against `.wuwei/config.toml`, `.wuwei/plan.json`, the ledger and the canary. SECURITY.md
lists several of them as known open. After this change, a seat's Bash segment whose words name one
of those records, or `.wuwei` itself, is refused unless its program is on a reader list. The
owner's session (no `agent_type`) keeps today's verdicts.

## Acceptance scenarios

1. A seat runs any of the 24 probed writer shapes (install, rsync, perl -pi, ruby -i, node -e,
   awk -i inplace, patch, ditto, ex, vim, sort -o, shuf -o, curl -o, wget -O, tar, unzip,
   git checkout, git restore, git show --output, openssl -out, xxd -r, split, scp, uniq) against
   config.toml, plan.json, the ledger or the canary: refused.
2. A seat reads them with cat, head, tail, grep, jq, wc, diff or wuwei plan show: passes.
3. The owner's session runs the same writes: same verdict as today.

Outside: paths built at run time, symlinks, the harness sandbox (#309).

## How this fails

1. A seat's real read with a program off the list (`sed -n`, `git log -- .wuwei/plan.json`,
   `sudo cat`) is refused and the seat stalls. The refusal names the readers, so the seat can switch.
2. A record named only at run time (`xargs rm` reading a file list, a joined string) still passes.
   This is out of scope, and SECURITY.md says so.
3. A word that mentions a record in prose (`git commit -m ".wuwei/plan.json"`) is refused. Seats
   pass long text by `-F` or `--body-file`.
