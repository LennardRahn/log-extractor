"""Parse cleaned CSP Shell telemetry dumps into structured records / CSV.

A cleaned log (produced by ``extractor.py``) interleaves ordinary shell output
with telemetry blocks. Each block is introduced by a ``Timestamp`` line and
followed by parameter readings::

    Timestamp 7688335
    30:5378 mcu_temp = 290 °C×100
    120:5378 mppt_temp = [62 112 135 53] °C×100
    143:5397 mrpm = 199939
    230:5398 temp_brd = -325 degC

Each parameter line has the shape ``id:address  name = value [unit]`` where:

* ``id``      is the parameter id
* ``address`` is the physical module address
* ``name``    is the parameter name
* ``value``   is either a scalar (number / nan / inf) or an ``[ ... ]`` array
              whose elements are space-separated
* ``unit``    is optional (e.g. ``°C×100``, ``mV``, ``deg/s``, ``Am²``)

Each reading is associated with the most recently seen ``Timestamp``. Lines
that are not parameter readings (shell output, ``HK:``/``[drun]`` messages, the
``list add`` parameter catalogue, etc.) are ignored.
"""

import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


# A line that introduces a new telemetry block: "Timestamp 7688335"
TIMESTAMP_LINE = re.compile(r'^Timestamp\s+(\d+)\s*$', re.IGNORECASE)

# A parameter reading: "id:address  name = <rest>". The value/unit split inside
# <rest> is handled separately because array values contain internal spaces.
PARAM_LINE = re.compile(
    r'^(?P<id>\d+):(?P<address>\d+)\s+(?P<name>\S+)\s*=\s*(?P<rest>.+?)\s*$'
)


@dataclass
class Record:
    timestamp: Optional[int]
    id: int
    address: int
    name: str
    value: str
    unit: Optional[str]


def _split_value_unit(rest: str):
    """Split the text after '=' into (value, unit).

    Arrays keep their internal spaces: the value runs to the closing ']' and
    anything after it is the unit. Scalars take the first whitespace-delimited
    token as the value and the remainder (if any) as the unit.
    """
    rest = rest.strip()
    if rest.startswith('['):
        end = rest.find(']')
        if end != -1:
            value = rest[:end + 1]
            unit = rest[end + 1:].strip()
            return value, (unit or None)
    parts = rest.split(None, 1)
    value = parts[0]
    unit = parts[1].strip() if len(parts) > 1 else None
    return value, unit


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

        # Only collect readings once we're inside a timestamped block; this
        # skips the parameter catalogue and other pre-telemetry noise.
        if current_ts is None:
            continue

        m = PARAM_LINE.match(line)
        if not m:
            continue

        value, unit = _split_value_unit(m.group('rest'))
        records.append(
            Record(
                timestamp=current_ts,
                id=int(m.group('id')),
                address=int(m.group('address')),
                name=m.group('name'),
                value=value,
                unit=unit,
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
