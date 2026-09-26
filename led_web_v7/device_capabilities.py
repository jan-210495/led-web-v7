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
# The firmware allocates this many bytes for the command plus its NUL terminator.
MAX_COMMAND_LENGTH = 180
MAX_COMMAND_PAYLOAD_LENGTH = MAX_COMMAND_LENGTH - 1
MAX_COLOR_COMPONENT = 255
MIN_DELAY_MS = 10
MAX_DELAY_MS = 2000


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

_MAX_PALETTE_COMPONENT = "255,255,255"
_MAX_ZONE_PALETTE_COMMAND_SUFFIX = ":" + ";".join([_MAX_PALETTE_COMPONENT] * 3)
MAX_ZONE_NAME_LENGTH = (
    MAX_COMMAND_PAYLOAD_LENGTH
    - len("ZONE_PALETTE:".encode("utf-8"))
    - len(_MAX_ZONE_PALETTE_COMMAND_SUFFIX.encode("utf-8"))
)


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
        "max_command_payload_length": MAX_COMMAND_PAYLOAD_LENGTH,
        "max_zone_name_length": MAX_ZONE_NAME_LENGTH,
        "builtin_effects": [asdict(effect) for effect in BUILTIN_EFFECTS],
    }


def _coerce_integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc


def validate_supported_data_pin(value: Any) -> int:
    """Return a supported pin or raise an operator-friendly validation error."""
    pin = _coerce_integer(value, "Pin")
    if pin not in SUPPORTED_DATA_PINS:
        choices = ", ".join(str(item) for item in SUPPORTED_DATA_PINS)
        raise ValueError(f"Pin {pin} is not supported by V7 firmware. Choose one of: {choices}")
    return pin


def validate_pixel_count(value: Any) -> int:
    """Return a V7-supported strip length."""
    pixel_count = _coerce_integer(value, "Pixel count")
    if not 1 <= pixel_count <= MAX_PIXELS_PER_STRIP:
        raise ValueError(f"Pixel count must be between 1 and {MAX_PIXELS_PER_STRIP}")
    return pixel_count


def validate_effect_id(value: Any) -> int:
    """Return an effect ID compiled into the V7 firmware."""
    mode_id = _coerce_integer(value, "Mode ID")
    if mode_id not in BUILTIN_EFFECT_IDS:
        available = ", ".join(str(item) for item in sorted(BUILTIN_EFFECT_IDS))
        raise ValueError(f"Mode ID {mode_id} is not supported by V7 firmware. Available IDs: {available}")
    return mode_id


def validate_byte(value: Any, label: str) -> int:
    """Return a color/brightness component accepted by the firmware."""
    component = _coerce_integer(value, label)
    if not 0 <= component <= MAX_COLOR_COMPONENT:
        raise ValueError(f"{label} must be between 0 and {MAX_COLOR_COMPONENT}")
    return component


def validate_rgb(value: Any, label: str = "Color") -> list[int]:
    """Return an RGB triplet that cannot overflow the serial protocol."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must contain exactly three RGB components")
    return [validate_byte(component, f"{label} component") for component in value]


def validate_palette(value: Any) -> list[list[int]]:
    """Return the three RGB colors required by palette commands."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Palette must contain exactly three RGB colors")
    return [validate_rgb(color, "Palette color") for color in value]


def validate_delay_ms(value: Any) -> int:
    """Return an animation delay accepted by the firmware."""
    delay_ms = _coerce_integer(value, "Delay")
    if not MIN_DELAY_MS <= delay_ms <= MAX_DELAY_MS:
        raise ValueError(f"Delay must be between {MIN_DELAY_MS} and {MAX_DELAY_MS}ms")
    return delay_ms


def validate_live_control_value(key: str, value: Any) -> Any:
    """Normalize every queueable live-control value before command construction."""
    validators = {
        "mode": validate_effect_id,
        "brightness": lambda item: validate_byte(item, "Brightness"),
        "color": validate_rgb,
        "palette": validate_palette,
        "delay_ms": validate_delay_ms,
    }
    try:
        return validators[key](value)
    except KeyError as exc:
        raise ValueError(f"Unsupported live control field '{key}'") from exc


def validate_command_payload(command: str) -> str:
    """Return a command guaranteed to fit the firmware's newline-delimited input buffer."""
    if not isinstance(command, str):
        raise ValueError("Serial command must be text")
    if "\n" in command or "\r" in command:
        raise ValueError("Serial command must not contain line breaks")
    try:
        byte_length = len(command.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("Serial command must contain valid UTF-8 text") from exc
    if byte_length > MAX_COMMAND_PAYLOAD_LENGTH:
        raise ValueError(
            f"Serial command is {byte_length} UTF-8 bytes; V7 accepts at most "
            f"{MAX_COMMAND_PAYLOAD_LENGTH} bytes before the newline terminator"
        )
    return command


def validate_zone_name_command_length(name: str) -> str:
    """Ensure a zone name still fits the longest V7 zone command (palette update)."""
    if not isinstance(name, str):
        raise ValueError("Zone name must be text")
    byte_length = len(name.encode("utf-8"))
    if byte_length > MAX_ZONE_NAME_LENGTH:
        raise ValueError(
            f"Zone name is {byte_length} UTF-8 bytes; V7 supports at most "
            f"{MAX_ZONE_NAME_LENGTH} bytes so palette commands fit the serial buffer"
        )
    return name
