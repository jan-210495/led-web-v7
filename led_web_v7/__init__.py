from __future__ import annotations

from flask import Flask
from flask_socketio import SocketIO

from .config import AppConfig
from .runtime import RuntimeState
from .serial_manager import SerialManager
from .storage import Storage
from .sync_engine import SyncEngine


def create_app() -> tuple[Flask, SocketIO]:
    config = AppConfig.from_env()

    app = Flask(
        __name__,
        template_folder=str(config.templates_dir),
        static_folder=str(config.static_dir),
    )
    app.config.update(config.flask_config())

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    storage = Storage(config.data_dir)
    runtime = RuntimeState(storage)
    serial_manager = SerialManager(storage, config)
    sync_engine = SyncEngine(storage, runtime, serial_manager)
    sync_engine.start()
    sync_engine.sync_layout(reason="startup")

    app.extensions["led.config"] = config
    app.extensions["led.storage"] = storage
    app.extensions["led.runtime"] = runtime
    app.extensions["led.serial"] = serial_manager
    app.extensions["led.sync"] = sync_engine
    app.extensions["socketio"] = socketio

    from .routes import web
    from .sockets import register_socket_handlers

    app.register_blueprint(web)
    register_socket_handlers(socketio)

    return app, socketio
