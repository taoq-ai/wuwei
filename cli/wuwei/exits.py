"""Shared command, guard, sweep, and adapter exit statuses."""

CLEAN, FINDINGS, UNRUN = 0, 1, 2

# d2 families (#362): an internal invariant names its family's next step after its own text,
# for example raise ValueError(f'invalid decision ledger; {DAMAGED}').
DAMAGED = ('a WUWEI record failed its consistency check, so nothing was written; run '
           'bin/wuwei doctor, which names the file and its fix (bin/wuwei state recover for state.json)')
PLAN_JSON = ('the plan JSON misses or misshapes this field; compare it with bin/wuwei plan '
             'template, which shows every field, and fix the one named here')
ADAPTER_DATA = ('an adapter or seat runtime returned data WUWEI cannot read, so the step is '
                'unmeasured and nothing was recorded; retry once, then run bin/wuwei doctor, '
                'which tests the adapter')
PAYLOAD = ('Claude Code sent a hook payload this WUWEI version cannot read, so nothing was '
           'done; run bin/wuwei doctor, then update Claude Code or WUWEI')
RACE = ('another session changed this record while the command ran, so nothing was '
        'written; run the same command again')
SYMLINK = ('links are refused so a write cannot be redirected; replace the link with a '
           'regular file (bin/wuwei doctor names it)')
FAMILIES = ('DAMAGED', 'PLAN_JSON', 'ADAPTER_DATA', 'PAYLOAD', 'RACE', 'SYMLINK')
