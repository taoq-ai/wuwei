"""Bounded JSON requests for the HTTP reference adapters."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from functools import wraps

from wuwei import env
from wuwei.registry import Result


class Failure(ValueError):
    """A local, safe diagnostic: no provider body or stderr text (a GraphQL error's first
    message, redacted and capped, may name the failing lookup, #617)."""


HINTS = {401: 'credential rejected (wrong, expired or revoked token)',
         403: 'credential has no access (scopes, SSO authorization or a rate limit)',
         404: 'not found or not visible to the credential (check the project or repository '
              "name and the token's access)",
         429: 'rate limited; retry later'}

WAIT = 60  # GitHub: with no reset given, wait at least one minute (#738)


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


class RateLimited(Failure):
    """#738: a GitHub rate limit and its reset (epoch seconds); the text is numbers and fixed words."""

    def __init__(self, reset, remaining=None, limit=None, resource=None):
        self.reset = reset
        left = (f' ({remaining} of {limit} {resource} calls left)'
                if None not in (remaining, limit, resource) else '')
        super().__init__(f'GitHub rate limit until {time.strftime("%H:%M:%S", time.gmtime(reset))} UTC'
                         f'{left}; retry after it')


def cap(root=None):
    """The longest wait for a reset (host.rate_limit_wait_seconds); 120 with no readable workspace."""
    try:
        return settings(root)['host']['rate_limit_wait_seconds']
    except (OSError, ValueError, KeyError):
        return 120


def gh_limit(stderr, env=None):
    """A RateLimited when gh's stderr names a rate limit, its reset read from gh api rate_limit."""
    if not re.search(r'rate limit', stderr or '', re.I):
        return None
    try:
        result = subprocess.run(['gh', 'api', 'rate_limit', '--hostname', 'github.com'],
                                capture_output=True, text=True, timeout=30, env=env)
        resources = json.loads(result.stdout)['resources'] if result.returncode == 0 else {}
        name, row = min(((name, resources[name]) for name in ('core', 'graphql')),
                        key=lambda pair: pair[1]['remaining'])
        if not all(type(row[key]) is int for key in ('remaining', 'limit', 'reset')):
            raise TypeError
        # Calls left means a secondary limit, which gives no reset.
        return RateLimited(row['reset'] if row['remaining'] == 0 else time.time() + WAIT,
                           row['remaining'], row['limit'], name)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        return RateLimited(time.time() + WAIT)


def retry(call, root=None):
    """Run call; on a RateLimited whose reset is within the cap, wait for it and run call once more.
    Per gh call or request, never per port operation, so a write that succeeded is not repeated."""
    try:
        return call()
    except RateLimited as limit:
        wait = limit.reset - time.time()
        if wait > cap(root):
            raise
        time.sleep(max(0, wait))
    return call()


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


def _github_limit(code, headers):
    """#738: raise RateLimited from GitHub's rate-limit headers; a 403 without them is not one."""
    left = [headers.get(key) or '' for key in ('X-RateLimit-Remaining', 'X-RateLimit-Limit')]
    resource = headers.get('X-RateLimit-Resource') or ''
    calls = ((int(left[0]), int(left[1]), resource)
             if all(map(str.isdigit, left)) and re.fullmatch(r'[a-z_]+', resource) else ())
    after, reset = headers.get('Retry-After') or '', headers.get('X-RateLimit-Reset') or ''
    if after.isdigit():
        raise RateLimited(time.time() + int(after), *calls) from None
    if left[0] == '0' and reset.isdigit():
        raise RateLimited(int(reset), *calls) from None
    if code == 429:
        raise RateLimited(time.time() + WAIT, *calls) from None


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
        if url.startswith('https://api.github.com/') and exc.code in (403, 429):
            _github_limit(exc.code, exc.headers or {})
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
