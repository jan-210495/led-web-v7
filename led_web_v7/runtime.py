from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from .storage import Storage


class RuntimeState:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {
            "global": {
                "mode": 1,
                "last_active_mode": 1,
                "color": [255, 96, 32],
                "palette": [[255, 96, 32], [255, 0, 140], [0, 190, 255]],
                "brightness": 96,
                "delay_ms": 40,
                "enabled": True,
            },
            "zones": {},
        }
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        snapshot = self.storage.snapshot()
        zone_names = {zone["name"] for zone in snapshot["zones"]}
        with self._lock:
            self._state["zones"] = {
                name: self._state["zones"].get(
                    name,
                    {
                        "mode": 1,
                        "last_active_mode": 1,
                        "color": [255, 96, 32],
                        "palette": [[255, 96, 32], [255, 0, 140], [0, 190, 255]],
                        "brightness": 96,
                        "delay_ms": 40,
                        "enabled": True,
                    },
                )
                for name in zone_names
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def ensure_zone(self, name: str) -> dict[str, Any]:
        with self._lock:
            return self._state["zones"].setdefault(
                name,
                {
                    "mode": 1,
                    "last_active_mode": 1,
                    "color": [255, 96, 32],
                    "palette": [[255, 96, 32], [255, 0, 140], [0, 190, 255]],
                    "brightness": 96,
                    "delay_ms": 40,
                    "enabled": True,
                },
            )

    def drop_zone(self, name: str) -> None:
        with self._lock:
            self._state["zones"].pop(name, None)

    def set_zone(self, name: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            zone = self._state["zones"].setdefault(
                name,
                {
                    "mode": 1,
                    "last_active_mode": 1,
                    "color": [255, 96, 32],
                    "palette": [[255, 96, 32], [255, 0, 140], [0, 190, 255]],
                    "brightness": 96,
                    "delay_ms": 40,
                    "enabled": True,
                },
            )
            zone.update(updates)
            return deepcopy(zone)

    def set_global(self, **updates: Any) -> dict[str, Any]:
        with self._lock:
            self._state["global"].update(updates)
            return deepcopy(self._state["global"])

    def global_state(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state["global"])
