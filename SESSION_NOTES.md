# V7 Session Notes

This directory was created from the V6 rewrite as a separate V7 project.

## Goals

- keep V5 and V6 untouched
- run V7 on homeserver port `5070`
- switch Arduino firmware from Adafruit NeoPixel to FastLED
- preserve the V6 backend, pages, APIs, Socket.IO events, JSON storage, and diagnostics
- document the firmware contract change clearly

## What is implemented

- `led_web_v7/` package with modular app creation
- V7 branding in templates and docs
- default app port `5070`
- `systemd/led-web-v7.service`
- FastLED firmware at `arduino/V7/V7.ino`
- Markdown handoff/worklog at `V7_WORKLOG.md`

## Important V7 Constraint

FastLED strip pins are firmware-supported compiled pins. Runtime config can activate those pins and set pixel counts, but arbitrary pins outside the compiled set are rejected by the firmware.
