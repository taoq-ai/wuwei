"""Conservative built-in patterns for data persisted by the trace recorder."""

import json
import re
from urllib.parse import quote, quote_plus, unquote


REDACTED = '[REDACTED]'
VALUES = set()


def known_values(value):
    """Remove loaded credentials without hiding public diagnostic field names."""
    if isinstance(value, dict):
        return {known_values(key): known_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [known_values(item) for item in value]
    if isinstance(value, str):
        variants = {encoded for secret in VALUES for encoded in
                    (secret, quote(secret, safe=''), quote_plus(secret),
                     json.dumps(secret)[1:-1]) if encoded}
        for secret in sorted(variants, key=len, reverse=True):
            value = value.replace(secret, REDACTED)
    return value


class Output:
    """Filter credentials from CLI stdout and stderr, including watch logs."""

    def __init__(self, stream):
        self.stream = stream
        self.pending = ''

    def write(self, value):
        self.pending += value
        complete, newline, self.pending = self.pending.rpartition('\n')
        if newline:
            self.stream.write(known_values(complete + newline))
        return len(value)

    def flush(self):
        self.stream.write(known_values(self.pending))
        self.pending = ''
        self.stream.flush()


SENSITIVE_FIELD = (
    r'password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|'
    r'authorization|cookie|credential|phone|mobile|message|body|text|pass\b|pwd|auth|[_-]key\b')
# Pattern strings: re compiles them on first use through its own cache, off the hook path.
SENSITIVE_KEY = SENSITIVE_FIELD
# #473: a body marker is not itself a credential; --json and -d count only with a quoted,
# brace or @ value, or one holding =, & or : (gh field lists and git branch -d stay
# readable, curl bodies do not).
SECRET = (
    rf'(?:{SENSITIVE_FIELD})[\w-]{{0,40}}(?:\\?["\'])?\s{{0,40}}[:=]\s{{0,40}}(?!\[BODY )\S|'
    rf'--(?:{SENSITIVE_FIELD})[\w-]{{0,40}}\s{{1,40}}(?!\[BODY )\S|'
    r'--data[\w-]{0,40}(?:\s{1,40}|=)\S|'
    r'(?:--json|(?<![\w-])-d)(?:\s{1,40}|=)(?:[\'"{@]|[^\s=&:]{0,2048}[=&:])|'
    r'\b(?:Bearer|Basic)\s{1,40}\S{1,2048}|[a-z][a-z0-9+.-]{0,30}://[^/\s]{0,2048}@|'
    r'\b(?:gh[pousr]_|github_pat_|sk-|xox[baprs]-|[sr]k_(?:live|test)_|'
    r'glpat-|AIza|npm_|hf_)[a-z0-9_-]{1,2048}|hooks\.slack\.com/services/|'
    r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|'
    r'\beyJ[a-z0-9_-]{1,2048}\.[a-z0-9_-]{1,2048}\.[a-z0-9_-]{1,2048}|'
    r'-----BEGIN [A-Z ]{0,40}PRIVATE KEY-----|\+\d[\d ().-]{7,40}\d')
PHONE = r'(?<!\w)\d[\d ().-]{7,40}\d(?!\w)'
BODY = (
    r'\b(?:git\s{1,40}commit\b[^\n;]{0,2048}?\s-m|'
    r'gh\s{1,40}pr\s{1,40}comment\b[^\n;]{0,2048}?\s(?:-b|--body))'
    r'(?:=|\s{0,40})("(?:\\.|[^"\\]){0,2048}(?:"|$)|'
    r"'[^']{0,2048}(?:'|$)|[^\s;\"']{1,2048})")
HEREDOC = (
    r'<<-?\s{0,40}[\'\"]?([\w-]{1,40})[\'\"]?[^\n]{0,2048}\n'
    r'([\s\S]{0,2048}?)(?:\n\t{0,40}\1\b|$)')


def body_marker(value):
    import hashlib
    return f'[BODY {len(value)} chars sha256:{hashlib.sha256(value.encode()).hexdigest()}]'


def redact(value, *, prefix=False):
    """prefix: keep the text before the first credential (the trace recorder, #473); elsewhere a
    string with a credential is replaced whole, so no text around it reaches a record."""
    value = known_values(value)
    if isinstance(value, dict):
        path = value.get('file_path', '')
        private_file = isinstance(path, str) and (
            len(path) > 2048 or any(part.startswith('.env') for part in path.lower().split('/'))
            or path.lower().endswith(('.pem', '.key'))
            or path.replace('\\', '/').endswith('.wuwei/env')
            or 'credentials' in path.lower() or 'secret' in path.lower())
        return {redact(key, prefix=prefix): REDACTED if (
            len(key) > 2048 or re.search(SENSITIVE_KEY, key, re.I)
            or re.search(SENSITIVE_KEY, re.sub(r'[^a-z0-9]', '', key.lower()), re.I)
            or private_file and key in ('content', 'new_string', 'old_string')) else redact(item, prefix=prefix)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, prefix=prefix) for item in value]
    if isinstance(value, str) and len(value) > 2048:
        import hashlib
        digest = hashlib.sha256(value.encode()).hexdigest()
        return redact(value[:512], prefix=prefix) + f'[TRUNCATED {len(value)} chars sha256:{digest}]'
    # ponytail: pattern redaction is best effort; the durable path is the M5 redactor port.
    if isinstance(value, str):
        value = re.sub(HEREDOC, lambda m: body_marker(m[2]), value)
        value = re.sub(BODY, lambda m: m[0][:m.start(1) - m.start()] + body_marker(
            m[1].strip(m[1][0]) if m[1].startswith(('"', "'")) else m[1]), value)
        decoded = unquote(value)
        found = re.search(SECRET, decoded, re.I)
        starts = [found.start()] if found else []
        starts += [m.start() for m in re.finditer(PHONE, decoded)
                   if sum(c.isdigit() for c in m[0]) >= 9 and not m[0].isdigit()]
        if starts:
            # ponytail: everything from the first credential on is dropped (tool, subcommand and
            # earlier paths stay); per-value redaction if traces need the tail.
            return value[:min(starts)] + REDACTED if prefix and decoded == value else REDACTED
    return value
