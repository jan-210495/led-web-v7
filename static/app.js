const socket = io();
let boot = window.APP_BOOTSTRAP || {};

function hexToRgb(hex) {
    const cleaned = (hex || "#000000").replace("#", "");
    return [
        parseInt(cleaned.slice(0, 2), 16),
        parseInt(cleaned.slice(2, 4), 16),
        parseInt(cleaned.slice(4, 6), 16),
    ];
}

function collectPresetZoneConfigs(prefix) {
    return (boot.zones || []).map((zone) => ({
        zone: zone.name,
        enabled: document.getElementById(`${prefix}_zone_${zone.name}_enabled`).checked,
        mode: parseInt(document.getElementById(`${prefix}_zone_${zone.name}_mode`).value, 10),
        brightness: parseInt(document.getElementById(`${prefix}_zone_${zone.name}_brightness`).value, 10),
        delay_ms: parseInt(document.getElementById(`${prefix}_zone_${zone.name}_delay_ms`).value, 10),
        palette: [
            hexToRgb(document.getElementById(`${prefix}_zone_${zone.name}_color_1`).value),
            hexToRgb(document.getElementById(`${prefix}_zone_${zone.name}_color_2`).value),
            hexToRgb(document.getElementById(`${prefix}_zone_${zone.name}_color_3`).value),
        ],
    }));
}

function throttle(fn, wait = 40) {
    let last = 0;
    let timeout = null;
    let pendingArgs = null;

    return (...args) => {
        const now = Date.now();
        pendingArgs = args;
        const run = () => {
            last = Date.now();
            timeout = null;
            fn(...pendingArgs);
        };

        if (now - last >= wait) {
            run();
            return;
        }

        if (!timeout) {
            timeout = setTimeout(run, wait - (now - last));
        }
    };
}

function setStatus(id, message, isError = false) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("error", isError);
}

async function api(url, method = "GET", body = null) {
    const options = { method, headers: {} };
    if (body) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.message || "Request failed");
    }
    return data;
}

function refreshSoon(messageId, message) {
    if (messageId) setStatus(messageId, message);
    setTimeout(() => window.location.reload(), 350);
}

function makePicker(id, initialColor, handler) {
    const el = document.getElementById(id);
    if (!el) return null;

    const picker = new iro.ColorPicker(`#${id}`, {
        width: 190,
        color: initialColor,
        layout: [
            { component: iro.ui.Wheel },
            { component: iro.ui.Slider, options: { sliderType: "hue" } },
        ],
    });

    const throttled = throttle((color) => {
        handler(color.rgb);
    }, 40);

    picker.on("color:change", (color) => throttled(color));
    picker.on("input:end", (color) => handler(color.rgb));
    return picker;
}

function emitGlobalOn() {
    socket.emit("global_on", {});
}

function emitGlobalOff() {
    socket.emit("global_off", {});
}

function emitZoneOn(name) {
    socket.emit("zone_on", { zone: name });
}

function emitZoneOff(name) {
    socket.emit("zone_off", { zone: name });
}

function identifyZone(name) {
    socket.emit("identify", { zone: name });
}

function renderPixelBoard() {
    const board = document.getElementById("pixel_board");
    if (!board) return;

    board.innerHTML = "";
    const totalPixels = boot.total_pixels || 0;
    const zones = boot.zones || [];

    for (let index = 0; index < totalPixels; index += 1) {
        const cell = document.createElement("div");
        cell.className = "pixel-cell";
        cell.title = `Pixel ${index}`;
        const zone = zones.find((item) => index >= item.start && index <= item.end);
        if (zone) {
            cell.classList.add("zone-pixel");
            cell.dataset.zone = zone.name;
        }
        const label = document.createElement("span");
        label.textContent = index;
        cell.appendChild(label);
        board.appendChild(cell);
    }
}

function initDashboard() {
    const globalState = (boot.runtime_state && boot.runtime_state.global) || {
        color: [255, 96, 32],
        brightness: 96,
        mode: 1,
    };

    makePicker(
        "picker_global",
        { r: globalState.color[0], g: globalState.color[1], b: globalState.color[2] },
        (rgb) => socket.emit("global_color", { r: rgb.r, g: rgb.g, b: rgb.b })
    );

    const globalMode = document.getElementById("global_mode");
    if (globalMode) {
        globalMode.addEventListener("change", () => {
            socket.emit("global_mode", { mode: parseInt(globalMode.value, 10) });
        });
    }

    const globalBrightness = document.getElementById("global_brightness");
    const globalBrightnessValue = document.getElementById("global_brightness_value");
    if (globalBrightness) {
        const sendBrightness = throttle(() => {
            const value = parseInt(globalBrightness.value, 10);
            if (globalBrightnessValue) globalBrightnessValue.textContent = value;
            socket.emit("global_brightness", { brightness: value });
        }, 40);
        globalBrightness.addEventListener("input", sendBrightness);
        globalBrightness.addEventListener("change", sendBrightness);
    }

    renderPixelBoard();
}

function initZoneControls() {
    (boot.zones || []).forEach((zone) => {
        const state = ((boot.runtime_state || {}).zones || {})[zone.name] || {
            color: [255, 96, 32],
            brightness: 96,
            mode: 1,
        };

        makePicker(
            `picker_${zone.name}`,
            { r: state.color[0], g: state.color[1], b: state.color[2] },
            (rgb) => socket.emit("zone_color", { zone: zone.name, r: rgb.r, g: rgb.g, b: rgb.b })
        );

        const modeInput = document.getElementById(`mode_${zone.name}`);
        if (modeInput) {
            modeInput.addEventListener("change", () => {
                socket.emit("zone_mode", { zone: zone.name, mode: parseInt(modeInput.value, 10) });
            });
        }

        const brightnessInput = document.getElementById(`brightness_${zone.name}`);
        const valueEl = document.getElementById(`brightness_value_${zone.name}`);
        if (brightnessInput) {
            const sendBrightness = throttle(() => {
                const value = parseInt(brightnessInput.value, 10);
                if (valueEl) valueEl.textContent = value;
                socket.emit("zone_brightness", { zone: zone.name, brightness: value });
            }, 40);
            brightnessInput.addEventListener("input", sendBrightness);
            brightnessInput.addEventListener("change", sendBrightness);
        }
    });
}

function applySelectedPreset() {
    const preset = document.getElementById("dashboard_preset_id");
    if (!preset) return;
    applyPreset(parseInt(preset.value, 10));
}

async function createStrip() {
    try {
        await api("/api/strips", "POST", {
            label: document.getElementById("new_strip_label").value.trim(),
            pin: parseInt(document.getElementById("new_strip_pin").value, 10),
            pixel_count: parseInt(document.getElementById("new_strip_pixels").value, 10),
        });
        refreshSoon("strip_status", "Strip added.");
    } catch (err) {
        setStatus("strip_status", err.message, true);
    }
}

async function updateStrip(stripId) {
    try {
        await api(`/api/strips/${stripId}`, "PUT", {
            label: document.getElementById(`strip_label_${stripId}`).value.trim(),
            pin: parseInt(document.getElementById(`strip_pin_${stripId}`).value, 10),
            pixel_count: parseInt(document.getElementById(`strip_pixels_${stripId}`).value, 10),
        });
        refreshSoon("strip_status", "Strip updated.");
    } catch (err) {
        setStatus("strip_status", err.message, true);
    }
}

async function deleteStrip(stripId) {
    try {
        await api(`/api/strips/${stripId}`, "DELETE");
        refreshSoon("strip_status", "Strip deleted.");
    } catch (err) {
        setStatus("strip_status", err.message, true);
    }
}

async function createZone() {
    try {
        await api("/api/zones", "POST", {
            name: document.getElementById("new_zone_name").value.trim(),
            label: document.getElementById("new_zone_label").value.trim(),
            start: parseInt(document.getElementById("new_zone_start").value, 10),
            end: parseInt(document.getElementById("new_zone_end").value, 10),
        });
        refreshSoon("zone_status", "Zone created.");
    } catch (err) {
        setStatus("zone_status", err.message, true);
    }
}

async function updateZone(name) {
    try {
        await api(`/api/zones/${name}`, "PUT", {
            label: document.getElementById(`zone_label_${name}`).value.trim(),
            start: parseInt(document.getElementById(`zone_start_${name}`).value, 10),
            end: parseInt(document.getElementById(`zone_end_${name}`).value, 10),
        });
        refreshSoon("zone_status", "Zone updated.");
    } catch (err) {
        setStatus("zone_status", err.message, true);
    }
}

async function deleteZone(name) {
    try {
        await api(`/api/zones/${name}`, "DELETE");
        refreshSoon("zone_status", "Zone deleted.");
    } catch (err) {
        setStatus("zone_status", err.message, true);
    }
}

async function createMode() {
    try {
        await api("/api/modes", "POST", {
            id: parseInt(document.getElementById("new_mode_id").value, 10),
            label: document.getElementById("new_mode_label").value.trim(),
            enabled: true,
        });
        refreshSoon("mode_status", "Mode added.");
    } catch (err) {
        setStatus("mode_status", err.message, true);
    }
}

async function updateMode(modeId) {
    try {
        await api(`/api/modes/${modeId}`, "PUT", {
            label: document.getElementById(`mode_label_${modeId}`).value.trim(),
            enabled: document.getElementById(`mode_enabled_${modeId}`).checked,
        });
        refreshSoon("mode_status", "Mode updated.");
    } catch (err) {
        setStatus("mode_status", err.message, true);
    }
}

async function deleteMode(modeId) {
    try {
        await api(`/api/modes/${modeId}`, "DELETE");
        refreshSoon("mode_status", "Mode deleted.");
    } catch (err) {
        setStatus("mode_status", err.message, true);
    }
}

async function createPreset() {
    try {
        await api("/api/presets", "POST", {
            name: document.getElementById("new_preset_name").value.trim(),
            description: document.getElementById("new_preset_description").value.trim(),
            global_brightness: parseInt(document.getElementById("new_preset_global_brightness").value, 10),
            zone_configs: collectPresetZoneConfigs("new_preset"),
        });
        refreshSoon("preset_status", "Saved mode created.");
    } catch (err) {
        setStatus("preset_status", err.message, true);
    }
}

async function updatePreset(presetId) {
    try {
        await api(`/api/presets/${presetId}`, "PUT", {
            name: document.getElementById(`preset_${presetId}_name`).value.trim(),
            description: document.getElementById(`preset_${presetId}_description`).value.trim(),
            global_brightness: parseInt(document.getElementById(`preset_${presetId}_global_brightness`).value, 10),
            zone_configs: collectPresetZoneConfigs(`preset_${presetId}`),
        });
        setStatus("preset_status", "Saved mode updated.");
    } catch (err) {
        setStatus("preset_status", err.message, true);
    }
}

async function deletePreset(presetId) {
    try {
        await api(`/api/presets/${presetId}`, "DELETE");
        refreshSoon("preset_status", "Saved mode deleted.");
    } catch (err) {
        setStatus("preset_status", err.message, true);
    }
}

async function applyPreset(presetId) {
    try {
        await api(`/api/presets/${presetId}/apply`, "POST");
        setStatus("preset_status", "Saved mode applied.");
    } catch (err) {
        setStatus("preset_status", err.message, true);
    }
}

async function saveSettings() {
    try {
        await api("/api/settings", "PUT", {
            serial_port: document.getElementById("serial_port").value.trim(),
            baud_rate: parseInt(document.getElementById("baud_rate").value, 10),
            flush_interval_ms: parseInt(document.getElementById("flush_interval_ms").value, 10),
        });
        setStatus("settings_status", "Settings saved and device resynced.");
    } catch (err) {
        setStatus("settings_status", err.message, true);
    }
}

async function reconnectSerial() {
    try {
        await api("/api/serial/reconnect", "POST");
        setStatus("settings_status", "Serial reconnected.");
        setStatus("diagnostics_status", "Serial reconnected.");
    } catch (err) {
        setStatus("settings_status", err.message, true);
        setStatus("diagnostics_status", err.message, true);
    }
}

async function syncLayout() {
    try {
        await api("/api/sync/layout", "POST");
        setStatus("settings_status", "Layout sync triggered.");
        setStatus("diagnostics_status", "Layout sync triggered.");
    } catch (err) {
        setStatus("settings_status", err.message, true);
        setStatus("diagnostics_status", err.message, true);
    }
}

async function refreshDiagnostics() {
    try {
        const data = await api("/api/diagnostics");
        const historyBox = document.getElementById("serial_history_box");
        const snapshotBox = document.getElementById("diagnostics_snapshot");
        if (historyBox) {
            historyBox.textContent = data.serial_history.map((item) => `[${item.direction}] ${item.payload}`).join("\n");
        }
        if (snapshotBox) {
            snapshotBox.textContent = JSON.stringify({
                strips: data.strips,
                zones: data.zones,
                runtime_state: data.runtime_state,
                sync_status: data.sync_status,
            }, null, 2);
        }
        setStatus("diagnostics_status", "Diagnostics refreshed.");
    } catch (err) {
        setStatus("diagnostics_status", err.message, true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.body.dataset.page === "web.index") {
        initDashboard();
    }
    if (document.body.dataset.page === "web.zones_page") {
        initZoneControls();
        renderPixelBoard();
    }
});
