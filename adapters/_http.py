"""Bounded JSON requests for the HTTP reference adapters."""

import json
import os
import sys
import urllib.request
from functools import wraps

from wuwei.registry import Result


class Failure(ValueError):
    """A local, safe diagnostic that contains no provider text."""


def operation(name):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            try:
                value = function(*args, **kwargs)
                return value if isinstance(value, Result) else Result(0, value)
            except (OSError, ValueError, TypeError, KeyError, IndexError,
                    AttributeError) as exc:
                # Provider text and request arguments may contain secrets or private content.
                detail = str(exc) if isinstance(exc, Failure) else type(exc).__name__
                reason = f'{name}: could not run: {detail}'
                print(reason, file=sys.stderr)
                return Result(2, None, reason)
        return call
    return decorate


def credential(name):
    value = os.environ.get(name)
    if not value:
        raise Failure(f'{name} is missing')
    return value


def request(url, token, payload=None, *, authorization='Bearer', extra_headers=None,
            method='POST'):
    headers = {'Content-Type': 'application/json',
               'Authorization': f'{authorization} {token}' if authorization else token}
    headers.update(extra_headers or {})
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise Failure('HTTP status was not successful')
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise Failure('response too large')
    if body.lstrip().startswith((b'event:', b'data:')):
        events = []
        for block in body.decode().split('\n\n'):
            data = '\n'.join(line[5:].lstrip() for line in block.splitlines()
                             if line.startswith('data:'))
            if data:
                events.append(json.loads(data))
        value = next((event for event in events if isinstance(event, dict)
                      and event.get('id') == (payload or {}).get('id')), None)
    else:
        value = json.loads(body)
    if not isinstance(value, dict):
        raise Failure('invalid JSON object')
    return value
