# V8 Engineering Notes

This is the continuity record for work performed on the V7 codebase while preparing the future V8 migration. It is intentionally separate from the user-facing roadmap so a later agent can understand *why* a change was made, what was verified, and what remains uncertain.

## Session/branch rules

- All changes in this Arena session must remain on `arena/01a0ddca-led-web-v7`.
- The user plans to migrate the finished work to a future branch named `led-web-v8`; do not create or switch to that branch in this session.
- Work is deliberately incremental: one approved roadmap checkbox at a time.
- At the end of each completed implementation step: verify the focused change, update this file, commit, push `origin/arena/01a0ddca-led-web-v7`, and report the commit ID and branch.
- Do not modify V5 or V6.

## Planning baseline — 2026-09-26

### What was inspected

The repository is a small Flask/Flask-SocketIO application plus Arduino Due FastLED firmware:

- `led_web_v7/storage.py`: JSON-backed strips, zones, mode labels, settings, and presets.
- `led_web_v7/runtime.py`: live in-memory global/zone state.
- `led_web_v7/serial_manager.py`: serial open/read/write/history.
- `led_web_v7/sync_engine.py`: background coalescing queue and layout synchronization.
- `led_web_v7/routes.py` / `sockets.py`: REST and Socket.IO control surface.
- `arduino/V7/V7.ino`: FastLED firmware and line-oriented text protocol.

The checked-in data starts empty for strips, zones, and presets. Modes 0–10 and serial defaults are present.

### Verification performed

```bash
python3 -m py_compile app.py led_web_v7/*.py
```

Result: passed.

No full Flask smoke test, serial-device test, Arduino compile, or formal test suite existed at planning time. Do not interpret the Python compilation result as hardware verification.

### Why the roadmap is ordered this way

1. **Tests first:** Existing behavior needs characterization before changing persistence, layout, or serial behavior. The next agent needs a safe way to detect regressions without Arduino hardware.
2. **Persistence and layout second:** The web application must reject configurations that firmware cannot honor, and virtual pixel indexing must not silently drift when strips change.
3. **Serial reliability before UI polish:** A polished UI is misleading if it cannot distinguish a sent command from a device-accepted command. Firmware replies should be part of the sync result.
4. **Firmware alignment after server contract work:** The firmware protocol should change only after Python-side behavior and fake-serial tests establish an explicit compatibility contract.
5. **Offline UI and operations after correctness:** Removing CDN dependencies and enhancing UX are valuable, but they should build on truthful device state.
6. **Security last:** This is explicitly deferred by the user because the controller is self-hosted and not internet-connected at present. It remains on the roadmap rather than being forgotten.

### Important implementation observations to preserve

- Firmware supports only compiled pins 2–13, max 12 strips, max 300 pixels each, max 20 zones, and mode IDs 0–10. The backend currently does not fully enforce all of those limits.
- Storage sorts strips by pin. Firmware also traverses active pins in compiled pin order. Changing pin assignment can therefore change physical LEDs represented by a zone's virtual indexes.
- Firmware has temporary boot defaults for strips on pins 6, 7, and 9, but a successful server layout sync clears and replaces them. It does not persist layout itself.
- Layout sync writes commands but does not reliably parse all firmware `OK:`/`ERR:` replies before claiming success.
- The background live-update queue catches serial failures and drops the queue snapshot; requested slider/color state can be lost during a device outage.
- The UI calls remote CDNs for Google Fonts, Socket.IO client, and iro color picker. This conflicts with a fully offline/self-contained deployment goal.
- The project lacks authentication, CSRF protections, origin restrictions, and non-default secret management. Per user direction, do not prioritize security work until the final roadmap phase.

## Completed work log

### 2026-09-26 — Roadmap publication

- Added `V8_SHINE_ROADMAP.md`.
- Added this engineering continuity record.
- No application, firmware, dependency, or behavior changes were made in this step.
- Awaiting user validation before beginning roadmap Step 1.1.

### 2026-09-26 — Step 1.1: Focused Python test harness and first regression tests

**Intent**
- Establish a repeatable regression baseline before changing persistence, layout, or serial behavior.
- Ensure application/API tests never need an Arduino, `/dev/ttyACM0`, or the repository's real `data/` directory.

**Changes**
- Added `requirements-dev.txt` with pytest pinned separately from production runtime dependencies.
- Added `pytest.ini` to make `tests/` the explicit test root and to show concise summary output.
- Added an isolated Flask fixture in `tests/conftest.py`.
  - It supplies a temporary `data/` directory through a test-only `AppConfig`.
  - It prevents the daemon serial queue from starting.
  - It replaces layout synchronization with an in-memory recording stub, allowing route behavior to be asserted without serial I/O.
- Added seven regression tests in `tests/test_storage.py` and `tests/test_routes.py`.
  - Storage initialization/default JSON files.
  - Zone creation blocked before any strip exists.
  - Overlapping zone rejection.
  - Hardware-free bootstrap response.
  - Strip/zone API success and virtual layout result.
  - Duplicate strip-pin rejection.
  - Overlapping zone API rejection.
- Added `.gitignore` entries for virtual environments and generated Python/pytest caches.
- Documented the test and compilation commands in `README.md` and updated `AGENTS.md` to replace the former "no formal test suite" guidance.

**Verification**
- Created a disposable test virtual environment outside the repository at `/tmp/led-web-v7-test-venv`.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest` — **7 passed**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest --collect-only -q` — **7 tests collected**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m py_compile app.py led_web_v7/*.py` — **passed**.
- Hardware/manual verification: not applicable for this step; the test fixture intentionally prevents serial access.

**Decisions / trade-offs**
- Kept pytest in a development-only requirements file so homeserver runtime installs do not gain test-only dependencies.
- Tests intentionally characterize the existing API responses and validation behavior; they do not preemptively alter product behavior planned for later roadmap steps.
- The serial worker is stubbed at the app boundary rather than mocking pyserial internals. This makes route/storage tests fast and guarantees no attempt to open a real serial device.

**Commit**
- Recorded in the completion response after the single step commit is created and pushed.

**Follow-up**
- Next approved work must be roadmap Step 1.2: make JSON persistence crash-safe and diagnosable.

### 2026-09-26 — Step 1.2: Crash-safe, diagnosable JSON persistence

**Intent**
- Prevent a partial JSON target file when the process or host fails during a configuration write.
- Replace raw JSON/parser failures with an operator-useful startup error that identifies the affected data file while preserving it for repair or restore.

**Changes**
- Added `StorageDataError`, a specific persistent-data exception.
- Replaced direct JSON overwrites with same-directory temporary-file writes in `Storage._write_json`.
  - JSON is written and flushed to a hidden temporary file.
  - The temporary file is file-synced.
  - `os.replace` atomically swaps it into the target path on the same filesystem.
  - The containing directory is synced on non-Windows systems to persist rename metadata.
  - A failed pre-replacement write/replacement cleans up the staging file and leaves the prior target intact. A post-replacement directory-sync failure explicitly tells the operator that the new target may already be present.
- Improved `_read_json` diagnostics for malformed JSON, invalid UTF-8, file read errors, and an unexpected top-level JSON type.
  - Errors identify the full data-file path and, for JSON parser failures, the line and column.
  - Existing invalid files are never replaced with defaults. The message directs the operator to repair or restore the file before restart.
- Added README recovery guidance.
- Expanded storage coverage from three to six tests, including malformed JSON preservation, wrong-root-type detection, and simulated atomic-replacement failure.

**Verification**
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest` — **10 passed**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m py_compile app.py led_web_v7/*.py` — **passed**.
- Ran a standalone startup-path check against malformed `strips.json`.
  - The process exited with `StorageDataError` naming the exact data file in the temporary test directory plus `line 2, column 1` and recovery guidance.
  - The malformed source contents were verified unchanged.
- Hardware/manual verification: not applicable; this change is confined to server-side JSON persistence.

**Decisions / trade-offs**
- The controller fails fast rather than silently replacing malformed configuration. Silent replacement could lose a user's strip/zone layout and make the actual failure difficult to diagnose.
- This step validates top-level JSON container types (`list` or `dict`) only. Field/schema-level validation and firmware capability limits remain intentionally deferred to Phase 2.
- Temporary files are created beside their target so `os.replace` remains atomic on the same filesystem. The `fsync` calls favor durability over a negligible configuration-save overhead.

**Commit**
- Recorded in the completion response after the single step commit is created and pushed.

**Follow-up**
- Next approved work must be roadmap Step 2.1: define one canonical V7 device-capability contract in Python.

## Template for future completed steps

Copy and fill this structure after each implementation step:

```md
### YYYY-MM-DD — Step X.Y: <title>

**Intent**
- Why this isolated change was needed.

**Changes**
- Files changed and the behavioral effect.

**Verification**
- Exact commands/tests run and result.
- Hardware/manual verification performed, or why it was not possible.

**Decisions / trade-offs**
- Relevant compatibility or design decisions.

**Commit**
- `<commit-id>` on `arena/01a0ddca-led-web-v7`; pushed to origin.

**Follow-up**
- The next unchecked roadmap step and any newly discovered concern.
```
