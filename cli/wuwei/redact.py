"""Conservative built-in patterns for data persisted by the trace recorder."""

import hashlib
import re
from urllib.parse import unquote


REDACTED = '[REDACTED]'
SENSITIVE_FIELD = (
    r'password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|'
    r'authorization|cookie|credential|phone|mobile|message|body|text|pass\b|pwd|auth|[_-]key\b')
SENSITIVE_KEY = re.compile(SENSITIVE_FIELD, re.I)
SECRET = re.compile(
    rf'(?:{SENSITIVE_FIELD})[\w-]{{0,40}}(?:\\?["\'])?\s{{0,40}}[:=]\s{{0,40}}\S|'
    rf'--(?:{SENSITIVE_FIELD})[\w-]{{0,40}}\s{{1,40}}\S|'
    r'(?:--(?:data[\w-]{0,40}|json)|-d)(?:\s{1,40}|=)\S|'
    r'\b(?:Bearer|Basic)\s{1,40}\S{1,2048}|[a-z][a-z0-9+.-]{0,30}://[^/\s]{0,2048}@|'
    r'\b(?:gh[pousr]_|github_pat_|sk-|xox[baprs]-|[sr]k_(?:live|test)_|'
    r'glpat-|AIza|npm_|hf_)[a-z0-9_-]{1,2048}|hooks\.slack\.com/services/|'
    r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|'
    r'\beyJ[a-z0-9_-]{1,2048}\.[a-z0-9_-]{1,2048}\.[a-z0-9_-]{1,2048}|'
    r'-----BEGIN [A-Z ]{0,40}PRIVATE KEY-----|\+\d[\d ().-]{7,40}\d', re.I)
PHONE = re.compile(r'(?<!\w)\d[\d ().-]{7,40}\d(?!\w)')
BODY = re.compile(
    r'\b(?:git\s{1,40}commit\b[^\n;]{0,2048}?\s-m|'
    r'gh\s{1,40}pr\s{1,40}comment\b[^\n;]{0,2048}?\s(?:-b|--body))'
    r'(?:=|\s{0,40})("(?:\\.|[^"\\]){0,2048}(?:"|$)|'
    r"'[^']{0,2048}(?:'|$)|[^\s;\"']{1,2048})")
HEREDOC = re.compile(
    r'<<-?\s{0,40}[\'\"]?([\w-]{1,40})[\'\"]?[^\n]{0,2048}\n'
    r'([\s\S]{0,2048}?)(?:\n\t{0,40}\1\b|$)')


def body_marker(value):
    return f'[BODY {len(value)} chars sha256:{hashlib.sha256(value.encode()).hexdigest()}]'


def redact(value):
    if isinstance(value, dict):
        path = value.get('file_path', '')
        private_file = isinstance(path, str) and (
            len(path) > 2048 or any(part.startswith('.env') for part in path.lower().split('/'))
            or path.lower().endswith(('.pem', '.key'))
            or 'credentials' in path.lower() or 'secret' in path.lower())
        return {redact(key): REDACTED if (
            len(key) > 2048 or SENSITIVE_KEY.search(key)
            or SENSITIVE_KEY.search(re.sub(r'[^a-z0-9]', '', key.lower()))
            or private_file and key in ('content', 'new_string', 'old_string')) else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and len(value) > 2048:
        digest = hashlib.sha256(value.encode()).hexdigest()
        return redact(value[:512]) + f'[TRUNCATED {len(value)} chars sha256:{digest}]'
    # ponytail: pattern redaction is best effort; the durable path is the M5 redactor port.
    if isinstance(value, str):
        value = HEREDOC.sub(lambda m: body_marker(m[2]), value)
        value = BODY.sub(lambda m: body_marker(
            m[1].strip(m[1][0]) if m[1].startswith(('"', "'")) else m[1]), value)
        decoded = unquote(value)
        if SECRET.search(decoded) or any(
                sum(c.isdigit() for c in m[0]) >= 9 and not m[0].isdigit()
                for m in PHONE.finditer(decoded)):
            return REDACTED
    return value
