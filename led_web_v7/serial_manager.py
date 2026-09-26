from __future__ import annotations

import threading
import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import serial

from .config import AppConfig
from .device_capabilities import validate_command_payload
from .storage import Storage


@dataclass
class SerialEvent:
    at: float
    direction: str
    payload: str


class SerialManager:
    def __init__(self, storage: Storage, config: AppConfig) -> None:
        self.storage = storage
        self.config = config
        self._lock = threading.RLock()
        self._serial: serial.Serial | None = None
        self._history: deque[SerialEvent] = deque(maxlen=120)
        self._status: dict[str, Any] = {
            "connected": False,
            "last_error": None,
            "last_command": None,
            "last_response": None,
            "connected_at": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._status)

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"at": item.at, "direction": item.direction, "payload": item.payload}
                for item in self._history
            ]

    def _record(self, direction: str, payload: str) -> None:
        self._history.append(SerialEvent(at=time.time(), direction=direction, payload=payload))

    def connect(self, force: bool = False) -> serial.Serial:
        settings = self.storage.snapshot()["settings"]
        port = settings["serial_port"]
        baud = int(settings["baud_rate"])
        with self._lock:
            if (
                self._serial is not None
                and self._serial.is_open
                and not force
                and self._serial.port == port
                and self._serial.baudrate == baud
            ):
                return self._serial
            if self._serial is not None and self._serial.is_open:
                self._serial.close()
            self._serial = serial.Serial(port, baud, timeout=0.2, write_timeout=0.5)
            time.sleep(2)
            self._status["connected"] = True
            self._status["last_error"] = None
            self._status["connected_at"] = time.time()
            return self._serial

    def send(self, command: str) -> None:
        command = validate_command_payload(command)
        with self._lock:
            try:
                if self._serial is None or not self._serial.is_open:
                    self.connect()
                assert self._serial is not None
                self._serial.write((command + "\n").encode("utf-8"))
                self._serial.flush()
                self._record("out", command)
                self._status["connected"] = True
                self._status["last_error"] = None
                self._status["last_command"] = command
            except Exception as exc:
                self._status["connected"] = False
                self._status["last_error"] = str(exc)
                raise

    def read_lines(self, duration: float = 0.4) -> list[str]:
        lines: list[str] = []
        deadline = time.time() + duration
        while time.time() < deadline:
            with self._lock:
                if self._serial is not None and self._serial.is_open and self._serial.in_waiting:
                    raw = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if raw:
                        lines.append(raw)
                        self._record("in", raw)
                        self._status["last_response"] = raw
            time.sleep(0.02)
        return lines

    def drain(self, duration: float = 0.1) -> list[str]:
        return self.read_lines(duration)

    def query(self, command: str, duration: float = 0.4) -> list[str]:
        command = validate_command_payload(command)
        self.connect()
        self.drain(0.08)
        self.send(command)
        return self.read_lines(duration)
