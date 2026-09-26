from __future__ import annotations

from pathlib import Path

import pytest

from led_web_v7.config import AppConfig
from led_web_v7.device_capabilities import MAX_COMMAND_PAYLOAD_LENGTH, MAX_ZONE_NAME_LENGTH
from led_web_v7.runtime import RuntimeState
from led_web_v7.serial_manager import SerialManager
from led_web_v7.storage import Storage
from led_web_v7.sync_engine import SyncEngine


def build_sync_engine(tmp_path: Path) -> tuple[SerialManager, SyncEngine]:
    storage = Storage(tmp_path / "data")
    config = AppConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        templates_dir=tmp_path / "templates",
        static_dir=tmp_path / "static",
        host="127.0.0.1",
        port=5070,
        secret_key="test-secret",
    )
    serial_manager = SerialManager(storage, config)
    return serial_manager, SyncEngine(storage, RuntimeState(storage), serial_manager)


def test_oversized_or_invalid_live_commands_never_enter_the_sync_queue(tmp_path: Path) -> None:
    _serial_manager, sync_engine = build_sync_engine(tmp_path)

    with pytest.raises(ValueError, match="V7 accepts at most 179 bytes"):
        sync_engine.queue_direct("X" * (MAX_COMMAND_PAYLOAD_LENGTH + 1))
    with pytest.raises(ValueError, match="must not contain line breaks"):
        sync_engine.queue_direct("ALL_OFF\nALL_MODE:1")
    with pytest.raises(ValueError, match="Mode ID 11 is not supported"):
        sync_engine.queue_global("mode", 11)
    with pytest.raises(ValueError, match="Brightness must be between 0 and 255"):
        sync_engine.queue_global("brightness", 256)
    with pytest.raises(ValueError, match="Color must contain exactly three RGB components"):
        sync_engine.queue_zone("desk", "color", [255, 0])
    with pytest.raises(ValueError, match="V7 supports at most"):
        sync_engine.queue_zone("z" * (MAX_ZONE_NAME_LENGTH + 1), "mode", 1)

    assert list(sync_engine._direct_queue) == []
    assert sync_engine._pending_updates == {"global": {}, "zones": {}}


def test_serial_manager_rejects_oversized_commands_before_opening_a_port(tmp_path: Path) -> None:
    serial_manager, _sync_engine = build_sync_engine(tmp_path)

    with pytest.raises(ValueError, match="V7 accepts at most 179 bytes"):
        serial_manager.send("X" * (MAX_COMMAND_PAYLOAD_LENGTH + 1))
    with pytest.raises(ValueError, match="V7 accepts at most 179 bytes"):
        serial_manager.query("X" * (MAX_COMMAND_PAYLOAD_LENGTH + 1))

    assert serial_manager.status() == {
        "connected": False,
        "last_error": None,
        "last_command": None,
        "last_response": None,
        "connected_at": None,
    }
