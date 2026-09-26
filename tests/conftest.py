from __future__ import annotations

from pathlib import Path

import pytest

import led_web_v7
from led_web_v7.config import AppConfig
from led_web_v7.sync_engine import SyncEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Build an isolated Flask app without starting a serial worker or touching hardware."""
    config = AppConfig(
        base_dir=PROJECT_ROOT,
        data_dir=tmp_path / "data",
        templates_dir=PROJECT_ROOT / "templates",
        static_dir=PROJECT_ROOT / "static",
        host="127.0.0.1",
        port=5070,
        secret_key="test-secret",
    )
    sync_reasons: list[str] = []

    monkeypatch.setattr(
        led_web_v7.AppConfig,
        "from_env",
        classmethod(lambda cls: config),
    )
    monkeypatch.setattr(SyncEngine, "start", lambda self: None)

    def record_layout_sync(self: SyncEngine, reason: str = "manual") -> None:
        sync_reasons.append(reason)
        self._set_sync_state(reason, True, None)

    monkeypatch.setattr(SyncEngine, "sync_layout", record_layout_sync)

    app, socketio = led_web_v7.create_app()
    app.config.update(TESTING=True)
    app.extensions["test.socketio"] = socketio
    app.extensions["test.sync_reasons"] = sync_reasons
    return app


@pytest.fixture
def client(app):
    return app.test_client()
