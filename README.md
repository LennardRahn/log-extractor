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

Note that values may be **arrays** with internal spaces (e.g.
`[62 112 135 53]`, `[-nan nan -nan]`), so a field is not simply a
whitespace-delimited token — the parser splits an array value at its closing
`]` and treats the rest as the unit.

## Usage

1. **Clean** the raw terminal dump (strip ANSI codes, drop injected
   `prometheus add` lines, reassemble split records):

   ```
   # configure INPUT_PATHS in extractor.py, then:
   python3 extractor.py
   ```

   This writes a `*_cleaned.log` next to each input.

2. **Parse** the cleaned log into a CSV of telemetry readings:

   ```
   python3 parser.py path/to/file_cleaned.log
   ```

   This writes a `*.csv` with columns `timestamp, id, address, name, value,
   unit` — one row per reading, each associated with the most recently seen
   `Timestamp`. Lines that are not parameter readings (shell output, `HK:` /
   `[drun]` messages, the `list add` catalogue) are ignored. `parser.py` is
   also usable as a library via `parse_cleaned()`.

   The same `Timestamp` can appear in several blocks (a re-fetch), so a given
   `(timestamp, id, address)` may legitimately occur more than once.
