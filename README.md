# LED Controller V7

V7 is a FastLED-focused continuation of the V6 LED controller. It keeps the V6 web app shape:

- Flask web app on the homeserver
- Arduino Due over serial
- multiple physical strips exposed as one virtual strip
- named zones with live controls
- saved modes, diagnostics, and sync visibility

What changes in V7:

- firmware uses FastLED instead of Adafruit NeoPixel
- strip pins are selected from firmware-supported compiled pins
- default app port is `5070`
- V5 and V6 stay untouched

## Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:5070`

## Tests and Verification

Install the development/test dependencies, then run the isolated regression suite:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests use temporary JSON data and stub the serial-sync worker, so they do **not** require an Arduino or `/dev/ttyACM0`.

Syntax-check the Python source before deployment:

```bash
python -m py_compile app.py led_web_v7/*.py
```

### Persistent-data recovery

Configuration in `data/*.json` is written through a same-directory temporary file and atomically replaced, so a process or power failure cannot leave a partially written target JSON file. If an existing data file is malformed, unreadable, or has the wrong top-level JSON type, startup fails safely with the file path and relevant parse location in the service logs. The controller deliberately does **not** overwrite that file: repair it or restore a backup, then restart the service.

### Firmware capability contract

`led_web_v7/device_capabilities.py` is the Python application's canonical mirror of the limits and built-in effects compiled into `arduino/V7/V7.ino`. It supplies capability data to the configuration UI and `/api/bootstrap`; it is not a replacement for firmware limits. When changing supported pins, strip/zone limits, command length, or built-in effects in the sketch, update this module in the same change.

### Firmware-limit validation

The application rejects unsupported data pins, strips longer than 300 pixels, more than 12 active strips, more than 20 zones, uncompiled effect IDs, and zone names/commands that would overflow the firmware serial buffer. HTTP configuration APIs return `400` with the validation message. Existing persisted layouts are also checked at startup so unsupported hardware data cannot be synchronized accidentally; repair the named JSON file before restarting if startup reports an incompatible configuration.

### Stable virtual-pixel mapping

The V7 firmware traverses active strips in ascending compiled data-pin order; the web app uses the same order for its virtual pixel layout. Before a strip is added, resized, moved to another pin, or removed, the app compares every saved zone's physical strip/local-pixel segments before and after the proposed change. Changes that would make a zone address different physical LEDs are rejected. Safe changes that leave every existing zone on the same physical pixels, such as changing an unused trailing strip, remain available.

## Homeserver Deployment

Runtime belongs on the homeserver:

- app path: `/home/abboudfam/led-web-v7`
- service: `led-web-v7`
- port: `5070`

Install/update dependencies after deploying:

```bash
cd /home/abboudfam/led-web-v7
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
sudo cp systemd/led-web-v7.service /etc/systemd/system/led-web-v7.service
sudo systemctl daemon-reload
sudo systemctl enable --now led-web-v7
```

## Layout

- `led_web_v7/` application package
- `templates/` server-rendered HTML
- `static/` client JS and CSS
- `data/` JSON persistence
- `systemd/` service file for homeserver deployment
- `arduino/V7/V7.ino` FastLED firmware
