from __future__ import annotations

from pathlib import Path

import pytest

from led_web_v7.storage import Storage


def test_storage_creates_default_data_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"

    storage = Storage(data_dir)
    snapshot = storage.snapshot()

    assert snapshot["strips"] == []
    assert snapshot["zones"] == []
    assert snapshot["presets"] == []
    assert snapshot["total_pixels"] == 0
    assert [mode["id"] for mode in snapshot["modes"]] == list(range(11))
    assert snapshot["settings"]["serial_port"] == "/dev/ttyACM0"
    assert all((data_dir / f"{name}.json").exists() for name in ("strips", "zones", "modes", "settings", "presets"))


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
