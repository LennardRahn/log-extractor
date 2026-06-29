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

Each parameter line has the shape `address:id  name = value [unit]`:

* `address` — the physical module address
* `id`      — the parameter id at that address
* `name`    — the parameter name
* `value`   — the returned value (numeric, or `nan`/`inf`)
* `unit`    — optional, may contain non-ASCII characters (e.g. `°C×100`)

## Usage

Two stages:

1. **Clean** the raw terminal dump (strip ANSI codes and injected
   `prometheus add` lines, collapse split records):

   ```
   # configure INPUT_PATHS in extractor.py, then:
   python3 extractor.py
   ```

   This writes a `*_cleaned.log` next to each input.

2. **Parse** the cleaned log into structured records and export to CSV or JSON:

   ```
   python3 parser.py path/to/file_cleaned.log            # CSV (default)
   python3 parser.py --format json path/to/file_cleaned.log
   ```

   Each record carries `timestamp, address, id, name, value, unit`, with every
   parameter associated to the most recently seen `Timestamp`.
