from __future__ import annotations

import json

from led_web_v7.device_capabilities import (
    BUILTIN_EFFECT_IDS,
    BUILTIN_EFFECTS,
    MAX_ACTIVE_STRIPS,
    MAX_COMMAND_LENGTH,
    MAX_PIXELS_PER_STRIP,
    MAX_ZONES,
    SUPPORTED_DATA_PINS,
    bootstrap_capabilities,
    default_mode_records,
)


def test_v7_capability_contract_matches_the_compiled_firmware_limits() -> None:
    assert SUPPORTED_DATA_PINS == tuple(range(2, 14))
    assert MAX_ACTIVE_STRIPS == 12
    assert MAX_PIXELS_PER_STRIP == 300
    assert MAX_ZONES == 20
    assert MAX_COMMAND_LENGTH == 180
    assert tuple(effect.id for effect in BUILTIN_EFFECTS) == tuple(range(11))
    assert BUILTIN_EFFECT_IDS == frozenset(range(11))


def test_capability_payload_and_default_modes_are_independent_json_safe_snapshots() -> None:
    payload = bootstrap_capabilities()
    default_modes = default_mode_records()

    assert payload["supported_data_pins"] == list(SUPPORTED_DATA_PINS)
    assert payload["max_active_strips"] == MAX_ACTIVE_STRIPS
    assert payload["max_pixels_per_strip"] == MAX_PIXELS_PER_STRIP
    assert payload["max_zones"] == MAX_ZONES
    assert payload["max_command_length"] == MAX_COMMAND_LENGTH
    assert payload["builtin_effects"] == [
        {"id": effect.id, "key": effect.key, "label": effect.label} for effect in BUILTIN_EFFECTS
    ]
    json.dumps(payload)
    assert default_modes == [
        {"id": effect.id, "key": effect.key, "label": effect.label, "enabled": True, "system": True}
        for effect in BUILTIN_EFFECTS
    ]

    payload["supported_data_pins"].append(99)
    default_modes[0]["label"] = "Changed"

    assert bootstrap_capabilities()["supported_data_pins"] == list(SUPPORTED_DATA_PINS)
    assert default_mode_records()[0]["label"] == "Off"
