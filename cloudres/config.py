"""Cloud configuration JSON read/write/validate.

Config is deliberately provider-agnostic and never stores raw secrets --
only a `credentials_ref` naming an env var or profile to look up
elsewhere. Supports dotted-path get/set (e.g. "limits.cpu_percent").
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

REQUIRED_TOP_LEVEL = ("provider", "region", "limits")
VALID_PROVIDERS = ("aws", "gcp", "azure", "other")

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "aws",
    "region": "us-east-1",
    "credentials_ref": "AWS_PROFILE_default",
    "limits": {
        "cpu_percent": 85,
        "mem_percent": 90,
        "disk_percent": 95,
    },
    "tags": {},
}


class ConfigError(ValueError):
    """Raised when a config file is missing, malformed, or fails validation."""


def default_config(provider: str = "aws") -> Dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["provider"] = provider
    if provider == "gcp":
        cfg["region"] = "us-central1"
        cfg["credentials_ref"] = "GOOGLE_APPLICATION_CREDENTIALS"
    elif provider == "azure":
        cfg["region"] = "eastus"
        cfg["credentials_ref"] = "AZURE_PROFILE_default"
    return cfg


def load(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {p}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Top-level JSON in {p} must be an object")
    return data


def save(path: str | Path, config: Dict[str, Any], indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=indent, sort_keys=True)
        f.write("\n")
    tmp.replace(p)  # atomic-ish write, avoids truncated file on crash


def validate(config: Dict[str, Any]) -> list[str]:
    """Return a list of validation problems (empty list means valid)."""
    problems = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in config:
            problems.append(f"missing required key: '{key}'")

    provider = config.get("provider")
    if provider is not None and provider not in VALID_PROVIDERS:
        problems.append(
            f"provider '{provider}' not in {VALID_PROVIDERS}"
        )

    limits = config.get("limits")
    if limits is not None:
        if not isinstance(limits, dict):
            problems.append("'limits' must be an object")
        else:
            for k, v in limits.items():
                if not isinstance(v, (int, float)):
                    problems.append(f"limits.{k} must be numeric, got {type(v).__name__}")
                elif not (0 <= v <= 100):
                    problems.append(f"limits.{k}={v} should be a percentage between 0 and 100")

    if "credentials_ref" in config and not isinstance(config["credentials_ref"], str):
        problems.append("'credentials_ref' must be a string naming an env var/profile, not a raw secret")

    return problems


def get_path(config: Dict[str, Any], dotted_key: str) -> Any:
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted_key)
        node = node[part]
    return node


def set_path(config: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = config
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def coerce_value(raw: str) -> Any:
    """Best-effort coercion of a CLI string into int/float/bool/JSON/str."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
