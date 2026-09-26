# V7 Worklog

## 2026-05-03

Objective: create `led-web-v7`, switch firmware to FastLED, and prepare homeserver deployment on port `5070`.

Completed locally:

- Copied `led-web-v6` to `led-web-v7` without `.venv`, `__pycache__`, or `.pyc` files.
- Renamed Python package from `led_web_v6` to `led_web_v7`.
- Renamed firmware folder and sketch to `arduino/V7/V7.ino`.
- Renamed systemd unit to `systemd/led-web-v7.service`.
- Updated Python entrypoint import to `led_web_v7`.
- Updated default port to `5070`.
- Updated default secret key to `led-web-v7`.
- Updated UI title and brand text to V7.
- Documented the FastLED firmware contract: supported pins are compiled in, runtime config activates only those pins.
- Rewrote `arduino/V7/V7.ino` to use FastLED and emit `READY_V7_FASTLED`.
- Preserved the existing serial protocol used by the V6 backend.
- Added compiled support for pins `2` through `13`, with `MAX_PIXELS_PER_STRIP` set to `300`.

Verification:

- `python3 -m py_compile app.py led_web_v7/*.py` passed.
- Direct Python source compilation passed.
- Arduino compile was not run locally because no Arduino CLI/IDE or PlatformIO command is installed in this environment.
- Flask runtime smoke testing was not run locally because the app is intended to run on the homeserver.

Deployment status:

- SSH target: `abboudfam@192.168.1.31`.
- Password auth was used after key auth failed.
- Files synced to `/home/abboudfam/led-web-v7`.
- Remote venv created at `/home/abboudfam/led-web-v7/.venv`.
- Requirements installed successfully.
- `led-web-v7.service` installed to `/etc/systemd/system/led-web-v7.service`.
- Service enabled and started.
- V7 is reachable at `http://192.168.1.31:5070`.

Runtime notes:

- Homeserver SELinux is enforcing.
- Synced files are labeled `samba_share_t`, so systemd could not execute `.venv/bin/python` directly and failed with `203/EXEC`.
- The service was changed to execute `/usr/bin/python3` and use `PYTHONPATH=/home/abboudfam/led-web-v7/.venv/lib64/python3.12/site-packages`.
- `/api/bootstrap` returns HTTP 200.
- `/api/health` returns HTTP 200 but reports serial offline.
- Smoke-tested `/`, `/zones`, `/modes`, `/config`, `/diagnostics`, `/api/bootstrap`, and `/api/health`; all returned HTTP 200 on the homeserver.
- Serial error: `/dev/ttyACM0` does not exist.
- `dmesg` did not show an Arduino Due / ACM serial device after the homeserver restart.
- No Arduino CLI/IDE/PlatformIO command is available on the homeserver `PATH`, so firmware compile/upload was not performed there.

Deploy commands used:

```bash
rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' /home/jabboud/projects/led-web-v7/ abboudfam@192.168.1.31:/home/abboudfam/led-web-v7/
ssh abboudfam@192.168.1.31 'cd /home/abboudfam/led-web-v7 && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt'
ssh abboudfam@192.168.1.31 'sudo cp /home/abboudfam/led-web-v7/systemd/led-web-v7.service /etc/systemd/system/led-web-v7.service && sudo systemctl daemon-reload && sudo systemctl enable --now led-web-v7'
ssh abboudfam@192.168.1.31 'systemctl status led-web-v7 --no-pager'
```

Planned homeserver path:

- `/home/abboudfam/led-web-v7`

Planned service:

- `led-web-v7`

Planned URL:

- `http://192.168.1.31:5070`

## Saved Progress Snapshot

Saved on 2026-05-03 after deployment.

Current state:

- Local V7 source exists at `/home/jabboud/projects/led-web-v7`.
- Homeserver V7 source exists at `/home/abboudfam/led-web-v7`.
- `led-web-v7.service` is installed, enabled, and active.
- The service runs `/usr/bin/python3 /home/abboudfam/led-web-v7/app.py`.
- The service environment uses `LED_WEB_PORT=5070`.
- The service uses `PYTHONPATH=/home/abboudfam/led-web-v7/.venv/lib64/python3.12/site-packages` because SELinux blocked direct execution of `.venv/bin/python`.
- Web UI is reachable at `http://192.168.1.31:5070`.
- All smoke-test routes returned HTTP 200: `/`, `/zones`, `/modes`, `/config`, `/diagnostics`, `/api/bootstrap`, `/api/health`.
- Serial remains offline because `/dev/ttyACM0` is absent after homeserver restart.
- FastLED firmware is written but not compiled/uploaded from the homeserver because Arduino tooling is not installed there.

Recommended next steps:

- Reconnect or power-cycle the Arduino Due and confirm `/dev/ttyACM0` or another serial device appears.
- Upload `arduino/V7/V7.ino` using an Arduino environment with FastLED installed.
- Recheck `http://192.168.1.31:5070/api/health`.
- Add strips/zones from the V7 UI and verify serial history in Diagnostics.
