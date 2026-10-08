"""#579: the day pace (design 5.2, Pace): one value per day that sets the inputs #567 and #528
already read (tier, depth, checks, seats), never a floor or who decides."""

PACES = ('careful', 'steady', 'fast')  # slowest first: the slower pace is the lower index


def current(data, config):
    """The day's pace, else the workspace default."""
    return data.get('pace') or config['pace']['default']


def label(answer, recommended):
    """The pace a gate card answer names: Approve is the recommendation."""
    text = str(answer).strip().removesuffix(' (Recommended)').strip()
    if text == 'Approve':
        return recommended
    text = text.removeprefix('Approve at ').strip()
    if text in PACES:
        return text
    raise ValueError(f'unknown pace answer {answer!r}; pass Approve, Approve at <pace> or one of '
                     'careful, steady or fast. Change something asks the separate questions')


def adjust(pace, tier, guard, flagged, measured):
    """(tier, depth, reasons) for one item. guard: the reason when the diff touches guard code or
    a trust path, else None; flagged: a lead flag or a FULL track; measured: the diff was read.
    Never returns a tier below its input (invariant I15)."""
    if pace == 'steady':
        return tier, tier, []
    if guard:
        return 'full', 'full', [f'pace {pace}: {guard}']
    if pace == 'careful' and tier == 'light':
        return 'standard', 'standard', ['pace careful']
    if pace == 'fast' and tier == 'standard' and measured and not flagged:
        return 'standard', 'light', ['pace fast: light depth']
    return tier, tier, []


def seats(pace, limits):
    """(cap, bound, hold): careful plans CAP minus one; fast holds every launch while the load
    average is at or over the core count. Neither refuses: the launch guard never reads the pace."""
    cap, bound = limits['cap'], limits['bound']
    if pace == 'careful':
        return max(1, cap - 1), 'pace careful', None
    load, cores = limits.get('load'), limits.get('cores')
    if pace == 'fast' and load is not None and cores and load >= cores:
        return cap, 'load', (f'host load {load:.1f} at or over {cores} cores (pace fast); the next seat '
                             f'launches when the load falls below {cores}')
    return cap, bound, None


# ponytail: minutes per depth before any cycle is measured (#567's targets, full doubled).
FALLBACK_MINUTES = {'light': 60, 'standard': 180, 'full': 360}


def predict(candidate):
    """The tier a candidate is expected to run at: the lead's, else full on a FULL track."""
    return candidate.get('tier') or ('full' if candidate.get('track') == 'FULL' else 'standard')


def _guard(candidate, trust_paths):
    """The step-zero reason when the candidate's paths touch guard code or a trust path (#567)."""
    from wuwei import dispatch
    run, reason = dispatch.step_zero('standard', candidate.get('paths', []), trust_paths)
    return reason if run else None


def _depth(pace, candidate, trust_paths):
    flagged = candidate.get('track') == 'FULL' or any(candidate.get('flags', {}).values())
    return adjust(pace, predict(candidate), _guard(candidate, trust_paths), flagged, True)[1]


def _last_suite(root, config):
    """Seconds of the newest recorded run of a configured repos.tests command, else None."""
    from wuwei import metrics, watch
    commands = {repo['name']: repo['tests'] for repo in config['repos'] if repo.get('tests')}
    for day in watch.days(root) if commands else ():
        data = metrics._state(day) or {}
        for name, command in commands.items():
            seconds = data.get('fast_checks', {}).get(name, {}).get(command, {}).get('seconds')
            if type(seconds) in (int, float):
                return seconds
    return None


def host_line(root, limits, config):
    """The host part of the advice: cores, load average and the last suite duration."""
    try:
        seconds = _last_suite(root, config)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        seconds = None
    load = limits.get('load')
    return (f"Host {limits.get('cores') or 'unmeasured'} cores, "
            f"load {'unmeasured' if load is None else f'{load:.1f}'}, "
            f"last suite {'unmeasured' if seconds is None else f'{round(seconds / 60)} min'}")


def advise(root, config, data, goal_list, limits, now):
    """#579: the recommended pace from the queue, the host and the budget, the input that binds
    it and what would unlock a faster one. The owner's default is shown, never overridden; the
    budget only advises against a pace, it never changes it."""
    from datetime import date, timedelta
    from wuwei import metrics, workspace
    candidates = data['candidates']
    trust = [path for repo in config['repos'] for path in repo['gates']['trust_paths']]
    guards = [row['id'] for row in candidates if _guard(row, trust)]
    try:
        medians = metrics.cycle_by_tier(metrics.cycles(root))
    except (OSError, ValueError, KeyError, TypeError):
        medians = metrics.UNMEASURED
    medians = {} if medians == metrics.UNMEASURED else medians

    def close(pace):
        cap = seats(pace, limits)[0]
        minutes = sum(medians[depth]['median_minutes'] if depth in medians else FALLBACK_MINUTES[depth]
                      for depth in (_depth(pace, row, trust) for row in candidates))
        return cap, (now + timedelta(minutes=minutes / max(cap, 1))).astimezone(workspace.zone(config))

    dates = sorted((goal_list[goal]['date'], goal) for goal in {row.get('goal') for row in candidates}
                   if goal in goal_list)
    unlock = None
    if guards:
        queue, unlock = 'careful', 'steady unlocks once they merge'
    else:
        _, steady_close = close('steady')
        local = now.astimezone(workspace.zone(config))
        late = (steady_close.date() > local.date()
                or steady_close.strftime('%H:%M') > str(data.get('envelope', {}).get('end', '24:00')))
        near = dates and (date.fromisoformat(dates[0][0]) - local.date()).days <= 2
        queue = 'fast' if candidates and (near or late) else 'steady'
    pace, binding = queue, 'queue'
    load, cores = limits.get('load'), limits.get('cores')
    if queue == 'fast' and load is not None and cores and load >= cores:
        pace, binding, unlock = 'steady', 'host', f'fast unlocks when the load average falls below {cores}'
    cap, finish = close(pace)
    budget, per_seat = config['budget']['tokens_per_day'], limits.get('per_seat_tokens')
    reach = len(candidates)
    if budget and per_seat:
        left, reach = budget - (limits.get('used_tokens') or 0), 0
        for row in candidates:
            left -= per_seat * (2 if _depth(pace, row, trust) == 'light' else 4)
            if left < 0:
                break
            reach += 1
        spend = (f'budget reaches {reach} of {len(candidates)} items at {pace}: advised against'
                 if reach < len(candidates) else f'budget covers the queue at {pace}')
        if reach < len(candidates):
            binding = 'budget'
    else:
        spend = 'budget unset' if not budget else 'budget per-seat tokens unmeasured'
    counts = [f'{sum(predict(row) == tier for row in candidates)} {tier}' for tier in ('light', 'standard', 'full')
              if any(predict(row) == tier for row in candidates)]
    shape = ', '.join([f'{len(candidates)} items', *counts,
                       *([f'{len(guards)} items touching guard code'] if guards else []),
                       *([f'{dates[0][1]} due {dates[0][0]}'] if dates else [])])
    wish = config['pace']['default']
    lines = [f"{shape}: {pace}, {cap} seats, expected close {finish.strftime('%H:%M')}",
             f'{host_line(root, limits, config)}; {spend}; binding: {binding}' + (f'; {unlock}' if unlock else '')]
    if wish != pace:
        lines.append(f'Your default is {wish}; the advice is {pace} (binding: {binding})')
    return {'pace': pace, 'lines': lines, 'seats': cap, 'close': finish.strftime('%H:%M'),
            'binding': binding, 'unlock': unlock, 'reach': reach, 'wish': wish, 'budget': spend}


def propose_default(root, config):
    """#579: after ten days at two paces, one owner card proposing the default pace with the
    numbers, at most once per ten days. Recommends the fewest escaped defects per merged item;
    a pace that costs escaped defects is named, never silently kept. Returns the D-n or None."""
    from wuwei import decision, grants, metrics, state, watch, workspace
    from wuwei.report import costly
    table = metrics.by_pace(root)
    if (table == metrics.UNMEASURED or len(table) < 2 or sum(row['days'] for row in table.values()) < 10
            or any((metrics._state(day) or {}).get('pace_card') for day in watch.days(root)[:10])):
        return None
    rate = lambda pace: (table[pace]['escaped'] / table[pace]['merged'] if table[pace]['merged'] else 0,
                         -table[pace]['merged'] / table[pace]['days'])
    best = min(table, key=rate)
    numbers = '; '.join(f"{pace}: {row['days']} days, {row['merged']} merged, {row['escaped']} escaped, "
                        f"{row['cards']} cards" for pace, row in table.items())
    warned = ''.join(f" {pace} costs escaped defects: {table[pace]['escaped']} of {table[pace]['merged']} merged."
                     for pace in costly(table))
    text = grants._record(
        f'Set the default pace to {best}?', f'Per pace: {numbers}.{warned}',
        [(pace, f'pace.default = {pace}', f"{table[pace]['escaped']} escaped of {table[pace]['merged']} merged.",
          f'Days start at {pace} unless the gate picks another.', 9 if pace == best else 3) for pace in table]
        + [('keep', f"Keep the default pace {config['pace']['default']}", 'Nothing changes.',
            'The advice and the gate card choose each day as today.', 2)],
        'Escaped defects per merged item', best,
        'The fewest escaped defects per merged item decided it; more escapes at this pace would flip it.',
        'workspace config pace.default.', 'The chosen pace hides a defect rate the next ten days show.',
        'After the next ten days at two paces.')
    ident = decision.write(text, root).stem
    decision.route_owner(ident, decision.evaluate(text)[0], root)
    row = {'id': ident, 'at': workspace.now().isoformat()}
    state._write_state(lambda data: data.__setitem__('pace_card', row), root, reserved=False,
                       kind='pace.carded', payload=row)
    return ident
