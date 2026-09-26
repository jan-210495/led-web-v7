from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any


NAME_RE = re.compile(r"^[a-z0-9_]+$")

DEFAULT_STRIPS: list[dict[str, Any]] = []
DEFAULT_ZONES: list[dict[str, Any]] = []
DEFAULT_MODES: list[dict[str, Any]] = [
    {"id": 0, "key": "off", "label": "Off", "enabled": True, "system": True},
    {"id": 1, "key": "solid", "label": "Solid", "enabled": True, "system": True},
    {"id": 2, "key": "rainbow", "label": "Rainbow", "enabled": True, "system": True},
    {"id": 3, "key": "chase", "label": "Chase", "enabled": True, "system": True},
    {"id": 4, "key": "scanner", "label": "Scanner", "enabled": True, "system": True},
    {"id": 5, "key": "breathing", "label": "Breathing", "enabled": True, "system": True},
    {"id": 6, "key": "wave", "label": "Wave", "enabled": True, "system": True},
    {"id": 7, "key": "chroma", "label": "Chroma", "enabled": True, "system": True},
    {"id": 8, "key": "colorwaves", "label": "Colorwaves", "enabled": True, "system": True},
    {"id": 9, "key": "twinkle", "label": "Twinkle", "enabled": True, "system": True},
    {"id": 10, "key": "confetti", "label": "Confetti", "enabled": True, "system": True},
]
DEFAULT_SETTINGS: dict[str, Any] = {
    "serial_port": "/dev/ttyACM0",
    "baud_rate": 115200,
    "flush_interval_ms": 50,
    "pin_options": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
}
DEFAULT_PRESETS: list[dict[str, Any]] = []


class StorageDataError(RuntimeError):
    """Persistent controller data could not be read or written safely."""


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._paths = {
            "strips": self.data_dir / "strips.json",
            "zones": self.data_dir / "zones.json",
            "modes": self.data_dir / "modes.json",
            "settings": self.data_dir / "settings.json",
            "presets": self.data_dir / "presets.json",
        }
        self._strips: list[dict[str, Any]] = []
        self._zones: list[dict[str, Any]] = []
        self._modes: list[dict[str, Any]] = []
        self._settings: dict[str, Any] = {}
        self._presets: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        with self._lock:
            self._strips = self._read_json("strips", DEFAULT_STRIPS)
            self._zones = self._read_json("zones", DEFAULT_ZONES)
            self._modes = self._normalize_modes(self._read_json("modes", DEFAULT_MODES))
            self._settings = self._read_json("settings", DEFAULT_SETTINGS)
            self._presets = self._normalize_presets(self._read_json("presets", DEFAULT_PRESETS))
            self._persist_all()

    def _read_json(self, key: str, default: Any) -> Any:
        path = self._paths[key]
        if not path.exists():
            self._write_json(path, deepcopy(default))
            return deepcopy(default)

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise StorageDataError(
                f"Data file '{path}' contains invalid JSON at line {exc.lineno}, column {exc.colno}: "
                f"{exc.msg}. The file was not changed; repair it or restore a backup before restarting."
            ) from exc
        except UnicodeDecodeError as exc:
            raise StorageDataError(
                f"Data file '{path}' is not valid UTF-8: {exc}. "
                "The file was not changed; repair it or restore a backup before restarting."
            ) from exc
        except OSError as exc:
            raise StorageDataError(f"Could not read data file '{path}': {exc}") from exc

        expected_type = type(default)
        if not isinstance(payload, expected_type):
            raise StorageDataError(
                f"Data file '{path}' must contain a JSON {expected_type.__name__}, "
                f"not {type(payload).__name__}. The file was not changed; repair it or restore a backup before restarting."
            )
        return payload

    def _write_json(self, path: Path, payload: Any) -> None:
        """Write JSON through a same-directory staging file, then atomically replace the target."""
        temporary_path: Path | None = None
        replaced_target = False
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary_path, path)
            temporary_path = None
            replaced_target = True
            self._fsync_directory(path.parent)
        except OSError as exc:
            recovery_note = (
                "The target may already contain the new data; verify it before retrying."
                if replaced_target
                else "The existing target was left unchanged."
            )
            raise StorageDataError(f"Could not safely write data file '{path}': {exc}. {recovery_note}") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Persist the rename metadata on filesystems that support directory fsync."""
        if os.name == "nt":
            return
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _persist_all(self) -> None:
        self._write_json(self._paths["strips"], self._strips)
        self._write_json(self._paths["zones"], self._zones)
        self._write_json(self._paths["modes"], self._modes)
        self._write_json(self._paths["settings"], self._settings)
        self._write_json(self._paths["presets"], self._presets)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "strips": deepcopy(self._strips),
                "zones": deepcopy(self._zones),
                "modes": deepcopy(self._modes),
                "settings": deepcopy(self._settings),
                "presets": deepcopy(self._presets),
                "total_pixels": self.total_pixels(),
            }

    def total_pixels(self) -> int:
        return sum(int(strip["pixel_count"]) for strip in self._strips)

    def pixel_layout(self) -> list[dict[str, Any]]:
        layout = []
        cursor = 0
        for strip in self._strips:
            count = int(strip["pixel_count"])
            layout.append(
                {
                    **deepcopy(strip),
                    "start": cursor,
                    "end": cursor + count - 1 if count else cursor,
                }
            )
            cursor += count
        return layout

    def strip_by_id(self, strip_id: int) -> dict[str, Any] | None:
        for strip in self._strips:
            if int(strip["id"]) == int(strip_id):
                return deepcopy(strip)
        return None

    def zone_by_name(self, name: str) -> dict[str, Any] | None:
        for zone in self._zones:
            if zone["name"] == name:
                return deepcopy(zone)
        return None

    def enabled_modes(self) -> list[dict[str, Any]]:
        return [mode for mode in self._modes if mode["enabled"]]

    def _normalize_name(self, value: str) -> str:
        name = value.strip().lower()
        if not name:
            raise ValueError("Name is required")
        if not NAME_RE.match(name):
            raise ValueError("Name must use lowercase letters, numbers, and underscores")
        return name

    def _normalize_label(self, name: str, label: str | None) -> str:
        return (label or "").strip() or name.replace("_", " ").title()

    def _normalize_modes(self, modes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_by_id: dict[int, dict[str, Any]] = {}
        for mode in modes:
            mode_id = int(mode["id"])
            normalized_by_id[mode_id] = {
                "id": mode_id,
                "key": str(mode.get("key") or f"mode_{mode_id}").strip().lower(),
                "label": str(mode.get("label") or f"Mode {mode_id}").strip(),
                "enabled": bool(mode.get("enabled", True)),
                "system": bool(mode.get("system", False)),
            }
        for mode in DEFAULT_MODES:
            mode_id = int(mode["id"])
            if mode_id not in normalized_by_id:
                normalized_by_id[mode_id] = deepcopy(mode)
        normalized = list(normalized_by_id.values())
        normalized.sort(key=lambda item: item["id"])
        return normalized

    def _normalize_palette(self, palette: Any) -> list[list[int]]:
        default_palette = [[255, 96, 32], [255, 0, 140], [0, 190, 255]]
        if not isinstance(palette, list) or not palette:
            return deepcopy(default_palette)
        normalized: list[list[int]] = []
        for item in palette[:3]:
            if not isinstance(item, list) or len(item) != 3:
                continue
            normalized.append([max(0, min(255, int(channel))) for channel in item])
        while len(normalized) < 3:
            normalized.append(list(normalized[-1] if normalized else default_palette[len(normalized)]))
        return normalized[:3]

    def _normalize_presets(self, presets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        seen_ids: set[int] = set()
        for preset in presets:
            preset_id = int(preset.get("id") or 0)
            if preset_id <= 0 or preset_id in seen_ids:
                continue
            seen_ids.add(preset_id)
            zone_configs = []
            for zone in preset.get("zone_configs", []):
                zone_name = str(zone.get("zone") or "").strip()
                if not zone_name:
                    continue
                zone_configs.append(
                    {
                        "zone": zone_name,
                        "enabled": bool(zone.get("enabled", True)),
                        "mode": int(zone.get("mode", 1)),
                        "brightness": max(0, min(255, int(zone.get("brightness", 96)))),
                        "delay_ms": max(10, min(2000, int(zone.get("delay_ms", 40)))),
                        "palette": self._normalize_palette(zone.get("palette")),
                    }
                )
            normalized.append(
                {
                    "id": preset_id,
                    "name": str(preset.get("name") or f"Preset {preset_id}").strip(),
                    "description": str(preset.get("description") or "").strip(),
                    "global_brightness": max(0, min(255, int(preset.get("global_brightness", 96)))),
                    "zone_configs": zone_configs,
                }
            )
        normalized.sort(key=lambda item: item["id"])
        return normalized

    def _validate_zone_range(self, start: int, end: int, ignore_name: str | None = None) -> None:
        total_pixels = self.total_pixels()
        if total_pixels <= 0:
            raise ValueError("Add at least one strip before creating zones")
        if start < 0 or end < 0:
            raise ValueError("Pixels must be >= 0")
        if start > end:
            raise ValueError("Start pixel must be <= end pixel")
        if end >= total_pixels:
            raise ValueError(f"End pixel must be < total pixel count ({total_pixels})")
        for zone in self._zones:
            if ignore_name and zone["name"] == ignore_name:
                continue
            overlaps = not (end < int(zone["start"]) or start > int(zone["end"]))
            if overlaps:
                raise ValueError(f"Overlap with zone '{zone['name']}' ({zone['start']}-{zone['end']})")

    def add_strip(self, pin: int, pixel_count: int, label: str | None = None) -> dict[str, Any]:
        with self._lock:
            pin = int(pin)
            pixel_count = int(pixel_count)
            if pin < 0:
                raise ValueError("Pin must be >= 0")
            if pixel_count <= 0:
                raise ValueError("Pixel count must be > 0")
            if any(int(strip["pin"]) == pin for strip in self._strips):
                raise ValueError(f"Pin {pin} is already assigned")

            next_id = max([int(strip["id"]) for strip in self._strips], default=0) + 1
            strip = {
                "id": next_id,
                "pin": pin,
                "pixel_count": pixel_count,
                "label": (label or "").strip() or f"Pin {pin}",
            }
            self._strips.append(strip)
            self._strips.sort(key=lambda item: int(item["pin"]))
            self._write_json(self._paths["strips"], self._strips)
            return deepcopy(strip)

    def update_strip(self, strip_id: int, pin: int, pixel_count: int, label: str | None = None) -> dict[str, Any]:
        with self._lock:
            pin = int(pin)
            pixel_count = int(pixel_count)
            if pixel_count <= 0:
                raise ValueError("Pixel count must be > 0")
            target = None
            for strip in self._strips:
                if int(strip["id"]) == int(strip_id):
                    target = strip
                    break
            if target is None:
                raise ValueError("Strip not found")
            if any(int(strip["pin"]) == pin and int(strip["id"]) != int(strip_id) for strip in self._strips):
                raise ValueError(f"Pin {pin} is already assigned")

            new_total = self.total_pixels() - int(target["pixel_count"]) + pixel_count
            for zone in self._zones:
                if int(zone["end"]) >= new_total:
                    raise ValueError("Resize would cut off existing zones. Update or delete those zones first.")

            target["pin"] = pin
            target["pixel_count"] = pixel_count
            target["label"] = (label or "").strip() or f"Pin {pin}"
            self._strips.sort(key=lambda item: int(item["pin"]))
            self._write_json(self._paths["strips"], self._strips)
            return deepcopy(target)

    def delete_strip(self, strip_id: int) -> None:
        with self._lock:
            target = self.strip_by_id(strip_id)
            if target is None:
                raise ValueError("Strip not found")
            remaining = [strip for strip in self._strips if int(strip["id"]) != int(strip_id)]
            total_after_delete = sum(int(strip["pixel_count"]) for strip in remaining)
            for zone in self._zones:
                if int(zone["end"]) >= total_after_delete:
                    raise ValueError("Delete would leave zones outside the available pixel range")
            self._strips = remaining
            self._write_json(self._paths["strips"], self._strips)

    def add_zone(self, name: str, start: int, end: int, label: str | None = None) -> dict[str, Any]:
        with self._lock:
            zone_name = self._normalize_name(name)
            if self.zone_by_name(zone_name):
                raise ValueError("Zone already exists")
            start = int(start)
            end = int(end)
            self._validate_zone_range(start, end)
            zone = {
                "name": zone_name,
                "label": self._normalize_label(zone_name, label),
                "start": start,
                "end": end,
            }
            self._zones.append(zone)
            self._zones.sort(key=lambda item: int(item["start"]))
            self._write_json(self._paths["zones"], self._zones)
            return deepcopy(zone)

    def update_zone(self, name: str, start: int, end: int, label: str | None = None) -> dict[str, Any]:
        with self._lock:
            target = None
            for zone in self._zones:
                if zone["name"] == name:
                    target = zone
                    break
            if target is None:
                raise ValueError("Zone not found")
            start = int(start)
            end = int(end)
            self._validate_zone_range(start, end, ignore_name=name)
            target["start"] = start
            target["end"] = end
            target["label"] = self._normalize_label(name, label)
            self._zones.sort(key=lambda item: int(item["start"]))
            self._write_json(self._paths["zones"], self._zones)
            return deepcopy(target)

    def delete_zone(self, name: str) -> None:
        with self._lock:
            if not self.zone_by_name(name):
                raise ValueError("Zone not found")
            self._zones = [zone for zone in self._zones if zone["name"] != name]
            self._write_json(self._paths["zones"], self._zones)

    def add_mode(self, mode_id: int, label: str, enabled: bool = True) -> dict[str, Any]:
        with self._lock:
            mode_id = int(mode_id)
            if any(int(mode["id"]) == mode_id for mode in self._modes):
                raise ValueError("Mode ID already exists")
            if mode_id < 0:
                raise ValueError("Mode ID must be >= 0")
            cleaned_label = (label or "").strip()
            if not cleaned_label:
                raise ValueError("Mode label is required")
            mode = {
                "id": mode_id,
                "key": cleaned_label.lower().replace(" ", "_"),
                "label": cleaned_label,
                "enabled": bool(enabled),
                "system": False,
            }
            self._modes.append(mode)
            self._modes.sort(key=lambda item: int(item["id"]))
            self._write_json(self._paths["modes"], self._modes)
            return deepcopy(mode)

    def update_mode(self, mode_id: int, label: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            target = None
            for mode in self._modes:
                if int(mode["id"]) == int(mode_id):
                    target = mode
                    break
            if target is None:
                raise ValueError("Mode not found")
            cleaned_label = (label or "").strip()
            if not cleaned_label:
                raise ValueError("Mode label is required")
            target["label"] = cleaned_label
            target["enabled"] = bool(enabled)
            target["key"] = cleaned_label.lower().replace(" ", "_")
            self._write_json(self._paths["modes"], self._modes)
            return deepcopy(target)

    def delete_mode(self, mode_id: int) -> None:
        with self._lock:
            target = None
            for mode in self._modes:
                if int(mode["id"]) == int(mode_id):
                    target = mode
                    break
            if target is None:
                raise ValueError("Mode not found")
            if target["system"]:
                raise ValueError("Built-in modes cannot be deleted. Disable them instead.")
            self._modes = [mode for mode in self._modes if int(mode["id"]) != int(mode_id)]
            self._write_json(self._paths["modes"], self._modes)

    def update_settings(self, serial_port: str, baud_rate: int, flush_interval_ms: int) -> dict[str, Any]:
        with self._lock:
            serial_port = serial_port.strip()
            if not serial_port:
                raise ValueError("Serial port is required")
            baud_rate = int(baud_rate)
            flush_interval_ms = int(flush_interval_ms)
            if baud_rate <= 0:
                raise ValueError("Baud rate must be > 0")
            if flush_interval_ms < 10:
                raise ValueError("Flush interval must be >= 10ms")
            self._settings["serial_port"] = serial_port
            self._settings["baud_rate"] = baud_rate
            self._settings["flush_interval_ms"] = flush_interval_ms
            self._write_json(self._paths["settings"], self._settings)
            return deepcopy(self._settings)

    def preset_by_id(self, preset_id: int) -> dict[str, Any] | None:
        for preset in self._presets:
            if int(preset["id"]) == int(preset_id):
                return deepcopy(preset)
        return None

    def add_preset(
        self,
        name: str,
        description: str,
        global_brightness: int,
        zone_configs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            cleaned_name = (name or "").strip()
            if not cleaned_name:
                raise ValueError("Preset name is required")
            next_id = max([int(item["id"]) for item in self._presets], default=0) + 1
            preset = self._normalize_presets(
                [
                    {
                        "id": next_id,
                        "name": cleaned_name,
                        "description": description,
                        "global_brightness": global_brightness,
                        "zone_configs": zone_configs,
                    }
                ]
            )[0]
            self._presets.append(preset)
            self._presets.sort(key=lambda item: int(item["id"]))
            self._write_json(self._paths["presets"], self._presets)
            return deepcopy(preset)

    def update_preset(
        self,
        preset_id: int,
        name: str,
        description: str,
        global_brightness: int,
        zone_configs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            target_index = None
            for index, preset in enumerate(self._presets):
                if int(preset["id"]) == int(preset_id):
                    target_index = index
                    break
            if target_index is None:
                raise ValueError("Preset not found")
            cleaned_name = (name or "").strip()
            if not cleaned_name:
                raise ValueError("Preset name is required")
            preset = self._normalize_presets(
                [
                    {
                        "id": int(preset_id),
                        "name": cleaned_name,
                        "description": description,
                        "global_brightness": global_brightness,
                        "zone_configs": zone_configs,
                    }
                ]
            )[0]
            self._presets[target_index] = preset
            self._write_json(self._paths["presets"], self._presets)
            return deepcopy(preset)

    def delete_preset(self, preset_id: int) -> None:
        with self._lock:
            if self.preset_by_id(preset_id) is None:
                raise ValueError("Preset not found")
            self._presets = [preset for preset in self._presets if int(preset["id"]) != int(preset_id)]
            self._write_json(self._paths["presets"], self._presets)
