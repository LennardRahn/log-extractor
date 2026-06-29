import re
from pathlib import Path

from parser import canonicalize


# ── Configure your input files here ──────────────────────────────────────────
INPUT_PATHS = [
    "log/2026-06-12T13:52:26+00:00-csh.log",
    # "/path/to/another.log",
]
# ─────────────────────────────────────────────────────────────────────────────


# Numeric value: scientific notation, plain float/int, nan, inf variants
_VALUE = r'(?:[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+\-]?\d+)?|[-+]?nan|[-+]?inf)'

# A line that is entirely a prometheus-add entry
PROMETHEUS_LINE = re.compile(
    rf'^prometheus add \w+\{{[^}}]+\}}\s+{_VALUE}\s+\d+\s*$',
    re.IGNORECASE,
)

# A prometheus-add fragment anywhere inside a string
INLINE_PROM = re.compile(
    rf'\s*prometheus add \w+\{{[^}}]+\}}\s+{_VALUE}\s+\d+\s*',
    re.IGNORECASE,
)

# Any ANSI/VT100 escape sequence
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

# A [90m ... [0m record block, possibly spanning multiple lines
RECORD = re.compile(r'\x1b\[90m(.*?)\x1b\[0m', re.DOTALL)


def clean_log(text: str) -> str:
    result_lines = []
    last_end = 0

    for m in RECORD.finditer(text):
        # ── Text BETWEEN records ──────────────────────────────────────────
        # Drop standalone prometheus lines; keep anything else after
        # stripping residual ANSI codes.
        between = text[last_end:m.start()]
        for line in between.splitlines():
            if PROMETHEUS_LINE.match(line.strip()):
                continue
            plain = ANSI_ESCAPE.sub('', line)
            if plain.strip():
                result_lines.append(plain.rstrip())

        last_end = m.end()

        # ── The record itself ─────────────────────────────────────────────
        # Prometheus lines may have been injected into the middle of the
        # [90m...[0m block, splitting a value or jamming tokens together.
        # Remove those fragments, then rebuild the record from its grammar:
        # since no field contains internal whitespace, canonicalize() recovers
        # the fields by structure instead of guessing where spaces belonged
        # (which used to corrupt e.g. scientific notation like "1e3" → "1 e3").
        inner = INLINE_PROM.sub('', m.group(1))
        canon = canonicalize(inner)
        if canon is not None:
            result_lines.append(canon)
        else:
            # Not a parameter record (header/status text): keep it verbatim,
            # just collapsed onto one line with ANSI codes already stripped.
            collapsed = ' '.join(inner.split())
            if collapsed:
                result_lines.append(collapsed)

    # ── Tail after the last record ────────────────────────────────────────
    tail = text[last_end:]
    for line in tail.splitlines():
        if PROMETHEUS_LINE.match(line.strip()):
            continue
        plain = ANSI_ESCAPE.sub('', line)
        if plain.strip():
            result_lines.append(plain.rstrip())

    return '\n'.join(result_lines) + '\n'


def main():
    for p in INPUT_PATHS:
        src = Path(p)
        if not src.exists():
            print(f"[SKIP] {p} — file not found")
            continue

        raw = src.read_text(encoding='utf-8', errors='replace')
        cleaned = clean_log(raw)

        original_lines = raw.count('\n')
        cleaned_lines = cleaned.count('\n')
        removed = original_lines - cleaned_lines

        dest = src.with_stem(src.stem + '_cleaned')
        dest.write_text(cleaned, encoding='utf-8')
        print(f"[OK]  {src}  →  {dest}  ({removed} lines removed)")


if __name__ == '__main__':
    main()

