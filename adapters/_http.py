"""Bounded JSON requests for the HTTP reference adapters."""

import json
import os
import sys
import urllib.error
import urllib.request
from functools import wraps

from wuwei import env
from wuwei.registry import Result


class Failure(ValueError):
    """A local, safe diagnostic that contains no provider text."""


HINTS = {401: 'credential rejected (wrong, expired or revoked token)',
         403: 'credential has no access (scopes, SSO authorization or a rate limit)',
         404: 'not found or not visible to the credential (check the project or repository '
              "name and the token's access)",
         429: 'rate limited; retry later'}


def status(code):
    """HTTP <code> and a one-line hint, so doctor names the cause (never provider text)."""
    hint = HINTS.get(code) or ('provider error; retry later' if 500 <= code < 600 else '')
    return f'HTTP {code}' + (f': {hint}' if hint else '')


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
    if why := env.malformed(name):
        raise Failure(f'{name} is malformed ({why}); paste only the token into .wuwei/env as {name}=<token>')
    return value


def settings(root):
    """The workspace config, for adapters that read their own table (tracker)."""
    from wuwei import workspace
    return workspace.load_config(workspace.find_workspace(root))


def request(url, token, payload=None, *, authorization='Bearer', extra_headers=None,
            method='POST'):
    headers = {'Content-Type': 'application/json',
               'Authorization': f'{authorization} {token}' if authorization else token}
    headers.update(extra_headers or {})
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise Failure(status(response.status))
            body = response.read(4_000_001)
    except urllib.error.HTTPError as exc:
        raise Failure(status(exc.code)) from None
    if len(body) > 4_000_000:
        raise Failure('response too large')
    if not body.strip():
        return {}  # Jira answers 204 with no body
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
