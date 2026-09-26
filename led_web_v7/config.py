from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    data_dir: Path
    templates_dir: Path
    static_dir: Path
    host: str
    port: int
    secret_key: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        base_dir = Path(__file__).resolve().parent.parent
        return cls(
            base_dir=base_dir,
            data_dir=base_dir / "data",
            templates_dir=base_dir / "templates",
            static_dir=base_dir / "static",
            host=os.getenv("LED_WEB_HOST", "0.0.0.0"),
            port=int(os.getenv("LED_WEB_PORT", "5070")),
            secret_key=os.getenv("LED_WEB_SECRET", "led-web-v7"),
        )

    def flask_config(self) -> dict[str, object]:
        return {
            "SECRET_KEY": self.secret_key,
            "HOST": self.host,
            "PORT": self.port,
        }
