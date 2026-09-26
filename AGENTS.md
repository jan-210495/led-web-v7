# Repository Guidelines

## Project Structure & Module Organization

This repository is the V7 LED controller. The Flask entrypoint is `app.py`, which creates the app through `led_web_v7/`. Backend modules are split by responsibility: `storage.py` for JSON persistence, `runtime.py` for live state, `serial_manager.py` for Arduino serial I/O, `sync_engine.py` for queued commands and layout sync, `routes.py` for HTTP APIs/pages, and `sockets.py` for Socket.IO handlers.

Templates live in `templates/`, browser assets in `static/`, runtime JSON data in `data/`, systemd deployment files in `systemd/`, and FastLED Arduino firmware in `arduino/V7/V7.ino`.

## Build, Test, and Development Commands

Create a local environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Run locally:

```bash
python app.py
```

The app listens on `0.0.0.0:5070` by default. Override with `LED_WEB_PORT=5071 python app.py`.

Syntax-check Python before deployment:

```bash
python3 -m py_compile app.py led_web_v7/*.py
```

## Firmware Contract

V7 uses FastLED. Unlike the V6 Adafruit NeoPixel firmware, arbitrary runtime data pins are not the goal. Supported data pins are compiled into `arduino/V7/V7.ino`; the web app can activate those supported pins and set pixel counts with `CLEAR_STRIPS` and `ADD_STRIP:<pin>:<count>`.

If protocol commands change, update both `led_web_v7/sync_engine.py` and `arduino/V7/V7.ino`.

## Testing Guidelines

There is no formal test suite yet. At minimum, run `py_compile`, then smoke-test these URLs on V7: `/`, `/zones`, `/modes`, `/config`, `/diagnostics`, and `/api/bootstrap`.

For hardware-affecting changes, verify serial state through `/api/health` and the Diagnostics page. Confirm the Arduino Due is running `arduino/V7/V7.ino`, not V5 or V6 firmware.

## Security & Deployment Notes

This laptop is for management only. Do not run persistent services here. Deploy runtime services to `homeserver`; V7 should run on port `5070`. Do not modify `led-web-v5` or `led-web-v6` unless explicitly requested.
