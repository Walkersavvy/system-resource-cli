# cloudres

A small CLI that does two things:

1. **Samples system resource usage** (CPU, memory, swap, disk, network) via `psutil`.
2. **Reads and writes a cloud configuration JSON file** (provider, region, a
   *reference* to credentials — never the raw secret — and alert thresholds),
   and can check a live resource snapshot against those thresholds.

Works on Windows, macOS, and Linux.

## Install

```bash
pip install -r requirements.txt
```

Run directly with:

```bash
python -m cloudres.cli status
```

## Usage

### Resource status

```bash
# One-off snapshot, human readable
python -m cloudres.cli status

# JSON output
python -m cloudres.cli status --json

# Refresh every 5 seconds until Ctrl+C
python -m cloudres.cli status --watch 5

# Check current usage against a config's thresholds and flag breaches
python -m cloudres.cli status --config config.json
```

### Export a snapshot to JSON

```bash
python -m cloudres.cli export --out usage.json
```

### Cloud config management

```bash
# Scaffold a new config file
python -m cloudres.cli config init --provider aws --out config.json

# Read a value (supports dotted paths)
python -m cloudres.cli config get limits.cpu_percent --file config.json

# Write a value (JSON-coerced: numbers/bools/strings/arrays all work)
python -m cloudres.cli config set limits.cpu_percent 80 --file config.json

# Validate a config file's structure
python -m cloudres.cli config validate config.json
```

## Config shape

```json
{
  "provider": "aws",
  "region": "us-east-1",
  "credentials_ref": "AWS_PROFILE_default",
  "limits": {
    "cpu_percent": 85,
    "mem_percent": 90,
    "disk_percent": 95
  },
  "tags": {}
}
```

`credentials_ref` intentionally never holds a raw key/secret — it names an
environment variable or profile that your own deployment scripts resolve
elsewhere. `config validate` enforces this stays a string, and rejects an
unknown `provider` or an out-of-range (0–100) limit unless `--force` is passed.

## Layout

```
cloudres/
├── cloudres/
│   ├── resources.py   # psutil-based sampling + threshold checks
│   ├── config.py       # JSON load/save/validate/get/set
│   └── cli.py           # argparse subcommands
├── requirements.txt
└── README.md
```

## Extending

- Add a provider-specific schema check in `config.validate()`.
- Add new metrics to `resources.ResourceSnapshot` and wire them into
  `check_against_limits()`.
- Point `--watch` output at a file/socket if you want continuous logging
  instead of stdout.
