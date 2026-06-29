"""Parse cleaned CSP Shell telemetry dumps into structured records.

A cleaned log (see ``extractor.py``) is a sequence of timestamped blocks::

    Timestamp 7858853
    30:5378  mcu_temp             = 405 °C×100
    143:5398  mrpm                 = 199720

Each parameter line has the shape ``id:address  name = value [unit]`` where:

* ``id``      is the parameter id
* ``address`` is the physical module address
* ``name``    is the human-readable parameter name
* ``value``   is the returned value (numeric, or nan/inf)
* ``unit``    is optional and may contain non-ASCII characters (e.g. ``°C×100``)

The value/unit pair is associated with the most recently seen ``Timestamp``.
"""

import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


# A line that introduces a new telemetry block: "Timestamp 7858853"
TIMESTAMP_LINE = re.compile(r'^Timestamp\s+(\d+)\s*$', re.IGNORECASE)

# Numeric value: scientific notation, plain float/int, nan, inf variants.
# Mirrors the value grammar used in extractor.py.
_VALUE = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+\-]?\d+)?|[-+]?nan|[-+]?inf'

# A parameter line: "143:5398  mrpm  = 199720" with an optional trailing unit.
PARAM_LINE = re.compile(
    rf'^(?P<id>\d+):(?P<address>\d+)\s+'
    rf'(?P<name>\S+)\s*=\s*'
    rf'(?P<value>{_VALUE})'
    rf'(?:\s+(?P<unit>\S.*?))?\s*$',
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


def parse_cleaned(text: str) -> List[Record]:
    """Parse cleaned log ``text`` into a list of :class:`Record`."""
    records: List[Record] = []
    current_ts: Optional[int] = None

    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue

        ts = TIMESTAMP_LINE.match(line)
        if ts:
            current_ts = int(ts.group(1))
            continue

        m = PARAM_LINE.match(line)
        if not m:
            # Non-telemetry line (ancillary text); skip it.
            continue

        unit = m.group('unit')
        records.append(
            Record(
                timestamp=current_ts,
                address=int(m.group('address')),
                id=int(m.group('id')),
                name=m.group('name'),
                value=m.group('value'),
                unit=unit.strip() if unit else None,
            )
        )

    return records


def write_csv(records: List[Record], dest: Path) -> None:
    fields = ['timestamp', 'id', 'address', 'name', 'value', 'unit']
    with dest.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))


def write_json(records: List[Record], dest: Path) -> None:
    dest.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description='Parse cleaned CSP Shell telemetry dumps into CSV/JSON.'
    )
    ap.add_argument('inputs', nargs='+', help='cleaned log file(s) to parse')
    ap.add_argument(
        '--format', choices=['csv', 'json'], default='csv',
        help='output format (default: csv)',
    )
    args = ap.parse_args(argv)

    for p in args.inputs:
        src = Path(p)
        if not src.exists():
            print(f"[SKIP] {p} — file not found")
            continue

        text = src.read_text(encoding='utf-8', errors='replace')
        records = parse_cleaned(text)

        dest = src.with_suffix('.' + args.format)
        if args.format == 'csv':
            write_csv(records, dest)
        else:
            write_json(records, dest)
        print(f"[OK]  {src}  →  {dest}  ({len(records)} records)")


if __name__ == '__main__':
    main()
