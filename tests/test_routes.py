from __future__ import annotations


def test_bootstrap_uses_isolated_default_data_and_never_needs_serial_hardware(client) -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["strips"] == []
    assert payload["zones"] == []
    assert payload["presets"] == []
    assert payload["total_pixels"] == 0
    assert [mode["id"] for mode in payload["enabled_modes"]] == list(range(11))
    assert payload["serial_status"]["connected"] is False


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
