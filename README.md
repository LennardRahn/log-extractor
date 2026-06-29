# log-extractor

Python scripts for extracting data and ancillary information from logs created
by CSP Shell sessions. The logs are simple terminal dumps, so there is plenty
of "junk data" in these files.

The telemetry system is queried for data and returns it with an associated
timestamp. A returned block looks like:

```
Timestamp 7858853
30:5378  mcu_temp             = 405 °C×100
143:5398  mrpm                 = 199720
```

Each parameter line has the shape `id:address  name = value [unit]`:

* `id`      — the parameter id
* `address` — the physical module address
* `name`    — the parameter name
* `value`   — the returned value (numeric, or `nan`/`inf`)
* `unit`    — optional, may contain non-ASCII characters (e.g. `°C×100`)

## Reconstruction, not whitespace guessing

The dumps are corrupted by `prometheus add` output interleaved into the same
terminal stream, sometimes *inside* a record — splitting a value across lines
or jamming tokens together. Since **no telemetry field contains internal
whitespace** (spaces only separate fields), records are rebuilt from the known
grammar `id:address  name = value [unit]` rather than by guessing where spaces
were lost. After removing the injected fragment, all whitespace is stripped and
the record is re-parsed by structure, then re-emitted in canonical form. This
avoids the earlier heuristic that corrupted scientific notation
(e.g. `1e3` → `1 e3`).

## Usage

1. **Clean** the raw terminal dump (strip ANSI codes, drop injected
   `prometheus add` lines, reconstruct split records):

   ```
   # configure INPUT_PATHS in extractor.py, then:
   python3 extractor.py
   ```

   This writes a `*_cleaned.log` next to each input.

2. **Parse** the cleaned log into structured records (optional — CSV export):

   ```
   python3 parser.py path/to/file_cleaned.log
   ```

   Each record carries `timestamp, id, address, name, value, unit`, with every
   parameter associated to the most recently seen `Timestamp`. `parser.py` is
   also usable as a library (`parse_cleaned`, `canonicalize`) if you already
   have your own exporter.
