"""cloudres CLI entrypoint.

Usage examples:
    cloudres status
    cloudres status --json --watch 5
    cloudres config init --provider aws --out config.json
    cloudres config get limits.cpu_percent --file config.json
    cloudres config set limits.cpu_percent 80 --file config.json
    cloudres config validate config.json
    cloudres export --out usage.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import config as cfgmod
from . import resources


def _print_status(snap: resources.ResourceSnapshot, as_json: bool, limits: dict | None) -> None:
    if as_json:
        payload = snap.to_dict()
        if limits:
            payload["breaches"] = resources.check_against_limits(snap, limits)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"host:      {snap.hostname}")
    print(f"cpu:       {snap.cpu_percent:5.1f}%  ({snap.cpu_count} cores)"
          + (f"  load_avg={snap.load_avg}" if snap.load_avg else ""))
    print(f"memory:    {snap.mem_percent:5.1f}%  ({snap.mem_used_mb:.0f} / {snap.mem_total_mb:.0f} MB)")
    print(f"swap:      {snap.swap_percent:5.1f}%")
    print(f"disk:      {snap.disk_percent:5.1f}%  ({snap.disk_used_gb:.1f} / {snap.disk_total_gb:.1f} GB)")
    print(f"net:       sent={snap.net_bytes_sent:,}B  recv={snap.net_bytes_recv:,}B")

    if limits:
        breaches = resources.check_against_limits(snap, limits)
        breached = [k for k, v in breaches.items() if v]
        if breached:
            print(f"!! threshold breached: {', '.join(breached)}")


def cmd_status(args: argparse.Namespace) -> int:
    limits = None
    if args.config:
        try:
            cfg = cfgmod.load(args.config)
            limits = cfg.get("limits")
        except cfgmod.ConfigError as e:
            print(f"warning: {e}", file=sys.stderr)

    if args.watch:
        try:
            while True:
                snap = resources.take_snapshot(disk_path=args.disk_path)
                _print_status(snap, args.json, limits)
                if not args.json:
                    print("-" * 40)
                time.sleep(max(args.watch, 1))
        except KeyboardInterrupt:
            return 0
    else:
        snap = resources.take_snapshot(disk_path=args.disk_path)
        _print_status(snap, args.json, limits)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    snap = resources.take_snapshot(disk_path=args.disk_path)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(snap.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote snapshot to {args.out}")
    return 0


def cmd_config_init(args: argparse.Namespace) -> int:
    cfg = cfgmod.default_config(provider=args.provider)
    cfgmod.save(args.out, cfg)
    print(f"wrote default {args.provider} config to {args.out}")
    return 0


def cmd_config_get(args: argparse.Namespace) -> int:
    cfg = cfgmod.load(args.file)
    try:
        value = cfgmod.get_path(cfg, args.key)
    except KeyError:
        print(f"key not found: {args.key}", file=sys.stderr)
        return 1
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(value)
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    cfg = cfgmod.load(args.file)
    value = cfgmod.coerce_value(args.value)
    cfgmod.set_path(cfg, args.key, value)
    problems = cfgmod.validate(cfg)
    if problems and not args.force:
        print("refusing to save -- validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("(use --force to save anyway)", file=sys.stderr)
        return 1
    cfgmod.save(args.file, cfg)
    print(f"set {args.key} = {value!r} in {args.file}")
    return 0


def cmd_config_validate(args: argparse.Namespace) -> int:
    cfg = cfgmod.load(args.file)
    problems = cfgmod.validate(cfg)
    if not problems:
        print(f"{args.file}: valid")
        return 0
    print(f"{args.file}: {len(problems)} problem(s):")
    for p in problems:
        print(f"  - {p}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudres",
        description="Sample system resource usage and manage cloud config JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Show current resource usage")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                           help="Refresh every N seconds instead of a single snapshot")
    p_status.add_argument("--disk-path", default="/", help="Path/drive to measure disk usage for")
    p_status.add_argument("--config", metavar="FILE", help="Cloud config JSON to check limits against")
    p_status.set_defaults(func=cmd_status)

    p_export = sub.add_parser("export", help="Write a single resource snapshot to a JSON file")
    p_export.add_argument("--out", required=True, help="Output JSON file path")
    p_export.add_argument("--disk-path", default="/", help="Path/drive to measure disk usage for")
    p_export.set_defaults(func=cmd_export)

    p_config = sub.add_parser("config", help="Manage cloud configuration JSON")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)

    p_init = config_sub.add_parser("init", help="Write a new default config file")
    p_init.add_argument("--provider", choices=cfgmod.VALID_PROVIDERS, default="aws")
    p_init.add_argument("--out", default="config.json", help="Where to write the config")
    p_init.set_defaults(func=cmd_config_init)

    p_get = config_sub.add_parser("get", help="Read a dotted-path key from a config file")
    p_get.add_argument("key", help="Dotted path, e.g. limits.cpu_percent")
    p_get.add_argument("--file", required=True, help="Config JSON file")
    p_get.set_defaults(func=cmd_config_get)

    p_set = config_sub.add_parser("set", help="Write a dotted-path key in a config file")
    p_set.add_argument("key", help="Dotted path, e.g. limits.cpu_percent")
    p_set.add_argument("value", help="New value (JSON-coerced: numbers/bools/strings/arrays)")
    p_set.add_argument("--file", required=True, help="Config JSON file")
    p_set.add_argument("--force", action="store_true", help="Save even if validation fails")
    p_set.set_defaults(func=cmd_config_set)

    p_validate = config_sub.add_parser("validate", help="Validate a config file's structure")
    p_validate.add_argument("file", help="Config JSON file")
    p_validate.set_defaults(func=cmd_config_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except cfgmod.ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
