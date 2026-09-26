from __future__ import annotations

from typing import Any

from flask import current_app
from flask_socketio import SocketIO, emit


def register_socket_handlers(socketio: SocketIO) -> None:
    def runtime():
        return current_app.extensions["led.runtime"]

    def sync_engine():
        return current_app.extensions["led.sync"]

    def bootstrap_payload():
        from .routes import bootstrap_payload as build_payload

        return build_payload()

    @socketio.on("connect")
    def handle_connect():
        emit("init", bootstrap_payload())

    @socketio.on("global_color")
    def handle_global_color(data: dict[str, Any]):
        color = [int(data["r"]), int(data["g"]), int(data["b"])]
        global_state = runtime().global_state()
        palette = list(global_state.get("palette") or [[255, 96, 32], [255, 0, 140], [0, 190, 255]])
        palette[0] = color
        runtime().set_global(color=color, palette=palette)
        sync_engine().queue_global("color", color)

    @socketio.on("global_mode")
    def handle_global_mode(data: dict[str, Any]):
        mode = int(data["mode"])
        global_state = runtime().global_state()
        global_state["mode"] = mode
        global_state["enabled"] = mode != 0
        if mode != 0:
            global_state["last_active_mode"] = mode
        runtime().set_global(**global_state)
        sync_engine().queue_global("mode", mode)
        if mode == 0:
            sync_engine().clear_global_pending()
            sync_engine().queue_global("mode", 0)

    @socketio.on("global_brightness")
    def handle_global_brightness(data: dict[str, Any]):
        brightness = int(data["brightness"])
        runtime().set_global(brightness=brightness)
        sync_engine().queue_global("brightness", brightness)

    @socketio.on("global_on")
    def handle_global_on(_data: dict[str, Any]):
        global_state = runtime().global_state()
        global_state["enabled"] = True
        mode = int(global_state.get("last_active_mode") or 1)
        color = list(global_state["color"])
        brightness = int(global_state["brightness"])
        global_state["mode"] = mode
        runtime().set_global(**global_state)
        sync_engine().queue_global("mode", mode)
        sync_engine().queue_global("color", color)
        sync_engine().queue_global("brightness", brightness)

    @socketio.on("global_off")
    def handle_global_off(_data: dict[str, Any]):
        sync_engine().clear_global_pending()
        global_state = runtime().global_state()
        global_state["enabled"] = False
        global_state["last_active_mode"] = int(global_state.get("mode") or 1)
        runtime().set_global(**global_state)
        sync_engine().queue_direct("ALL_OFF")

    @socketio.on("zone_color")
    def handle_zone_color(data: dict[str, Any]):
        name = data["zone"]
        color = [int(data["r"]), int(data["g"]), int(data["b"])]
        zone_state = runtime().ensure_zone(name)
        palette = list(zone_state.get("palette") or [[255, 96, 32], [255, 0, 140], [0, 190, 255]])
        palette[0] = color
        runtime().set_zone(name, color=color, palette=palette)
        sync_engine().queue_zone(name, "color", color)

    @socketio.on("zone_mode")
    def handle_zone_mode(data: dict[str, Any]):
        name = data["zone"]
        mode = int(data["mode"])
        zone_state = runtime().ensure_zone(name)
        zone_state["mode"] = mode
        zone_state["enabled"] = mode != 0
        if mode != 0:
            zone_state["last_active_mode"] = mode
        runtime().set_zone(name, **zone_state)
        sync_engine().queue_zone(name, "mode", mode)
        if mode == 0:
            sync_engine().clear_zone_pending(name)
            sync_engine().queue_zone(name, "mode", 0)

    @socketio.on("zone_brightness")
    def handle_zone_brightness(data: dict[str, Any]):
        name = data["zone"]
        brightness = int(data["brightness"])
        runtime().set_zone(name, brightness=brightness)
        sync_engine().queue_zone(name, "brightness", brightness)

    @socketio.on("zone_on")
    def handle_zone_on(data: dict[str, Any]):
        name = data["zone"]
        runtime().set_zone(name, enabled=True)
        sync_engine().queue_direct(f"ZONE_ON:{name}")

    @socketio.on("zone_off")
    def handle_zone_off(data: dict[str, Any]):
        name = data["zone"]
        sync_engine().clear_zone_pending(name)
        runtime().set_zone(name, enabled=False)
        sync_engine().queue_direct(f"ZONE_OFF:{name}")

    @socketio.on("identify")
    def handle_identify(data: dict[str, Any]):
        sync_engine().queue_direct(f"ZONE_IDENTIFY:{data['zone']}")
