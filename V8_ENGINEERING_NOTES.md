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

### 2026-09-26 — Step 2.1: Canonical V7 device-capability contract

**Intent**
- Give the Python application one explicit, tested mirror of the limits and built-in effects compiled into the V7 FastLED firmware.
- Remove UI/bootstrap dependence on persisted or duplicated capability literals without changing accepted hardware configurations yet.

**Changes**
- Added `led_web_v7/device_capabilities.py`.
  - Mirrors V7 firmware family, supported data pins 2–13, maximum active strips (12), pixels per strip (300), zones (20), command length (180), and effects 0–10.
  - Provides immutable effect definitions, the built-in ID set for future validation, fresh default mode records, and a JSON-safe bootstrap payload.
  - Documents that `arduino/V7/V7.ino` remains the hardware authority and must be kept in sync.
- Replaced the duplicated Python default-mode literal list with mode records derived from the capability module.
- Removed the derived `pin_options` field from persistent serial settings and migrated legacy saved settings by removing that field during normal load/persist. Pins are hardware capabilities, not user-editable serial configuration.
- Added `device_capabilities` to every bootstrap response and the browser's `window.APP_BOOTSTRAP` payload.
- Changed the Configuration page's new-strip pin menu and FastLED hardware note to use bootstrap capability data.
- Added a matching firmware comment plus README/agent guidance so future firmware changes update the Python mirror in the same change.

**Verification**
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest` — **14 passed**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m py_compile app.py led_web_v7/*.py` — **passed**.
- Ran the capability-only tests — **2 passed**.
- Printed and inspected the JSON-safe capability payload; it contains all V7 limits and effects 0–10.
- Searched the Python application/template source after the refactor: capability literals remain only in `device_capabilities.py`; the legacy `pin_options` reference is retained solely for one-time compatibility cleanup. Persisted `data/modes.json` remains user-editable mode state, not a source of default capability definitions.
- Arduino compile/hardware verification: not applicable for this metadata/UI change; no firmware behavior was changed.

**Decisions / trade-offs**
- The capability module is a deliberate Python mirror, not generated code. The Arduino sketch remains authoritative because it is what physically controls the hardware. The code comments and documentation make synchronization an explicit maintainer responsibility.
- Step 2.1 exposes and centralizes limits but intentionally does **not** reject existing out-of-range strips, modes, or commands. That behavioral enforcement is the narrowly scoped next step (2.2), avoiding a combined refactor/behavior-change commit.
- Existing settings files with `pin_options` are migrated safely on first load. The public bootstrap now exposes the richer `device_capabilities` object; the obsolete `settings.pin_options` field is removed.

**Commit**
- Recorded in the completion response after the single step commit is created and pushed.

**Follow-up**
- Next approved work must be roadmap Step 2.2: enforce firmware layout limits in the storage/API layer.

### 2026-09-26 — Step 2.2: Enforce V7 firmware layout and command limits

**Intent**
- Reject configurations and live-control values that the currently compiled V7 firmware cannot honor, before they are persisted or sent to serial.
- Make invalid persisted hardware configuration fail safely at startup instead of allowing a later partial/failed hardware sync.

**Changes**
- Extended `device_capabilities.py` with reusable validators for:
  - supported pins; pixel count; active strip count; zone count; built-in effect IDs;
  - RGB/brightness values; palette shape; animation delay; and all queueable live-control values;
  - serial command byte length, embedded line breaks, and the maximum safe zone-name length.
- Documented the firmware detail that its 180-byte command buffer includes the C-string terminator. Commands therefore allow at most 179 UTF-8 payload bytes before the newline. The longest zone command is a palette update, which permits a 130-byte ASCII zone name; this is calculated from the shared command contract, not hard-coded in storage or UI.
- Enforced V7 limits in `Storage` before writes:
  - data pin must be 2–13;
  - strip length must be 1–300;
  - active strip count cannot exceed 12;
  - zone count cannot exceed 20;
  - zone names must be serial-safe;
  - persisted/custom/preset effect IDs must be compiled IDs 0–10.
- Validated persisted strips, zones, modes, and presets at startup. Incompatible saved data raises the existing file-specific `StorageDataError` and is left untouched for repair.
- Added command safety at both queue and serial boundaries:
  - direct commands are checked before entering `SyncEngine`'s queue;
  - queued global/zone state is range-checked before command construction;
  - `SerialManager.send` and `query` apply a final command-payload check before opening/writing a port.
- Validated Socket.IO live effect/color/brightness changes before mutating runtime state or queueing commands. Zone actions now require an existing stored zone, preventing unknown zone names from becoming raw serial commands.
- Added browser constraints derived from capability bootstrap data: strip pixel inputs have a maximum of 300 and new zone names have the calculated maximum length.
- Corrected a durability detail discovered during the real checked-in data validation: atomic replacement now preserves an existing data file's permission bits instead of replacing them with the temporary file's default mode.
- Added README documentation for enforced firmware limits.

**Verification**
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest` — **23 passed**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m py_compile app.py led_web_v7/*.py` — **passed**.
- Verified a maximum-length zone name produces a 179-byte `ZONE_PALETTE` command, exactly matching the usable firmware payload capacity.
- Loaded the repository's real `data/` directory through `Storage` after the change: 0 strips, 0 zones, 11 modes, 0 presets, 0 total pixels; no content or permission-mode diff was produced.
- Arduino compile/hardware verification: not applicable for this server-side validation step; no executable firmware behavior was changed.

**Decisions / trade-offs**
- Unsupported effect IDs now fail rather than being saved as arbitrary labels or being sent to firmware's solid-color fallback. The old Configuration-page custom-mode control may now show an explicit 400 validation error for noncompiled IDs; a later UX-only roadmap step (5.2) will clarify/remove that obsolete affordance.
- Existing incompatible persisted layout/effect data fails fast with a recovery message. Silently clipping or deleting stored hardware configuration could physically remap or unexpectedly turn off LEDs.
- Command validation is duplicated at queue and serial boundaries intentionally: normal app paths fail before queuing, while the serial boundary remains a final guard for future/internal callers and layout sync.
- Existing file permissions are preserved during atomic replacement. New files keep the secure temporary-file default; no permission broadening was introduced.

**Commit**
- Recorded in the completion response after the single step commit is created and pushed.

**Follow-up**
- Next approved work must be roadmap Step 2.3: preserve virtual-pixel mapping during strip changes.

### 2026-09-26 — Step 2.3: Preserve virtual-pixel mapping during strip changes

**Intent**
- Prevent a strip add, resize, pin move, or deletion from silently causing a saved zone's numeric range to address different physical LEDs.
- Establish one explicit ordering rule shared by the application and compiled Arduino firmware.

**Changes**
- Defined virtual strip order as ascending Arduino data-pin order, matching the firmware's `SUPPORTED_PINS` traversal in `setVirtualPixel`.
- Added storage helpers that:
  - build virtual layouts from this firmware order;
  - translate each zone into stable `(strip ID, local start, local end)` physical segments; and
  - compare current and proposed strip layouts before a mutation is persisted.
- Strip additions, edits, and deletions now use a proposed-layout validation flow before mutating in-memory data or JSON.
  - If a zone would address a different strip/local-pixel segment, the operation is rejected with the exact affected zone names.
  - If a layout shrink would leave a zone outside the available virtual range, the operation is rejected directly.
  - Changes that leave every saved zone physically identical are allowed, including safe modifications/deletion of unused trailing strips.
- Normalized loaded strips to ascending pin order so persisted configuration, dashboard layout, configuration list, serial sync ordering, and firmware traversal agree.
- Added configuration-page and README explanations of the ordering and blocking behavior.

**Verification**
- Ran `/tmp/led-web-v7-test-venv/bin/python -m pytest` — **29 passed**.
- Ran `/tmp/led-web-v7-test-venv/bin/python -m py_compile app.py led_web_v7/*.py` — **passed**.
- Added coverage for:
  - firmware pin ordering even when strips are added out of order;
  - rejection when inserting a preceding strip would remap a zone;
  - rejection when resizing a preceding strip would remap a zone;
  - rejection when changing pin order would remap a zone;
  - acceptance of safe trailing-strip resize/deletion; and
  - the HTTP 400 response for a blocked strip change.
- Arduino compile/hardware verification: not applicable; no firmware code or wire protocol changed.

**Decisions / trade-offs**
- A separate arbitrary strip-order field was deliberately not introduced. The current Arduino firmware always maps virtual pixels by compiled pin order, so persisting a different web-only order would be misleading and unsafe without a firmware protocol redesign.
- The guard compares physical segment identity rather than applying a simplistic rule such as "never edit a strip with zones." This permits safe maintenance when all existing zones remain on the same LEDs while preventing accidental remapping.
- Blocked operations require the operator to update or remove the named zones first. Automatic zone-offset rewriting was rejected because a layout change can be ambiguous across physical strips and could light the wrong hardware.

**Commit**
- Recorded in the completion response after the single step commit is created and pushed.

**Follow-up**
- Next approved work must be roadmap Step 2.4: add a server-side layout preview/validation endpoint.

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
