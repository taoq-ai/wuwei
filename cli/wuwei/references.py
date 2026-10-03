"""Canonical code-host repository and PR references."""

import re

from wuwei.exits import DAMAGED


def repository(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('expected owner/repo; pass owner/repo')
    if any(part in ('.', '..') for part in value.split('/')):
        raise ValueError(f'invalid repository; {DAMAGED}')
    return value


def pull_request(value):
    if not isinstance(value, str) or not re.fullmatch(r'[^#]+#[1-9][0-9]*', value):
        raise ValueError('expected owner/repo#number; pass owner/repo#number')
    repository(value.split('#')[0])
    return value
