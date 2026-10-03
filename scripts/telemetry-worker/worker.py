"""The WUWEI telemetry collector (design 5.13): a pure accept function and a thin worker entry.

Deploy bundles cli/wuwei/telemetry.py beside this file, so validate is the plugin's own.
"""

from datetime import date, timedelta
import json

import telemetry

PER_IP = 10
PER_DAY = 1000


def weeks_before(today):
    """The four ISO weeks before the week of today."""
    return {telemetry.week_of((today - timedelta(weeks=n)).isoformat()) for n in range(1, 5)}


def accept(body, *, today, seen, ip_count, writes):
    """(status, dataset path or None) for one posted payload; nothing here keeps state."""
    try:
        found = telemetry.validate(json.loads(body))
    except (ValueError, TypeError, KeyError):
        return 400, None
    if 'token' not in found:
        return 400, None
    if found['week'] not in weeks_before(today):
        return 422, None
    if (found['token'], found['week']) in seen:
        return 409, None
    if ip_count >= PER_IP or writes >= PER_DAY:
        return 429, None
    return 201, f"data/{found['week']}/{found['token']}.json"


# The platform entry: a Python worker. Per-IP counts live in memory only and are never written.
_counts, _writes, _seen = {}, {}, set()


async def on_fetch(request, env):  # pragma: no cover - platform glue over accept
    import base64
    from js import Response, fetch

    if request.method != 'POST':
        return Response.new('', status=405)
    today = date.today()
    ip = request.headers.get('cf-connecting-ip') or ''
    key, text = (today, ip), await request.text()
    status, path = accept(text, today=today, seen=_seen,
                          ip_count=_counts.get(key, 0), writes=_writes.get(today, 0))
    _counts[key] = _counts.get(key, 0) + 1
    if status == 201:
        body = json.loads(text)
        answer = await fetch(f'https://api.github.com/repos/{env.DATASET}/contents/{path}', method='PUT',
                             headers={'Authorization': f'Bearer {env.BOT_TOKEN}', 'User-Agent': 'wuwei-telemetry',
                                      'Accept': 'application/vnd.github+json'},
                             body=json.dumps({'message': f'telemetry: {body["week"]}', 'content': base64.b64encode(
                                 json.dumps(body, sort_keys=True).encode()).decode()}))
        status = 201 if answer.status in (200, 201) else 409 if answer.status == 422 else 502
        _writes[today] = _writes.get(today, 0) + int(status == 201)
        if status != 502:
            _seen.add((body['token'], body['week']))
    return Response.new('', status=status)
