from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

import led_web_v7.storage as storage_module
from led_web_v7.device_capabilities import (
    MAX_ACTIVE_STRIPS,
    MAX_ZONE_NAME_LENGTH,
    MAX_ZONES,
    SUPPORTED_DATA_PINS,
    default_mode_records,
)
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


def test_storage_rejects_unsupported_hardware_values_before_persisting(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "data")

    with pytest.raises(ValueError, match="Pin 1 is not supported"):
        storage.add_strip(pin=1, pixel_count=1)
    with pytest.raises(ValueError, match="between 1 and 300"):
        storage.add_strip(pin=2, pixel_count=301)
    with pytest.raises(ValueError, match="Mode ID 11 is not supported"):
        storage.add_mode(11, "Custom")

    storage.add_strip(pin=2, pixel_count=300)
    with pytest.raises(ValueError, match="V7 supports at most"):
        storage.add_zone("z" * (MAX_ZONE_NAME_LENGTH + 1), 0, 0)
    with pytest.raises(ValueError, match="Mode ID 11 is not supported"):
        storage.add_preset(
            "Invalid effect",
            "",
            96,
            [{"zone": "desk", "mode": 11, "brightness": 96, "delay_ms": 40, "palette": []}],
        )

    assert storage.snapshot()["strips"] == [{"id": 1, "pin": 2, "pixel_count": 300, "label": "Pin 2"}]
    assert storage.snapshot()["zones"] == []
    assert storage.snapshot()["presets"] == []


def test_storage_enforces_strip_and_zone_capacity(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "data")
    for pin in SUPPORTED_DATA_PINS:
        storage.add_strip(pin=pin, pixel_count=1)

    assert len(storage.snapshot()["strips"]) == MAX_ACTIVE_STRIPS
    with pytest.raises(ValueError, match=f"at most {MAX_ACTIVE_STRIPS} active strips"):
        storage.add_strip(pin=SUPPORTED_DATA_PINS[0], pixel_count=1)

    zone_storage = Storage(tmp_path / "zone-data")
    zone_storage.add_strip(pin=SUPPORTED_DATA_PINS[0], pixel_count=300)
    for index in range(MAX_ZONES):
        zone_storage.add_zone(f"zone_{index}", index, index)

    assert len(zone_storage.snapshot()["zones"]) == MAX_ZONES
    with pytest.raises(ValueError, match=f"at most {MAX_ZONES} zones"):
        zone_storage.add_zone("one_too_many", MAX_ZONES, MAX_ZONES)


def test_storage_rejects_persisted_values_that_the_firmware_cannot_honor(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    strips_path = data_dir / "strips.json"
    strips_path.write_text(
        json.dumps([{"id": 1, "pin": 99, "pixel_count": 1, "label": "Unsupported"}]),
        encoding="utf-8",
    )

    with pytest.raises(StorageDataError, match="Pin 99 is not supported"):
        Storage(data_dir)

    assert json.loads(strips_path.read_text(encoding="utf-8"))[0]["pin"] == 99


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


def test_storage_preserves_existing_data_file_permissions(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    storage = Storage(data_dir)
    strips_path = data_dir / "strips.json"
    strips_path.chmod(0o640)

    storage.add_strip(pin=2, pixel_count=1, label="Desk")

    assert stat.S_IMODE(strips_path.stat().st_mode) == 0o640


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
