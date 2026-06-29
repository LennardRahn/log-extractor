"""Parse and reconstruct CSP Shell telemetry records.

A telemetry response is a sequence of timestamped blocks::

    Timestamp 7858853
    30:5378  mcu_temp             = 405 °C×100
    143:5398  mrpm                 = 199720

Each parameter line has the shape ``id:address  name = value [unit]`` where:

* ``id``      is the parameter id
* ``address`` is the physical module address
* ``name``    is the human-readable parameter name (an identifier)
* ``value``   is the returned value (numeric, or nan/inf)
* ``unit``    is optional and may contain non-ASCII characters (e.g. ``°C×100``)

Crucially, **no field contains internal whitespace** — spaces only ever
separate fields. That fact is what makes robust reconstruction possible: when
interleaved output (see ``extractor.py``) jams tokens together or splits a
value, the original spacing cannot be recovered by guessing, but it does not
need to be — the grammar alone determines where each field begins and ends.
"""

import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


# A line that introduces a new telemetry block: "Timestamp 7858853"
TIMESTAMP_LINE = re.compile(r'^Timestamp\s+(\d+)\s*$', re.IGNORECASE)

# Numeric value: scientific notation, plain float/int, nan, inf variants.
# Mirrors the value grammar used in extractor.py.
_VALUE = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+\-]?\d+)?|[-+]?nan|[-+]?inf'

# The record grammar applied to a *whitespace-free* token string. Because no
# field may contain a space, removing all whitespace first and matching this
# pattern reconstructs the fields by structure rather than by guessing where
# spaces belonged. ``name`` must start with a letter/underscore so the boundary
# with the preceding numeric address is unambiguous; ``value`` is matched
# greedily so the unit (anything left over) starts at the first non-numeric
# character.
PARAM_DENSE = re.compile(
    rf'^(?P<id>\d+):(?P<address>\d+)'
    rf'(?P<name>[A-Za-z_]\w*)='
    rf'(?P<value>{_VALUE})'
    rf'(?P<unit>\S+)?$',
    re.IGNORECASE,
)


@dataclass
class Record:
    timestamp: Optional[int]
    id: int
    address: int
    name: str
    value: str
    unit: Optional[str]


def _match_dense(text: str):
    """Match ``text`` against the record grammar, ignoring all whitespace."""
    return PARAM_DENSE.match(re.sub(r'\s+', '', text))


def canonicalize(record: str) -> Optional[str]:
    """Reconstruct ``record`` into canonical ``id:address  name = value [unit]``.

    Whitespace in the input is ignored, so a record whose internal spacing was
    destroyed by interleaved output is recovered by structure. Returns ``None``
    if ``record`` is not a parameter record (e.g. a header or status line),
    leaving the caller free to keep it verbatim.
    """
    m = _match_dense(record)
    if not m:
        return None
    base = (
        f"{int(m.group('id'))}:{int(m.group('address'))}  "
        f"{m.group('name')} = {m.group('value')}"
    )
    unit = m.group('unit')
    return f"{base} {unit}" if unit else base


def parse_record(record: str, timestamp: Optional[int] = None) -> Optional[Record]:
    """Parse a single record line into a :class:`Record`, or ``None``."""
    m = _match_dense(record)
    if not m:
        return None
    return Record(
        timestamp=timestamp,
        id=int(m.group('id')),
        address=int(m.group('address')),
        name=m.group('name'),
        value=m.group('value'),
        unit=m.group('unit'),
    )


def parse_cleaned(text: str) -> List[Record]:
    """Parse cleaned log ``text`` into a list of :class:`Record`."""
    records: List[Record] = []
    current_ts: Optional[int] = None

    for line in text.splitlines():
        if not line.strip():
            continue

        ts = TIMESTAMP_LINE.match(line.strip())
        if ts:
            current_ts = int(ts.group(1))
            continue

        rec = parse_record(line, current_ts)
        if rec is not None:
            records.append(rec)

    return records


def write_csv(records: List[Record], dest: Path) -> None:
    fields = ['timestamp', 'id', 'address', 'name', 'value', 'unit']
    with dest.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description='Parse cleaned CSP Shell telemetry dumps into CSV.'
    )
    ap.add_argument('inputs', nargs='+', help='cleaned log file(s) to parse')
    args = ap.parse_args(argv)

    for p in args.inputs:
        src = Path(p)
        if not src.exists():
            print(f"[SKIP] {p} — file not found")
            continue

        records = parse_cleaned(src.read_text(encoding='utf-8', errors='replace'))
        dest = src.with_suffix('.csv')
        write_csv(records, dest)
        print(f"[OK]  {src}  →  {dest}  ({len(records)} records)")


if __name__ == '__main__':
    main()
