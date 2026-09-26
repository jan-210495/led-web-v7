from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, render_template, request


web = Blueprint("web", __name__)


def storage():
    return current_app.extensions["led.storage"]


def runtime():
    return current_app.extensions["led.runtime"]


def serial_manager():
    return current_app.extensions["led.serial"]


def sync_engine():
    return current_app.extensions["led.sync"]


def bootstrap_payload() -> dict:
    snapshot = storage().snapshot()
    runtime().refresh_from_store()
    return {
        **snapshot,
        "pixel_layout": storage().pixel_layout(),
        "enabled_modes": storage().enabled_modes(),
        "serial_status": serial_manager().status(),
        "serial_history": serial_manager().history()[-25:],
        "runtime_state": runtime().snapshot(),
        "sync_status": sync_engine().sync_status(),
    }


@web.route("/")
def index():
    return render_template("index.html", title="Dashboard", **bootstrap_payload())


@web.route("/zones")
def zones_page():
    return render_template("zones.html", title="Zones", **bootstrap_payload())


@web.route("/config")
def config_page():
    return render_template("config.html", title="Configuration", **bootstrap_payload())


@web.route("/modes")
def modes_page():
    return render_template("modes.html", title="Modes", **bootstrap_payload())


@web.route("/diagnostics")
def diagnostics_page():
    payload = bootstrap_payload()
    payload["now_label"] = datetime.now(ZoneInfo("Asia/Damascus")).strftime("%Y-%m-%d %H:%M:%S")
    return render_template("diagnostics.html", title="Diagnostics", **payload)


@web.route("/api/bootstrap")
def api_bootstrap():
    return jsonify(bootstrap_payload())


@web.route("/api/health")
def api_health():
    response = bootstrap_payload()
    try:
        ping_response = serial_manager().query("PING", duration=0.3)
        response["ping_response"] = ping_response
    except Exception as exc:
        response["ping_response"] = []
        response["serial_status"]["connected"] = False
        response["serial_status"]["last_error"] = str(exc)
    return jsonify(response)


@web.route("/api/diagnostics")
def api_diagnostics():
    payload = bootstrap_payload()
    payload["serial_history"] = serial_manager().history()
    return jsonify(payload)


@web.route("/api/serial/reconnect", methods=["POST"])
def api_reconnect_serial():
    try:
        serial_manager().connect(force=True)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "serial_status": serial_manager().status()})


@web.route("/api/sync/layout", methods=["POST"])
def api_sync_layout():
    sync_engine().sync_layout(reason="manual")
    return jsonify({"status": "ok", "sync_status": sync_engine().sync_status(), "serial_status": serial_manager().status()})


@web.route("/api/strips", methods=["POST"])
def api_create_strip():
    data = request.get_json(force=True)
    strip = storage().add_strip(data.get("pin"), data.get("pixel_count"), data.get("label"))
    sync_engine().sync_layout(reason="strip-create")
    return jsonify({"status": "ok", "strip": strip, "total_pixels": storage().total_pixels()})


@web.route("/api/strips/<int:strip_id>", methods=["PUT"])
def api_update_strip(strip_id: int):
    data = request.get_json(force=True)
    strip = storage().update_strip(strip_id, data.get("pin"), data.get("pixel_count"), data.get("label"))
    sync_engine().sync_layout(reason="strip-update")
    return jsonify({"status": "ok", "strip": strip, "total_pixels": storage().total_pixels()})


@web.route("/api/strips/<int:strip_id>", methods=["DELETE"])
def api_delete_strip(strip_id: int):
    storage().delete_strip(strip_id)
    sync_engine().sync_layout(reason="strip-delete")
    return jsonify({"status": "ok", "total_pixels": storage().total_pixels()})


@web.route("/api/zones", methods=["POST"])
def api_create_zone():
    data = request.get_json(force=True)
    zone = storage().add_zone(data.get("name", ""), data.get("start"), data.get("end"), data.get("label"))
    runtime().refresh_from_store()
    sync_engine().queue_direct(f"CREATE_ZONE:{zone['name']}:{zone['start']}:{zone['end']}")
    return jsonify({"status": "ok", "zone": zone})


@web.route("/api/zones/<name>", methods=["PUT"])
def api_update_zone(name: str):
    data = request.get_json(force=True)
    zone = storage().update_zone(name, data.get("start"), data.get("end"), data.get("label"))
    sync_engine().queue_direct(f"UPDATE_ZONE:{zone['name']}:{zone['start']}:{zone['end']}")
    return jsonify({"status": "ok", "zone": zone})


@web.route("/api/zones/<name>", methods=["DELETE"])
def api_delete_zone(name: str):
    storage().delete_zone(name)
    runtime().drop_zone(name)
    sync_engine().clear_zone_pending(name)
    sync_engine().queue_direct(f"DELETE_ZONE:{name}")
    return jsonify({"status": "ok"})


@web.route("/api/modes", methods=["POST"])
def api_create_mode():
    data = request.get_json(force=True)
    mode = storage().add_mode(data.get("id"), data.get("label", ""), data.get("enabled", True))
    return jsonify({"status": "ok", "mode": mode})


@web.route("/api/modes/<int:mode_id>", methods=["PUT"])
def api_update_mode(mode_id: int):
    data = request.get_json(force=True)
    mode = storage().update_mode(mode_id, data.get("label", ""), data.get("enabled", True))
    return jsonify({"status": "ok", "mode": mode})


@web.route("/api/modes/<int:mode_id>", methods=["DELETE"])
def api_delete_mode(mode_id: int):
    storage().delete_mode(mode_id)
    return jsonify({"status": "ok"})


def _preset_zone_configs(payload: dict) -> list[dict]:
    zone_configs = []
    for item in payload.get("zone_configs", []):
        zone_configs.append(
            {
                "zone": item.get("zone"),
                "enabled": item.get("enabled", True),
                "mode": item.get("mode", 1),
                "brightness": item.get("brightness", 96),
                "delay_ms": item.get("delay_ms", 40),
                "palette": item.get("palette", []),
            }
        )
    return zone_configs


@web.route("/api/presets", methods=["POST"])
def api_create_preset():
    data = request.get_json(force=True)
    preset = storage().add_preset(
        data.get("name", ""),
        data.get("description", ""),
        data.get("global_brightness", 96),
        _preset_zone_configs(data),
    )
    return jsonify({"status": "ok", "preset": preset})


@web.route("/api/presets/<int:preset_id>", methods=["PUT"])
def api_update_preset(preset_id: int):
    data = request.get_json(force=True)
    preset = storage().update_preset(
        preset_id,
        data.get("name", ""),
        data.get("description", ""),
        data.get("global_brightness", 96),
        _preset_zone_configs(data),
    )
    return jsonify({"status": "ok", "preset": preset})


@web.route("/api/presets/<int:preset_id>", methods=["DELETE"])
def api_delete_preset(preset_id: int):
    storage().delete_preset(preset_id)
    return jsonify({"status": "ok"})


@web.route("/api/presets/<int:preset_id>/apply", methods=["POST"])
def api_apply_preset(preset_id: int):
    preset = storage().preset_by_id(preset_id)
    if preset is None:
        raise ValueError("Preset not found")

    sync_engine().clear_global_pending()
    runtime().set_global(brightness=int(preset["global_brightness"]))
    sync_engine().queue_global("brightness", int(preset["global_brightness"]))

    for zone_config in preset["zone_configs"]:
        zone_name = zone_config["zone"]
        if storage().zone_by_name(zone_name) is None:
            continue
        palette = zone_config["palette"]
        primary = list(palette[0])
        zone_state = runtime().ensure_zone(zone_name)
        zone_state["palette"] = palette
        zone_state["color"] = primary
        zone_state["brightness"] = int(zone_config["brightness"])
        zone_state["delay_ms"] = int(zone_config["delay_ms"])
        zone_state["mode"] = int(zone_config["mode"])
        zone_state["enabled"] = bool(zone_config["enabled"])
        if zone_state["mode"] != 0:
            zone_state["last_active_mode"] = zone_state["mode"]

        sync_engine().clear_zone_pending(zone_name)
        if not zone_config["enabled"] or int(zone_config["mode"]) == 0:
            sync_engine().queue_direct(f"ZONE_OFF:{zone_name}")
            continue
        sync_engine().queue_zone(zone_name, "palette", palette)
        sync_engine().queue_zone(zone_name, "color", primary)
        sync_engine().queue_zone(zone_name, "brightness", int(zone_config["brightness"]))
        sync_engine().queue_zone(zone_name, "delay_ms", int(zone_config["delay_ms"]))
        sync_engine().queue_zone(zone_name, "mode", int(zone_config["mode"]))

    return jsonify({"status": "ok", "preset": preset})


@web.route("/api/settings", methods=["PUT"])
def api_update_settings():
    data = request.get_json(force=True)
    updated = storage().update_settings(data.get("serial_port", ""), data.get("baud_rate"), data.get("flush_interval_ms"))
    try:
        serial_manager().connect(force=True)
        sync_engine().sync_layout(reason="settings-save")
    except Exception as exc:
        status = serial_manager().status()
        status["connected"] = False
        status["last_error"] = str(exc)
        return jsonify({"status": "partial", "message": str(exc), "settings": updated, "serial_status": status})
    return jsonify({"status": "ok", "settings": updated, "serial_status": serial_manager().status()})


@web.app_errorhandler(ValueError)
def handle_value_error(exc: ValueError):
    return jsonify({"message": str(exc)}), 400
