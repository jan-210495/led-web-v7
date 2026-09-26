# LED Controller V8 — Improvement Roadmap

**Status:** planning approved? **No — awaiting user validation.**

**Working branch:** `arena/01a0ddca-led-web-v7`

**Future migration target:** a later `led-web-v8` branch, created outside this Arena session.

## Operating agreement

- This document is the source of truth for the improvement sequence.
- Only **one unchecked implementation step** will be performed at a time after the user approves it.
- Each implementation step ends with focused tests/smoke checks, an update to `V8_ENGINEERING_NOTES.md`, one commit, and a push to `origin/arena/01a0ddca-led-web-v7`.
- A checkbox is changed to `[x]` only after the associated code, verification, notes, commit, and push are complete.
- Small corrective fixes discovered while executing a step may be included only when they are required for that step's acceptance criteria. Otherwise they become a new unchecked step.
- V8 remains LAN/self-hosted for now. Security hardening is deliberately deferred to the final phase at the user's request.

## North-star outcome

Make this a dependable, understandable LED controller that:

1. rejects impossible layouts before they reach the Arduino;
2. preserves predictable physical-to-virtual pixel mapping;
3. makes serial/device failures visible and recoverable;
4. remains usable when the device reconnects or the server restarts;
5. has automated regression coverage for the protocol and configuration model; and
6. can be handed to a future agent or maintainer with clear operational documentation.

## Current baseline observed during planning

- Python package syntax compiles with `python3 -m py_compile app.py led_web_v7/*.py`.
- There is no automated test suite yet.
- Storage currently contains no strips, zones, or presets; built-in mode definitions and serial settings exist.
- The web backend and FastLED firmware share a text serial protocol, but some hardware constraints are enforced only by firmware.
- The live-command queue drops updates on a serial failure, and layout synchronization does not validate firmware acknowledgements.
- Browser assets currently include CDN dependencies (fonts, Socket.IO client, and the iro color picker).

---

## Phase 0 — Planning and working record

- [x] **0.1 Publish this roadmap and engineering notes.**
  - Purpose: establish the one-step-at-a-time workflow and preserve the reasoning for future agents.
  - Done when: this roadmap and `V8_ENGINEERING_NOTES.md` are committed and pushed.

## Phase 1 — Establish a safe engineering baseline

- [x] **1.1 Add a focused Python test harness and first regression tests.**
  - Scope: introduce pytest-based tests and fixtures without changing current product behavior; cover app creation, default bootstrap data, storage validation, and selected API success/error paths.
  - Done when: tests run in one documented command, do not need real serial hardware, and pass alongside the existing Python compilation check.
  - Completed 2026-09-26: added a seven-test isolated pytest suite, a development requirements file, documented verification commands, and cache/virtualenv ignore rules.

- [x] **1.2 Make JSON persistence crash-safe and diagnosable.**
  - Scope: replace direct JSON overwrites with atomic writes; add clear handling for invalid/corrupt JSON that reports the file and failure safely rather than producing an obscure startup error.
  - Done when: all application-owned data writes are atomic, behavior is regression-tested, and invalid persisted data yields a useful operator-facing error.
  - Completed 2026-09-26: all storage writes now fsync a same-directory temporary file before atomic replacement; malformed, unreadable, and wrong-root-type JSON now raises a file-specific recovery error without changing the source file.

## Phase 2 — Make the layout model truthful before it reaches hardware

- [x] **2.1 Define one canonical V7 device-capability contract in Python.**
  - Scope: centralize supported pins, maximum strip count, pixels per strip, zone count, command length, and built-in effect IDs in a dedicated module derived from the V7 firmware contract.
  - Done when: validation and UI/bootstrap capability data use this one source instead of scattered literals; existing hardware behavior remains unchanged.
  - Completed 2026-09-26: added `device_capabilities.py` as the firmware mirror; defaults, configuration UI, and bootstrap payload now use it, while actual rejection/enforcement remains isolated for Step 2.2.

- [ ] **2.2 Enforce firmware layout limits in the storage/API layer.**
  - Scope: use the capability contract to reject unsupported pins, strip lengths over 300, more than 12 strips, more than 20 zones, invalid mode IDs, and unsafe command payloads before writing JSON or queueing commands.
  - Done when: impossible hardware configurations receive clear HTTP 400 messages and are covered by tests.

- [ ] **2.3 Preserve virtual-pixel mapping during strip changes.**
  - Scope: explicitly define stable physical strip ordering and prevent or safely handle edits/deletions that would silently make existing zone indexes point at different LEDs.
  - Done when: strip changes either preserve the affected zone mapping or are blocked with a precise explanation; the chosen behavior is tested and documented.

- [ ] **2.4 Add a server-side layout preview/validation endpoint.**
  - Scope: expose a read-only preflight representation of strips, virtual ranges, zones, and detected layout warnings for use by the UI and diagnostics.
  - Done when: the UI can explain the exact virtual layout before hardware sync, with automated coverage for cross-strip zones and invalid changes.

## Phase 3 — Make serial synchronization reliable and observable

- [ ] **3.1 Give serial commands structured results and parse device replies.**
  - Scope: distinguish write failure, timeout, `OK:*`, and `ERR:*` responses; retain useful command/response timing data without changing the command vocabulary.
  - Done when: a command can report whether firmware accepted it, and tests use a fake serial device rather than physical hardware.

- [ ] **3.2 Make layout sync transactional from the operator's perspective.**
  - Scope: verify `CLEAR_STRIPS`, every `ADD_STRIP`, zone deletion, and zone creation response; report the failing command and preserve the full result in diagnostics.
  - Done when: a failed firmware acknowledgement makes layout sync fail visibly instead of being reported as successful.

- [ ] **3.3 Preserve/reconcile live updates across serial outages.**
  - Scope: stop silently discarding queued state updates on disconnect; retain a latest desired state and reconcile it deliberately after a successful reconnect or manual re-sync.
  - Done when: recovery behavior is deterministic, visible in diagnostics, and covered by fake-serial tests.

- [ ] **3.4 Improve hardware health and diagnostics.**
  - Scope: add a concise health model for connection, last successful ping, last successful sync, pending/recovery state, firmware readiness, and the most recent device error.
  - Done when: the dashboard and Diagnostics page communicate what action an operator should take instead of only showing raw serial history.

## Phase 4 — Align firmware and application behavior

- [ ] **4.1 Tighten the V7 firmware protocol contract.**
  - Scope: make responses consistently identifiable, reject invalid effect IDs explicitly, and add an optional capabilities/version response that the server can query.
  - Done when: the app can identify compatible V7 FastLED firmware and explain a firmware mismatch; command behavior is documented in the protocol reference.

- [ ] **4.2 Make device state recovery explicit after Arduino reset.**
  - Scope: detect the firmware ready banner/version where practical and perform a deliberate full layout plus desired-state reconciliation after a reset/reconnect.
  - Done when: an Arduino reset has documented, tested recovery behavior and does not depend on the operator guessing when to re-sync.

- [ ] **4.3 Validate firmware changes with Arduino tooling or a documented hardware verification matrix.**
  - Scope: add repeatable compile instructions and, when tooling/hardware is available, verify the sketch plus core protocol/effect scenarios.
  - Done when: firmware verification status is unambiguous and reproducible; no unverified firmware change is presented as deployed.

## Phase 5 — Improve product polish and offline self-hosting

- [ ] **5.1 Make the live-control UI reflect command and recovery state.**
  - Scope: show pending/sent/failed feedback for meaningful actions, avoid stale controls after applying presets, and surface hardware errors near the action that caused them.
  - Done when: an operator can tell whether a requested lighting change reached the controller without opening Diagnostics.

- [ ] **5.2 Clarify effect modes versus saved presets.**
  - Scope: remove the current ambiguity between firmware animation modes and reusable lighting presets; prevent UI-only custom effect IDs unless matching firmware support exists.
  - Done when: labels, pages, and validation accurately describe what can be configured versus what must be implemented in firmware.

- [ ] **5.3 Remove runtime CDN dependence for the self-hosted UI.**
  - Scope: vendor or replace external font, Socket.IO-client, and color-picker dependencies using a maintainable local asset strategy compatible with the selected package approach.
  - Done when: core UI operation does not require browser access to third-party CDNs and license/source notes are recorded.

- [ ] **5.4 Improve accessibility and responsive usability.**
  - Scope: keyboard-accessible controls, visible focus states, form labels/errors, color-independent status indicators, and practical layouts for phone/tablet control.
  - Done when: a keyboard-only smoke check and responsive browser check pass, with no regression in the desktop workflow.

## Phase 6 — Operational maturity and handoff quality

- [ ] **6.1 Add a simulated-device development mode.**
  - Scope: provide an explicit opt-in fake Arduino/serial implementation for local development, demos, API tests, and UI work without `/dev/ttyACM0`.
  - Done when: the full web app can be exercised locally with realistic protocol responses and no physical LED hardware.

- [ ] **6.2 Add repeatable quality commands and CI-ready configuration.**
  - Scope: document one command for tests and static checks; add lightweight formatting/linting only where it is useful and does not create churn.
  - Done when: a clean checkout has a documented, repeatable verification command suitable for later CI.

- [ ] **6.3 Refresh deployment, migration, and recovery documentation.**
  - Scope: document installation, systemd configuration, serial permissions, FastLED installation/upload, data backup/restore, reset recovery, and V7-to-V8 migration expectations.
  - Done when: a new maintainer can deploy and recover the controller without relying on chat history.

- [ ] **6.4 Prepare the V8 migration handoff.**
  - Scope: record the final compatibility state, migration checklist, release notes, and any data/firmware steps required before copying this work to the future `led-web-v8` branch.
  - Done when: the future branch migration is a mechanical, reviewed procedure rather than an undocumented copy.

## Phase 7 — Security hardening (deferred by request)

- [ ] **7.1 Define the trusted-network threat model and exposure boundary.**
  - Scope: document which hosts may access the controller and whether a reverse proxy or VPN is expected.

- [ ] **7.2 Add appropriate access controls and transport protections.**
  - Scope: choose authentication, authorization, origin restrictions, secret management, CSRF policy, and HTTPS/reverse-proxy configuration based on the agreed threat model.

- [ ] **7.3 Validate the hardened deployment.**
  - Scope: verify that protected HTTP and Socket.IO paths work for authorized users and are blocked for unauthorized origins/clients.

---

## Explicitly out of scope unless separately approved

- Changing the session branch away from `arena/01a0ddca-led-web-v7`.
- Modifying V5 or V6 projects.
- Replacing the Arduino Due or changing LED hardware/protocol type.
- Large framework rewrites (for example, replacing Flask) without a separate decision.
- Performing the deferred security phase before the user asks for it.

## Next action

**Await roadmap validation.** Once approved, begin only with **Step 1.1** and stop after that focused step has been tested, documented, committed, pushed, and reported.
