"""Built-in redaction of inbound message text: phone numbers, emails and secrets."""

import re

from wuwei import redact as patterns
from wuwei.registry import Result

# Secrets run first so the digit runs inside a token are not taken as a phone number.
PATTERNS = (
    # ponytail: the trace SECRET list also catches field words such as `message:`;
    # a message-specific list replaces it when that over-redaction matters.
    ('secret', re.compile(rf'(?:{patterns.SECRET})\S*', re.I)),
    ('email', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')),
    ('phone', re.compile(r'\+?' + patterns.PHONE)),
)


def redact(text, *, root=None):
    if not isinstance(text, str):
        return Result(2, None, 'redactor.builtin: text must be a string')
    findings = []

    def replace(kind):
        def sub(match):
            if kind == 'phone' and sum(c.isdigit() for c in match[0]) < 9:
                return match[0]
            phone = kind == 'secret' and re.fullmatch(r'\+[\d ().-]+', match[0])
            findings.append({'kind': 'phone' if phone else kind})
            return patterns.REDACTED
        return sub

    for kind, pattern in PATTERNS:
        text = pattern.sub(replace(kind), text)
    return Result(1 if findings else 0, {'text': text, 'findings': findings})
