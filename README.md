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
