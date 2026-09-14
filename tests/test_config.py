"""Tests for cloudres.config: load/save/validate/get_path/set_path."""
import json

import pytest

from cloudres import config as cfgmod


def test_default_config_has_required_keys():
    cfg = cfgmod.default_config()
    for key in cfgmod.REQUIRED_TOP_LEVEL:
        assert key in cfg


def test_default_config_varies_by_provider():
    aws = cfgmod.default_config("aws")
    gcp = cfgmod.default_config("gcp")
    assert aws["region"] != gcp["region"]
    assert aws["credentials_ref"] != gcp["credentials_ref"]


def test_validate_passes_on_default_config():
    cfg = cfgmod.default_config()
    assert cfgmod.validate(cfg) == []


def test_validate_flags_missing_required_key():
    cfg = cfgmod.default_config()
    del cfg["region"]
    problems = cfgmod.validate(cfg)
    assert any("region" in p for p in problems)


def test_validate_flags_bad_provider():
    cfg = cfgmod.default_config()
    cfg["provider"] = "not_a_real_cloud"
    problems = cfgmod.validate(cfg)
    assert any("provider" in p for p in problems)


def test_validate_flags_out_of_range_limit():
    cfg = cfgmod.default_config()
    cfg["limits"]["cpu_percent"] = 150
    problems = cfgmod.validate(cfg)
    assert any("cpu_percent" in p for p in problems)


def test_validate_flags_non_numeric_limit():
    cfg = cfgmod.default_config()
    cfg["limits"]["cpu_percent"] = "high"
    problems = cfgmod.validate(cfg)
    assert any("cpu_percent" in p for p in problems)


def test_validate_flags_non_string_credentials_ref():
    cfg = cfgmod.default_config()
    cfg["credentials_ref"] = {"key": "not-a-string"}
    problems = cfgmod.validate(cfg)
    assert any("credentials_ref" in p for p in problems)


def test_save_then_load_round_trips(tmp_path):
    cfg = cfgmod.default_config("azure")
    path = tmp_path / "config.json"
    cfgmod.save(path, cfg)
    loaded = cfgmod.load(path)
    assert loaded == cfg


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load(tmp_path / "does_not_exist.json")


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load(path)


def test_load_non_object_json_raises(tmp_path):
    path = tmp_path / "list.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load(path)


def test_get_path_dotted_key():
    cfg = cfgmod.default_config()
    assert cfgmod.get_path(cfg, "limits.cpu_percent") == 85


def test_get_path_missing_key_raises():
    cfg = cfgmod.default_config()
    with pytest.raises(KeyError):
        cfgmod.get_path(cfg, "limits.does_not_exist")


def test_set_path_updates_existing_key():
    cfg = cfgmod.default_config()
    cfgmod.set_path(cfg, "limits.cpu_percent", 70)
    assert cfg["limits"]["cpu_percent"] == 70


def test_set_path_creates_missing_nested_keys():
    cfg = cfgmod.default_config()
    cfgmod.set_path(cfg, "tags.env", "production")
    assert cfg["tags"]["env"] == "production"


def test_coerce_value_numbers_and_bools():
    assert cfgmod.coerce_value("85") == 85
    assert cfgmod.coerce_value("85.5") == 85.5
    assert cfgmod.coerce_value("true") is True


def test_coerce_value_plain_string_passthrough():
    assert cfgmod.coerce_value("us-east-1") == "us-east-1"
