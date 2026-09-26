from __future__ import annotations

import pytest

from led_web_v7.storage import Storage


def test_virtual_pixel_layout_always_matches_firmware_pin_order(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    storage.add_strip(pin=9, pixel_count=2, label="Later pin")
    storage.add_strip(pin=2, pixel_count=3, label="Earlier pin")

    assert storage.pixel_layout() == [
        {"id": 2, "pin": 2, "pixel_count": 3, "label": "Earlier pin", "start": 0, "end": 2},
        {"id": 1, "pin": 9, "pixel_count": 2, "label": "Later pin", "start": 3, "end": 4},
    ]
    assert [strip["pin"] for strip in storage.snapshot()["strips"]] == [2, 9]


def test_adding_a_preceding_strip_is_blocked_when_it_would_remap_a_zone(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    storage.add_strip(pin=4, pixel_count=10, label="Desk")
    storage.add_zone("desk", 0, 9)

    with pytest.raises(ValueError, match="would move existing zones to different physical pixels: desk"):
        storage.add_strip(pin=2, pixel_count=5, label="New first strip")

    assert storage.pixel_layout() == [
        {"id": 1, "pin": 4, "pixel_count": 10, "label": "Desk", "start": 0, "end": 9}
    ]
    assert storage.zone_by_name("desk") == {"name": "desk", "label": "Desk", "start": 0, "end": 9}


def test_resizing_a_preceding_strip_is_blocked_when_it_would_remap_a_zone(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    first = storage.add_strip(pin=2, pixel_count=10, label="First")
    storage.add_strip(pin=4, pixel_count=10, label="Second")
    storage.add_zone("second", 10, 19)

    with pytest.raises(ValueError, match="would move existing zones to different physical pixels: second"):
        storage.update_strip(first["id"], pin=2, pixel_count=11, label="First")

    assert storage.strip_by_id(first["id"])["pixel_count"] == 10
    assert storage.zone_by_name("second") == {"name": "second", "label": "Second", "start": 10, "end": 19}


def test_reordering_strip_pins_is_blocked_when_it_would_remap_a_zone(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    first = storage.add_strip(pin=2, pixel_count=10, label="First")
    storage.add_strip(pin=4, pixel_count=10, label="Second")
    storage.add_zone("second", 10, 19)

    with pytest.raises(ValueError, match="would move existing zones to different physical pixels: second"):
        storage.update_strip(first["id"], pin=6, pixel_count=10, label="First")

    assert storage.strip_by_id(first["id"])["pin"] == 2


def test_safe_trailing_strip_changes_remain_available_with_existing_zones(tmp_path) -> None:
    storage = Storage(tmp_path / "data")
    storage.add_strip(pin=2, pixel_count=10, label="First")
    trailing = storage.add_strip(pin=4, pixel_count=10, label="Trailing")
    storage.add_zone("first", 0, 9)

    updated = storage.update_strip(trailing["id"], pin=4, pixel_count=12, label="Trailing")
    storage.delete_strip(trailing["id"])

    assert updated["pixel_count"] == 12
    assert storage.pixel_layout() == [
        {"id": 1, "pin": 2, "pixel_count": 10, "label": "First", "start": 0, "end": 9}
    ]
    assert storage.zone_by_name("first") == {"name": "first", "label": "First", "start": 0, "end": 9}
