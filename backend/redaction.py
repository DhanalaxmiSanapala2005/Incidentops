import re
PATTERNS = [
    (re.compile(r"(?i)\b([\w.-]*(?:password|passwd|pwd|secret|api[_-]?key|token))\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
]


def redact(text: str) -> tuple[str, bool]:
    out = text
    for rx, rep in PATTERNS:
        out = rx.sub(rep, out)
    return out, out != text
