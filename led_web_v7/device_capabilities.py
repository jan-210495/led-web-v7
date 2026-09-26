"""Canonical Python mirror of the compiled V7 FastLED firmware capabilities.

Keep this module aligned with the constants and built-in effect switch in
``arduino/V7/V7.ino``. The Arduino sketch remains the hardware authority;
this module gives the web application one explicit contract for presentation
and validation work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


FIRMWARE_FAMILY = "V7 FastLED"
SUPPORTED_DATA_PINS: tuple[int, ...] = tuple(range(2, 14))
MAX_ACTIVE_STRIPS = 12
MAX_PIXELS_PER_STRIP = 300
MAX_ZONES = 20
MAX_COMMAND_LENGTH = 180


@dataclass(frozen=True)
class BuiltinEffect:
    """An effect ID implemented by the current V7 firmware switch statement."""

    id: int
    key: str
    label: str


BUILTIN_EFFECTS: tuple[BuiltinEffect, ...] = (
    BuiltinEffect(0, "off", "Off"),
    BuiltinEffect(1, "solid", "Solid"),
    BuiltinEffect(2, "rainbow", "Rainbow"),
    BuiltinEffect(3, "chase", "Chase"),
    BuiltinEffect(4, "scanner", "Scanner"),
    BuiltinEffect(5, "breathing", "Breathing"),
    BuiltinEffect(6, "wave", "Wave"),
    BuiltinEffect(7, "chroma", "Chroma"),
    BuiltinEffect(8, "colorwaves", "Colorwaves"),
    BuiltinEffect(9, "twinkle", "Twinkle"),
    BuiltinEffect(10, "confetti", "Confetti"),
)
BUILTIN_EFFECT_IDS: frozenset[int] = frozenset(effect.id for effect in BUILTIN_EFFECTS)


def default_mode_records() -> list[dict[str, Any]]:
    """Return fresh storage records for effects compiled into the firmware."""
    return [{**asdict(effect), "enabled": True, "system": True} for effect in BUILTIN_EFFECTS]


def bootstrap_capabilities() -> dict[str, Any]:
    """Return a JSON-safe, fresh snapshot for templates and API clients."""
    return {
        "firmware_family": FIRMWARE_FAMILY,
        "supported_data_pins": list(SUPPORTED_DATA_PINS),
        "max_active_strips": MAX_ACTIVE_STRIPS,
        "max_pixels_per_strip": MAX_PIXELS_PER_STRIP,
        "max_zones": MAX_ZONES,
        "max_command_length": MAX_COMMAND_LENGTH,
        "builtin_effects": [asdict(effect) for effect in BUILTIN_EFFECTS],
    }
