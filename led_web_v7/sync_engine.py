from __future__ import annotations

import threading
import time
from collections import deque
from copy import deepcopy
from typing import Any

from serial import SerialException

from .runtime import RuntimeState
from .serial_manager import SerialManager
from .storage import Storage


class SyncEngine:
    def __init__(self, storage: Storage, runtime: RuntimeState, serial_manager: SerialManager) -> None:
        self.storage = storage
        self.runtime = runtime
        self.serial = serial_manager
        self._lock = threading.RLock()
        self._pending_lock = threading.Lock()
        self._worker_started = False
        self._direct_queue: deque[str] = deque()
        self._pending_updates: dict[str, Any] = {"global": {}, "zones": {}}
        self._sync_state: dict[str, Any] = {
            "last_layout_sync_at": None,
            "last_layout_sync_reason": None,
            "last_layout_sync_ok": None,
            "last_layout_sync_error": None,
        }

    def start(self) -> None:
        if self._worker_started:
            return
        worker = threading.Thread(target=self._flush_loop, daemon=True)
        worker.start()
        self._worker_started = True

    def sync_status(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._sync_state)

    def queue_direct(self, command: str) -> None:
        with self._pending_lock:
            self._direct_queue.append(command)

    def queue_global(self, key: str, value: Any) -> None:
        with self._pending_lock:
            self._pending_updates["global"][key] = value

    def queue_zone(self, name: str, key: str, value: Any) -> None:
        with self._pending_lock:
            payload = self._pending_updates["zones"].setdefault(name, {})
            payload[key] = value

    def clear_zone_pending(self, name: str) -> None:
        with self._pending_lock:
            self._pending_updates["zones"].pop(name, None)

    def clear_global_pending(self) -> None:
        with self._pending_lock:
            self._pending_updates["global"].clear()

    def _palette_command(self, prefix: str, palette: list[list[int]]) -> str:
        parts = ["{},{},{}".format(int(color[0]), int(color[1]), int(color[2])) for color in palette[:3]]
        while len(parts) < 3:
            parts.append(parts[-1] if parts else "255,96,32")
        return f"{prefix}:{';'.join(parts[:3])}"

    def sync_strips(self) -> None:
        snapshot = self.storage.snapshot()
        self.serial.connect()
        self.serial.send("CLEAR_STRIPS")
        time.sleep(0.05)
        for strip in sorted(snapshot["strips"], key=lambda item: int(item["pin"])):
            self.serial.send(f"ADD_STRIP:{int(strip['pin'])}:{int(strip['pixel_count'])}")
            time.sleep(0.03)

    def sync_zones(self) -> None:
        snapshot = self.storage.snapshot()
        self.serial.connect()
        lines = self.serial.query("LIST_ZONES", duration=0.5)
        existing = []
        for line in lines:
            if line.startswith("ZONE:"):
                parts = line.split(":")
                if len(parts) >= 4:
                    existing.append(parts[1])
        for name in existing:
            self.serial.send(f"DELETE_ZONE:{name}")
            time.sleep(0.03)
        for zone in snapshot["zones"]:
            self.serial.send(f"CREATE_ZONE:{zone['name']}:{zone['start']}:{zone['end']}")
            time.sleep(0.03)

    def sync_layout(self, reason: str = "manual") -> None:
        try:
            self.sync_strips()
            time.sleep(0.05)
            self.sync_zones()
            self._set_sync_state(reason, True, None)
        except Exception as exc:
            self._set_sync_state(reason, False, str(exc))

    def _set_sync_state(self, reason: str, ok: bool, error: str | None) -> None:
        with self._lock:
            self._sync_state["last_layout_sync_at"] = time.time()
            self._sync_state["last_layout_sync_reason"] = reason
            self._sync_state["last_layout_sync_ok"] = ok
            self._sync_state["last_layout_sync_error"] = error

    def _flush_loop(self) -> None:
        while True:
            config = self.storage.snapshot()["settings"]
            interval = max(int(config["flush_interval_ms"]), 10) / 1000.0
            direct_commands: list[str] = []
            global_payload: dict[str, Any] = {}
            zone_payloads: dict[str, dict[str, Any]] = {}
            with self._pending_lock:
                while self._direct_queue:
                    direct_commands.append(self._direct_queue.popleft())
                if self._pending_updates["global"]:
                    global_payload = deepcopy(self._pending_updates["global"])
                    self._pending_updates["global"].clear()
                if self._pending_updates["zones"]:
                    zone_payloads = deepcopy(self._pending_updates["zones"])
                    self._pending_updates["zones"].clear()
            try:
                for command in direct_commands:
                    self.serial.send(command)
                    time.sleep(0.01)
                if global_payload:
                    mode_value = global_payload.get("mode")
                    palette_value = global_payload.get("palette")
                    if palette_value:
                        self.serial.send(self._palette_command("ALL_PALETTE", palette_value))
                    if "delay_ms" in global_payload:
                        self.serial.send(f"ALL_DELAY:{int(global_payload['delay_ms'])}")
                    if mode_value is not None:
                        self.serial.send(f"ALL_MODE:{mode_value}")
                    if mode_value != 0:
                        if "color" in global_payload:
                            r, g, b = global_payload["color"]
                            self.serial.send(f"ALL_COLOR:{r},{g},{b}")
                        if "brightness" in global_payload:
                            self.serial.send(f"ALL_BRIGHTNESS:{global_payload['brightness']}")
                for zone_name in sorted(zone_payloads):
                    payload = zone_payloads[zone_name]
                    mode_value = payload.get("mode")
                    palette_value = payload.get("palette")
                    if palette_value:
                        self.serial.send(self._palette_command(f"ZONE_PALETTE:{zone_name}", palette_value))
                    if "delay_ms" in payload:
                        self.serial.send(f"ZONE_DELAY:{zone_name}:{int(payload['delay_ms'])}")
                    if mode_value is not None:
                        self.serial.send(f"ZONE_MODE:{zone_name}:{mode_value}")
                    if mode_value == 0:
                        continue
                    if "color" in payload:
                        r, g, b = payload["color"]
                        self.serial.send(f"ZONE_COLOR:{zone_name}:{r},{g},{b}")
                    if "brightness" in payload:
                        self.serial.send(f"ZONE_BRIGHTNESS:{zone_name}:{payload['brightness']}")
            except SerialException:
                pass
            except Exception:
                pass
            time.sleep(interval)
