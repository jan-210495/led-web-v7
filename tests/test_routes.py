from __future__ import annotations

import pytest

from led_web_v7.device_capabilities import (
    MAX_PIXELS_PER_STRIP,
    MAX_ZONE_NAME_LENGTH,
    SUPPORTED_DATA_PINS,
    bootstrap_capabilities,
)


def test_bootstrap_uses_isolated_default_data_and_never_needs_serial_hardware(client) -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["strips"] == []
    assert payload["zones"] == []
    assert payload["presets"] == []
    assert payload["total_pixels"] == 0
    assert [mode["id"] for mode in payload["enabled_modes"]] == list(range(11))
    assert payload["device_capabilities"] == bootstrap_capabilities()
    assert "pin_options" not in payload["settings"]
    assert payload["serial_status"]["connected"] is False


def test_api_rejects_values_outside_the_firmware_contract(client) -> None:
    unsupported_pin = client.post("/api/strips", json={"pin": 1, "pixel_count": 1, "label": "Bad pin"})
    oversized_strip = client.post("/api/strips", json={"pin": 2, "pixel_count": 301, "label": "Too long"})
    supported_strip = client.post("/api/strips", json={"pin": 2, "pixel_count": 1, "label": "Desk"})
    oversized_zone_name = client.post(
        "/api/zones",
        json={"name": "z" * (MAX_ZONE_NAME_LENGTH + 1), "start": 0, "end": 0},
    )
    unsupported_mode = client.post("/api/modes", json={"id": 11, "label": "Not compiled", "enabled": True})
    invalid_preset = client.post(
        "/api/presets",
        json={
            "name": "Invalid effect",
            "description": "",
            "global_brightness": 96,
            "zone_configs": [{"zone": "desk", "mode": 11, "brightness": 96, "delay_ms": 40, "palette": []}],
        },
    )

    assert unsupported_pin.status_code == 400
    assert unsupported_pin.get_json()["message"] == "Pin 1 is not supported by V7 firmware. Choose one of: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13"
    assert oversized_strip.status_code == 400
    assert oversized_strip.get_json()["message"] == "Pixel count must be between 1 and 300"
    assert supported_strip.status_code == 200
    assert oversized_zone_name.status_code == 400
    assert oversized_zone_name.get_json()["message"].startswith("Zone name is")
    assert unsupported_mode.status_code == 400
    assert unsupported_mode.get_json()["message"].startswith("Mode ID 11 is not supported by V7 firmware")
    assert invalid_preset.status_code == 400
    assert invalid_preset.get_json()["message"].startswith("Mode ID 11 is not supported by V7 firmware")


def test_live_socket_rejects_an_uncompiled_effect_before_queueing(client, app) -> None:
    client.post("/api/strips", json={"pin": 2, "pixel_count": 1, "label": "Desk"})
    client.post("/api/zones", json={"name": "desk", "start": 0, "end": 0})
    socket_client = app.extensions["test.socketio"].test_client(app)
    socket_client.get_received()

    with pytest.raises(ValueError, match="Mode ID 11 is not supported"):
        socket_client.emit("zone_mode", {"zone": "desk", "mode": 11})

    assert app.extensions["led.runtime"].snapshot()["zones"]["desk"]["mode"] == 1
    assert app.extensions["led.sync"]._pending_updates == {"global": {}, "zones": {}}


def test_configuration_page_uses_the_canonical_supported_pin_list(client) -> None:
    response = client.get("/config")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="new_strip_pin"' in page
    for pin in SUPPORTED_DATA_PINS:
        assert f'<option value="{pin}">{pin}</option>' in page
    assert f'id="new_strip_pixels" min="1" max="{MAX_PIXELS_PER_STRIP}"' in page
    assert f"{MAX_PIXELS_PER_STRIP} pixels per strip" in page

    zones_page = client.get("/zones").get_data(as_text=True)
    assert f'id="new_zone_name" placeholder="screen_area" maxlength="{MAX_ZONE_NAME_LENGTH}"' in zones_page


def test_strip_and_zone_api_create_a_valid_virtual_layout(client, app) -> None:
    strip_response = client.post(
        "/api/strips",
        json={"pin": 6, "pixel_count": 12, "label": "Desk"},
    )
    zone_response = client.post(
        "/api/zones",
        json={"name": "desk", "label": "Desk zone", "start": 2, "end": 9},
    )

    assert strip_response.status_code == 200
    assert strip_response.get_json()["strip"] == {
        "id": 1,
        "pin": 6,
        "pixel_count": 12,
        "label": "Desk",
    }
    assert zone_response.status_code == 200
    assert zone_response.get_json()["zone"] == {
        "name": "desk",
        "label": "Desk zone",
        "start": 2,
        "end": 9,
    }

    bootstrap = client.get("/api/bootstrap").get_json()
    assert bootstrap["pixel_layout"] == [
        {"id": 1, "pin": 6, "pixel_count": 12, "label": "Desk", "start": 0, "end": 11}
    ]
    assert bootstrap["zones"] == [
        {"name": "desk", "label": "Desk zone", "start": 2, "end": 9}
    ]
    assert app.extensions["test.sync_reasons"] == ["startup", "strip-create"]


def test_strip_api_rejects_duplicate_pins(client) -> None:
    client.post("/api/strips", json={"pin": 6, "pixel_count": 8, "label": "First"})

    response = client.post("/api/strips", json={"pin": 6, "pixel_count": 8, "label": "Second"})

    assert response.status_code == 400
    assert response.get_json() == {"message": "Pin 6 is already assigned"}


def test_zone_api_rejects_overlapping_ranges(client) -> None:
    client.post("/api/strips", json={"pin": 6, "pixel_count": 12, "label": "Desk"})
    client.post("/api/zones", json={"name": "left", "start": 0, "end": 5})

    response = client.post("/api/zones", json={"name": "right", "start": 5, "end": 10})

    assert response.status_code == 400
    assert response.get_json() == {"message": "Overlap with zone 'left' (0-5)"}
