from __future__ import annotations

import json
from pathlib import Path

import pytest

import led_web_v7.storage as storage_module
from led_web_v7.device_capabilities import default_mode_records
from led_web_v7.storage import Storage, StorageDataError


def test_storage_creates_default_data_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"

    storage = Storage(data_dir)
    snapshot = storage.snapshot()

    assert snapshot["strips"] == []
    assert snapshot["zones"] == []
    assert snapshot["presets"] == []
    assert snapshot["total_pixels"] == 0
    assert snapshot["modes"] == default_mode_records()
    assert snapshot["settings"]["serial_port"] == "/dev/ttyACM0"
    assert "pin_options" not in snapshot["settings"]
    assert all((data_dir / f"{name}.json").exists() for name in ("strips", "zones", "modes", "settings", "presets"))


def test_storage_migrates_legacy_pin_options_out_of_serial_settings(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings_path = data_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "serial_port": "/dev/ttyUSB0",
                "baud_rate": 57600,
                "flush_interval_ms": 100,
                "pin_options": [99],
            }
        ),
        encoding="utf-8",
    )

    storage = Storage(data_dir)

    assert storage.snapshot()["settings"] == {
        "serial_port": "/dev/ttyUSB0",
        "baud_rate": 57600,
        "flush_interval_ms": 100,
    }
    assert "pin_options" not in json.loads(settings_path.read_text(encoding="utf-8"))


def test_storage_rejects_zone_without_a_configured_strip(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "data")

    with pytest.raises(ValueError, match="Add at least one strip"):
        storage.add_zone("desk", 0, 0)


def test_storage_rejects_overlapping_zone_ranges(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "data")
    storage.add_strip(pin=6, pixel_count=12, label="Desk")
    storage.add_zone("left", 0, 5)

    with pytest.raises(ValueError, match=r"Overlap with zone 'left' \(0-5\)"):
        storage.add_zone("right", 5, 9)


def test_storage_reports_malformed_json_without_overwriting_it(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    strips_path = data_dir / "strips.json"
    original_contents = '{"id":\n'
    strips_path.write_text(original_contents, encoding="utf-8")

    with pytest.raises(StorageDataError) as exc_info:
        Storage(data_dir)

    message = str(exc_info.value)
    assert str(strips_path) in message
    assert "contains invalid JSON at line 2, column 1" in message
    assert "The file was not changed; repair it or restore a backup before restarting." in message
    assert strips_path.read_text(encoding="utf-8") == original_contents


def test_storage_rejects_valid_json_with_the_wrong_top_level_type(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    strips_path = data_dir / "strips.json"
    strips_path.write_text("{}", encoding="utf-8")

    with pytest.raises(StorageDataError) as exc_info:
        Storage(data_dir)

    message = str(exc_info.value)
    assert str(strips_path) in message
    assert "must contain a JSON list, not dict" in message
    assert strips_path.read_text(encoding="utf-8") == "{}"


def test_storage_keeps_existing_json_when_atomic_replace_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    storage = Storage(data_dir)
    strips_path = data_dir / "strips.json"
    original_contents = strips_path.read_text(encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(storage_module.os, "replace", fail_replace)

    with pytest.raises(StorageDataError, match="simulated replacement failure"):
        storage.add_strip(pin=6, pixel_count=12, label="Desk")

    assert strips_path.read_text(encoding="utf-8") == original_contents
    assert list(data_dir.glob(".strips.json.*.tmp")) == []
