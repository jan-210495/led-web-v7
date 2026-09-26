#include <FastLED.h>

// LED Controller V7 firmware for Arduino Due.
// V7 keeps the V6 serial protocol, but uses FastLED with firmware-supported pins.
// Runtime strip config can activate supported pins and choose pixel counts.
// Keep matching Python capability metadata in led_web_v7/device_capabilities.py.

#define LED_TYPE WS2812B
#define COLOR_ORDER BRG

const int BAUD_RATE = 115200;
const int SUPPORTED_STRIP_COUNT = 12;
const int MAX_PIXELS_PER_STRIP = 300;
const int MAX_ZONES = 20;
const int MAX_COMMAND_LEN = 180;
const unsigned long FRAME_DELAY_MS = 10;
const unsigned long IDENTIFY_TOGGLE_MS = 120;
const int IDENTIFY_FLASH_COUNT = 6;

const uint8_t SUPPORTED_PINS[SUPPORTED_STRIP_COUNT] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13};

CRGB ledsPin2[MAX_PIXELS_PER_STRIP];
CRGB ledsPin3[MAX_PIXELS_PER_STRIP];
CRGB ledsPin4[MAX_PIXELS_PER_STRIP];
CRGB ledsPin5[MAX_PIXELS_PER_STRIP];
CRGB ledsPin6[MAX_PIXELS_PER_STRIP];
CRGB ledsPin7[MAX_PIXELS_PER_STRIP];
CRGB ledsPin8[MAX_PIXELS_PER_STRIP];
CRGB ledsPin9[MAX_PIXELS_PER_STRIP];
CRGB ledsPin10[MAX_PIXELS_PER_STRIP];
CRGB ledsPin11[MAX_PIXELS_PER_STRIP];
CRGB ledsPin12[MAX_PIXELS_PER_STRIP];
CRGB ledsPin13[MAX_PIXELS_PER_STRIP];

CRGB* LED_BUFFERS[SUPPORTED_STRIP_COUNT] = {
  ledsPin2,
  ledsPin3,
  ledsPin4,
  ledsPin5,
  ledsPin6,
  ledsPin7,
  ledsPin8,
  ledsPin9,
  ledsPin10,
  ledsPin11,
  ledsPin12,
  ledsPin13
};

struct StripConfig {
  bool active;
  uint8_t pin;
  int pixelCount;
  CRGB* leds;
};

struct Zone {
  bool exists;
  bool enabled;
  String name;
  int startPixel;
  int endPixel;
  int mode;
  int lastMode;
  int r;
  int g;
  int b;
  int r2;
  int g2;
  int b2;
  int r3;
  int g3;
  int b3;
  int brightness;
  int delayMs;
  int step;
  int direction;
};

struct IdentifyState {
  bool active;
  int zoneIndex;
  bool lightsOn;
  int togglesRemaining;
  unsigned long lastToggleAt;
};

StripConfig strips[SUPPORTED_STRIP_COUNT];
Zone zones[MAX_ZONES];
IdentifyState identifyState;

char serialBuffer[MAX_COMMAND_LEN];
int serialLength = 0;
unsigned long lastFrameAt = 0;

void registerFastLedControllers();
void initState();
void configureDefaultStrips();
void clearStripConfig();
int supportedPinIndex(uint8_t pin);
bool addStrip(uint8_t pin, int pixelCount);
bool updateStrip(int stripIndex, uint8_t pin, int pixelCount);
bool deleteStrip(int stripIndex);
int totalPixels();
void listStrips();
bool pixelRangeValid(int startPixel, int endPixel);
int findZoneIndexByName(const String& name);
int createZone(const String& name, int startPixel, int endPixel);
bool updateZoneRange(const String& name, int startPixel, int endPixel);
bool deleteZoneByName(const String& name);
void listZones();
void clearAll();
void showAll();
void renderAllZones();
void renderZone(Zone& zone);
void renderSolid(Zone& zone);
void renderRainbow(Zone& zone);
void renderChase(Zone& zone);
void renderScanner(Zone& zone);
void renderBreathing(Zone& zone);
void renderWave(Zone& zone);
void renderChroma(Zone& zone);
void renderColorwaves(Zone& zone);
void renderTwinkle(Zone& zone);
void renderConfetti(Zone& zone);
void renderIdentifyOverlay();
void startIdentify(int zoneIndex);
void updateIdentifyState();
void setVirtualPixel(int pixelIndex, const CRGB& color);
CRGB scaledColor(int r, int g, int b, int brightness);
CRGB wheel(byte pos);
CRGB paletteColor(Zone& zone, uint8_t pos);
void readSerialCommands();
void processCommand(String cmd);
void handleCreateZone(const String& cmd);
void handleUpdateZone(const String& cmd);
void handleZoneColor(const String& cmd);
void handleZonePalette(const String& cmd);
void handleZoneMode(const String& cmd);
void handleZoneBrightness(const String& cmd);
void handleZoneDelay(const String& cmd);
void handleAddStrip(const String& cmd);
void handleUpdateStrip(const String& cmd);
void handleDeleteStrip(const String& cmd);
void handleGlobalColor(const String& cmd);
void handleGlobalPalette(const String& cmd);
void handleGlobalDelay(const String& cmd);

void setup() {
  Serial.begin(BAUD_RATE);
  registerFastLedControllers();
  FastLED.setBrightness(255);
  initState();
  configureDefaultStrips();
  clearAll();
  showAll();
  Serial.println("READY_V7_FASTLED");
}

void loop() {
  readSerialCommands();

  unsigned long now = millis();
  if (now - lastFrameAt >= FRAME_DELAY_MS) {
    lastFrameAt = now;
    updateIdentifyState();
    renderAllZones();
  }
}

void registerFastLedControllers() {
  FastLED.addLeds<LED_TYPE, 2, COLOR_ORDER>(ledsPin2, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 3, COLOR_ORDER>(ledsPin3, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 4, COLOR_ORDER>(ledsPin4, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 5, COLOR_ORDER>(ledsPin5, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 6, COLOR_ORDER>(ledsPin6, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 7, COLOR_ORDER>(ledsPin7, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 8, COLOR_ORDER>(ledsPin8, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 9, COLOR_ORDER>(ledsPin9, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 10, COLOR_ORDER>(ledsPin10, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 11, COLOR_ORDER>(ledsPin11, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 12, COLOR_ORDER>(ledsPin12, MAX_PIXELS_PER_STRIP);
  FastLED.addLeds<LED_TYPE, 13, COLOR_ORDER>(ledsPin13, MAX_PIXELS_PER_STRIP);
}

void initState() {
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    strips[i].active = false;
    strips[i].pin = SUPPORTED_PINS[i];
    strips[i].pixelCount = 0;
    strips[i].leds = LED_BUFFERS[i];
  }

  for (int i = 0; i < MAX_ZONES; i++) {
    zones[i].exists = false;
    zones[i].enabled = false;
    zones[i].name = "";
    zones[i].startPixel = 0;
    zones[i].endPixel = 0;
    zones[i].mode = 0;
    zones[i].lastMode = 1;
    zones[i].r = 255;
    zones[i].g = 96;
    zones[i].b = 32;
    zones[i].r2 = 255;
    zones[i].g2 = 0;
    zones[i].b2 = 140;
    zones[i].r3 = 0;
    zones[i].g3 = 190;
    zones[i].b3 = 255;
    zones[i].brightness = 96;
    zones[i].delayMs = 40;
    zones[i].step = 0;
    zones[i].direction = 1;
  }

  identifyState.active = false;
  identifyState.zoneIndex = -1;
  identifyState.lightsOn = false;
  identifyState.togglesRemaining = 0;
  identifyState.lastToggleAt = 0;
}

void configureDefaultStrips() {
  addStrip(6, 8);
  addStrip(7, 23);
  addStrip(9, 37);
}

void clearStripConfig() {
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    fill_solid(strips[i].leds, MAX_PIXELS_PER_STRIP, CRGB::Black);
    strips[i].active = false;
    strips[i].pixelCount = 0;
  }
  showAll();
}

int supportedPinIndex(uint8_t pin) {
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    if (SUPPORTED_PINS[i] == pin) return i;
  }
  return -1;
}

bool addStrip(uint8_t pin, int pixelCount) {
  int idx = supportedPinIndex(pin);
  if (idx < 0) return false;
  if (pixelCount <= 0 || pixelCount > MAX_PIXELS_PER_STRIP) return false;

  strips[idx].active = true;
  strips[idx].pixelCount = pixelCount;
  fill_solid(strips[idx].leds, MAX_PIXELS_PER_STRIP, CRGB::Black);
  return true;
}

bool updateStrip(int stripIndex, uint8_t pin, int pixelCount) {
  if (stripIndex < 0 || stripIndex >= SUPPORTED_STRIP_COUNT) return false;
  if (!strips[stripIndex].active) return false;
  if (strips[stripIndex].pin != pin) {
    strips[stripIndex].active = false;
    strips[stripIndex].pixelCount = 0;
    return addStrip(pin, pixelCount);
  }
  return addStrip(pin, pixelCount);
}

bool deleteStrip(int stripIndex) {
  if (stripIndex < 0 || stripIndex >= SUPPORTED_STRIP_COUNT) return false;
  fill_solid(strips[stripIndex].leds, MAX_PIXELS_PER_STRIP, CRGB::Black);
  strips[stripIndex].active = false;
  strips[stripIndex].pixelCount = 0;
  return true;
}

int totalPixels() {
  int total = 0;
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    if (strips[i].active) total += strips[i].pixelCount;
  }
  return total;
}

void listStrips() {
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    if (strips[i].active) {
      Serial.print("STRIP:");
      Serial.print(i);
      Serial.print(":");
      Serial.print(strips[i].pin);
      Serial.print(":");
      Serial.println(strips[i].pixelCount);
    }
  }
  Serial.println("END_STRIPS");
}

bool pixelRangeValid(int startPixel, int endPixel) {
  int total = totalPixels();
  if (total <= 0) return false;
  if (startPixel < 0 || endPixel < 0) return false;
  if (startPixel > endPixel) return false;
  if (startPixel >= total || endPixel >= total) return false;
  return true;
}

int findZoneIndexByName(const String& name) {
  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists && zones[i].name == name) return i;
  }
  return -1;
}

int createZone(const String& name, int startPixel, int endPixel) {
  if (!pixelRangeValid(startPixel, endPixel)) return -2;
  if (findZoneIndexByName(name) >= 0) return -3;

  for (int i = 0; i < MAX_ZONES; i++) {
    if (!zones[i].exists) {
      zones[i].exists = true;
      zones[i].enabled = true;
      zones[i].name = name;
      zones[i].startPixel = startPixel;
      zones[i].endPixel = endPixel;
      zones[i].mode = 1;
      zones[i].lastMode = 1;
      zones[i].r = 255;
      zones[i].g = 96;
      zones[i].b = 32;
      zones[i].r2 = 255;
      zones[i].g2 = 0;
      zones[i].b2 = 140;
      zones[i].r3 = 0;
      zones[i].g3 = 190;
      zones[i].b3 = 255;
      zones[i].brightness = 96;
      zones[i].delayMs = 40;
      zones[i].step = 0;
      zones[i].direction = 1;
      return i;
    }
  }

  return -1;
}

bool updateZoneRange(const String& name, int startPixel, int endPixel) {
  if (!pixelRangeValid(startPixel, endPixel)) return false;

  int idx = findZoneIndexByName(name);
  if (idx < 0) return false;

  zones[idx].startPixel = startPixel;
  zones[idx].endPixel = endPixel;
  zones[idx].step = 0;
  zones[idx].direction = 1;
  return true;
}

bool deleteZoneByName(const String& name) {
  int idx = findZoneIndexByName(name);
  if (idx < 0) return false;

  zones[idx].exists = false;
  zones[idx].enabled = false;
  if (identifyState.active && identifyState.zoneIndex == idx) {
    identifyState.active = false;
  }
  return true;
}

void listZones() {
  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists) {
      Serial.print("ZONE:");
      Serial.print(zones[i].name);
      Serial.print(":");
      Serial.print(zones[i].startPixel);
      Serial.print(":");
      Serial.println(zones[i].endPixel);
    }
  }
  Serial.println("END_ZONES");
}

void readSerialCommands() {
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\r') continue;

    if (c == '\n') {
      serialBuffer[serialLength] = '\0';
      String cmd = String(serialBuffer);
      serialLength = 0;
      cmd.trim();

      if (cmd.length() > 0) {
        processCommand(cmd);
      }
    } else if (serialLength < MAX_COMMAND_LEN - 1) {
      serialBuffer[serialLength++] = c;
    } else {
      serialLength = 0;
      Serial.println("ERR:COMMAND_TOO_LONG");
    }
  }
}

void processCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
    return;
  }

  if (cmd == "LIST_ZONES") {
    listZones();
    return;
  }

  if (cmd == "LIST_STRIPS") {
    listStrips();
    return;
  }

  if (cmd == "CLEAR_STRIPS") {
    clearStripConfig();
    Serial.println("OK:CLEAR_STRIPS");
    return;
  }

  if (cmd.startsWith("ADD_STRIP:")) {
    handleAddStrip(cmd);
    return;
  }

  if (cmd.startsWith("UPDATE_STRIP:")) {
    handleUpdateStrip(cmd);
    return;
  }

  if (cmd.startsWith("DELETE_STRIP:")) {
    handleDeleteStrip(cmd);
    return;
  }

  if (cmd.startsWith("CREATE_ZONE:")) {
    handleCreateZone(cmd);
    return;
  }

  if (cmd.startsWith("UPDATE_ZONE:")) {
    handleUpdateZone(cmd);
    return;
  }

  if (cmd.startsWith("DELETE_ZONE:")) {
    String name = cmd.substring(12);
    if (deleteZoneByName(name)) Serial.println("OK:DELETE_ZONE");
    else Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  if (cmd == "ALL_OFF") {
    for (int i = 0; i < MAX_ZONES; i++) {
      if (zones[i].exists) {
        if (zones[i].mode != 0) zones[i].lastMode = zones[i].mode;
        zones[i].enabled = false;
        zones[i].mode = 0;
      }
    }
    Serial.println("OK:ALL_OFF");
    return;
  }

  if (cmd.startsWith("ALL_COLOR:")) {
    handleGlobalColor(cmd);
    return;
  }

  if (cmd.startsWith("ALL_PALETTE:")) {
    handleGlobalPalette(cmd);
    return;
  }

  if (cmd.startsWith("ALL_MODE:")) {
    int mode = cmd.substring(9).toInt();
    for (int i = 0; i < MAX_ZONES; i++) {
      if (zones[i].exists) {
        zones[i].mode = mode;
        if (mode != 0) {
          zones[i].lastMode = mode;
          zones[i].enabled = true;
        } else {
          zones[i].enabled = false;
        }
        zones[i].step = 0;
        zones[i].direction = 1;
      }
    }
    Serial.println("OK:ALL_MODE");
    return;
  }

  if (cmd.startsWith("ALL_BRIGHTNESS:")) {
    int value = constrain(cmd.substring(15).toInt(), 0, 255);
    for (int i = 0; i < MAX_ZONES; i++) {
      if (zones[i].exists) zones[i].brightness = value;
    }
    Serial.println("OK:ALL_BRIGHTNESS");
    return;
  }

  if (cmd.startsWith("ALL_DELAY:")) {
    handleGlobalDelay(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_COLOR:")) {
    handleZoneColor(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_PALETTE:")) {
    handleZonePalette(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_MODE:")) {
    handleZoneMode(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_BRIGHTNESS:")) {
    handleZoneBrightness(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_DELAY:")) {
    handleZoneDelay(cmd);
    return;
  }

  if (cmd.startsWith("ZONE_OFF:")) {
    String zoneName = cmd.substring(9);
    int idx = findZoneIndexByName(zoneName);

    if (idx >= 0) {
      if (zones[idx].mode != 0) zones[idx].lastMode = zones[idx].mode;
      zones[idx].enabled = false;
      zones[idx].mode = 0;
      Serial.println("OK:ZONE_OFF");
    } else {
      Serial.println("ERR:ZONE_NOT_FOUND");
    }
    return;
  }

  if (cmd.startsWith("ZONE_ON:")) {
    String zoneName = cmd.substring(8);
    int idx = findZoneIndexByName(zoneName);

    if (idx >= 0) {
      zones[idx].enabled = true;
      if (zones[idx].mode == 0) zones[idx].mode = zones[idx].lastMode > 0 ? zones[idx].lastMode : 1;
      zones[idx].step = 0;
      zones[idx].direction = 1;
      Serial.println("OK:ZONE_ON");
    } else {
      Serial.println("ERR:ZONE_NOT_FOUND");
    }
    return;
  }

  if (cmd.startsWith("ZONE_IDENTIFY:")) {
    String zoneName = cmd.substring(14);
    int idx = findZoneIndexByName(zoneName);

    if (idx >= 0) {
      startIdentify(idx);
      Serial.println("OK:ZONE_IDENTIFY");
    } else {
      Serial.println("ERR:ZONE_NOT_FOUND");
    }
    return;
  }

  Serial.println("ERR:UNKNOWN_COMMAND");
}

void handleCreateZone(const String& cmd) {
  int p1 = cmd.indexOf(':');
  int p2 = cmd.indexOf(':', p1 + 1);
  int p3 = cmd.indexOf(':', p2 + 1);

  if (p1 > 0 && p2 > p1 && p3 > p2) {
    String name = cmd.substring(p1 + 1, p2);
    int startPixel = cmd.substring(p2 + 1, p3).toInt();
    int endPixel = cmd.substring(p3 + 1).toInt();

    int result = createZone(name, startPixel, endPixel);
    if (result >= 0) Serial.println("OK:CREATE_ZONE");
    else if (result == -2) Serial.println("ERR:INVALID_RANGE");
    else if (result == -3) Serial.println("ERR:ZONE_EXISTS");
    else Serial.println("ERR:ZONE_LIMIT");
  } else {
    Serial.println("ERR:BAD_COMMAND");
  }
}

void handleUpdateZone(const String& cmd) {
  int p1 = cmd.indexOf(':');
  int p2 = cmd.indexOf(':', p1 + 1);
  int p3 = cmd.indexOf(':', p2 + 1);

  if (p1 > 0 && p2 > p1 && p3 > p2) {
    String name = cmd.substring(p1 + 1, p2);
    int startPixel = cmd.substring(p2 + 1, p3).toInt();
    int endPixel = cmd.substring(p3 + 1).toInt();

    if (updateZoneRange(name, startPixel, endPixel)) Serial.println("OK:UPDATE_ZONE");
    else Serial.println("ERR:UPDATE_ZONE");
  } else {
    Serial.println("ERR:BAD_COMMAND");
  }
}

bool parseRgb(const String& rgbPart, int& r, int& g, int& b) {
  int firstComma = rgbPart.indexOf(',');
  int secondComma = rgbPart.indexOf(',', firstComma + 1);
  if (firstComma <= 0 || secondComma <= firstComma) return false;
  r = constrain(rgbPart.substring(0, firstComma).toInt(), 0, 255);
  g = constrain(rgbPart.substring(firstComma + 1, secondComma).toInt(), 0, 255);
  b = constrain(rgbPart.substring(secondComma + 1).toInt(), 0, 255);
  return true;
}

void handleZoneColor(const String& cmd) {
  int firstColon = cmd.indexOf(':');
  int secondColon = cmd.indexOf(':', firstColon + 1);
  if (secondColon <= firstColon) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  String zoneName = cmd.substring(firstColon + 1, secondColon);
  int idx = findZoneIndexByName(zoneName);
  if (idx < 0) {
    Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  if (!parseRgb(cmd.substring(secondColon + 1), zones[idx].r, zones[idx].g, zones[idx].b)) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  Serial.println("OK:ZONE_COLOR");
}

void handleZonePalette(const String& cmd) {
  int firstColon = cmd.indexOf(':');
  int secondColon = cmd.indexOf(':', firstColon + 1);
  if (secondColon <= firstColon) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  String zoneName = cmd.substring(firstColon + 1, secondColon);
  int idx = findZoneIndexByName(zoneName);
  if (idx < 0) {
    Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  String palettePart = cmd.substring(secondColon + 1);
  int firstSep = palettePart.indexOf(';');
  int secondSep = palettePart.indexOf(';', firstSep + 1);
  if (firstSep <= 0 || secondSep <= firstSep) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  if (
    !parseRgb(palettePart.substring(0, firstSep), zones[idx].r, zones[idx].g, zones[idx].b) ||
    !parseRgb(palettePart.substring(firstSep + 1, secondSep), zones[idx].r2, zones[idx].g2, zones[idx].b2) ||
    !parseRgb(palettePart.substring(secondSep + 1), zones[idx].r3, zones[idx].g3, zones[idx].b3)
  ) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  Serial.println("OK:ZONE_PALETTE");
}

void handleZoneMode(const String& cmd) {
  int firstColon = cmd.indexOf(':');
  int secondColon = cmd.indexOf(':', firstColon + 1);
  if (secondColon <= firstColon) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  String zoneName = cmd.substring(firstColon + 1, secondColon);
  int mode = cmd.substring(secondColon + 1).toInt();
  int idx = findZoneIndexByName(zoneName);
  if (idx < 0) {
    Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  zones[idx].mode = mode;
  if (mode != 0) {
    zones[idx].lastMode = mode;
    zones[idx].enabled = true;
  } else {
    zones[idx].enabled = false;
  }
  zones[idx].step = 0;
  zones[idx].direction = 1;
  Serial.println("OK:ZONE_MODE");
}

void handleZoneBrightness(const String& cmd) {
  int firstColon = cmd.indexOf(':');
  int secondColon = cmd.indexOf(':', firstColon + 1);
  if (secondColon <= firstColon) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  String zoneName = cmd.substring(firstColon + 1, secondColon);
  int idx = findZoneIndexByName(zoneName);
  if (idx < 0) {
    Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  zones[idx].brightness = constrain(cmd.substring(secondColon + 1).toInt(), 0, 255);
  Serial.println("OK:ZONE_BRIGHTNESS");
}

void handleZoneDelay(const String& cmd) {
  int firstColon = cmd.indexOf(':');
  int secondColon = cmd.indexOf(':', firstColon + 1);
  if (secondColon <= firstColon) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  String zoneName = cmd.substring(firstColon + 1, secondColon);
  int idx = findZoneIndexByName(zoneName);
  if (idx < 0) {
    Serial.println("ERR:ZONE_NOT_FOUND");
    return;
  }

  zones[idx].delayMs = constrain(cmd.substring(secondColon + 1).toInt(), 10, 2000);
  Serial.println("OK:ZONE_DELAY");
}

void handleGlobalColor(const String& cmd) {
  int r, g, b;
  if (!parseRgb(cmd.substring(10), r, g, b)) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists) {
      zones[i].r = r;
      zones[i].g = g;
      zones[i].b = b;
    }
  }

  Serial.println("OK:ALL_COLOR");
}

void handleGlobalPalette(const String& cmd) {
  String palettePart = cmd.substring(12);
  int firstSep = palettePart.indexOf(';');
  int secondSep = palettePart.indexOf(';', firstSep + 1);

  if (firstSep <= 0 || secondSep <= firstSep) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  int r1, g1, b1, r2, g2, b2, r3, g3, b3;
  if (
    !parseRgb(palettePart.substring(0, firstSep), r1, g1, b1) ||
    !parseRgb(palettePart.substring(firstSep + 1, secondSep), r2, g2, b2) ||
    !parseRgb(palettePart.substring(secondSep + 1), r3, g3, b3)
  ) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists) {
      zones[i].r = r1;
      zones[i].g = g1;
      zones[i].b = b1;
      zones[i].r2 = r2;
      zones[i].g2 = g2;
      zones[i].b2 = b2;
      zones[i].r3 = r3;
      zones[i].g3 = g3;
      zones[i].b3 = b3;
    }
  }

  Serial.println("OK:ALL_PALETTE");
}

void handleGlobalDelay(const String& cmd) {
  int value = constrain(cmd.substring(10).toInt(), 10, 2000);
  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists) zones[i].delayMs = value;
  }
  Serial.println("OK:ALL_DELAY");
}

void handleAddStrip(const String& cmd) {
  int p1 = cmd.indexOf(':');
  int p2 = cmd.indexOf(':', p1 + 1);
  if (p1 <= 0 || p2 <= p1) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  uint8_t pin = (uint8_t)cmd.substring(p1 + 1, p2).toInt();
  int pixelCount = cmd.substring(p2 + 1).toInt();
  if (addStrip(pin, pixelCount)) Serial.println("OK:ADD_STRIP");
  else Serial.println("ERR:ADD_STRIP");
}

void handleUpdateStrip(const String& cmd) {
  int p1 = cmd.indexOf(':');
  int p2 = cmd.indexOf(':', p1 + 1);
  int p3 = cmd.indexOf(':', p2 + 1);
  if (p1 <= 0 || p2 <= p1 || p3 <= p2) {
    Serial.println("ERR:BAD_COMMAND");
    return;
  }

  int stripIndex = cmd.substring(p1 + 1, p2).toInt();
  uint8_t pin = (uint8_t)cmd.substring(p2 + 1, p3).toInt();
  int pixelCount = cmd.substring(p3 + 1).toInt();
  if (updateStrip(stripIndex, pin, pixelCount)) Serial.println("OK:UPDATE_STRIP");
  else Serial.println("ERR:UPDATE_STRIP");
}

void handleDeleteStrip(const String& cmd) {
  int stripIndex = cmd.substring(13).toInt();
  if (deleteStrip(stripIndex)) Serial.println("OK:DELETE_STRIP");
  else Serial.println("ERR:DELETE_STRIP");
}

void renderAllZones() {
  clearAll();

  for (int i = 0; i < MAX_ZONES; i++) {
    if (zones[i].exists && zones[i].enabled && zones[i].mode != 0) {
      renderZone(zones[i]);
    }
  }

  renderIdentifyOverlay();
  showAll();
}

void renderZone(Zone& zone) {
  if (zone.delayMs > FRAME_DELAY_MS) {
    int divisor = max(1, zone.delayMs / FRAME_DELAY_MS);
    if ((zone.step % divisor) != 0 && zone.mode != 1) {
      renderSolid(zone);
      zone.step++;
      return;
    }
  }

  switch (zone.mode) {
    case 1: renderSolid(zone); break;
    case 2: renderRainbow(zone); break;
    case 3: renderChase(zone); break;
    case 4: renderScanner(zone); break;
    case 5: renderBreathing(zone); break;
    case 6: renderWave(zone); break;
    case 7: renderChroma(zone); break;
    case 8: renderColorwaves(zone); break;
    case 9: renderTwinkle(zone); break;
    case 10: renderConfetti(zone); break;
    default: renderSolid(zone); break;
  }
}

void renderSolid(Zone& zone) {
  CRGB color = scaledColor(zone.r, zone.g, zone.b, zone.brightness);
  for (int i = zone.startPixel; i <= zone.endPixel; i++) {
    setVirtualPixel(i, color);
  }
}

void renderRainbow(Zone& zone) {
  int zoneLength = zone.endPixel - zone.startPixel + 1;
  if (zoneLength <= 0) return;

  for (int i = 0; i < zoneLength; i++) {
    uint8_t hue = (uint8_t)((i * 255 / max(zoneLength, 1) + zone.step) & 255);
    CRGB color = CHSV(hue, 255, constrain(zone.brightness, 0, 255));
    setVirtualPixel(zone.startPixel + i, color);
  }
  zone.step = (zone.step + max(1, 80 / max(10, zone.delayMs))) & 255;
}

void renderChase(Zone& zone) {
  CRGB color = scaledColor(zone.r, zone.g, zone.b, zone.brightness);
  for (int i = zone.startPixel; i <= zone.endPixel; i++) {
    if (((i - zone.startPixel + zone.step) % 3) == 0) {
      setVirtualPixel(i, color);
    }
  }
  zone.step = (zone.step + 1) % 3;
}

void renderScanner(Zone& zone) {
  int zoneLength = zone.endPixel - zone.startPixel + 1;
  if (zoneLength <= 0) return;

  CRGB color = scaledColor(zone.r, zone.g, zone.b, zone.brightness);
  int pos = zone.startPixel + zone.step;
  setVirtualPixel(pos, color);

  zone.step += zone.direction;
  if (zone.step >= zoneLength - 1 || zone.step <= 0) {
    zone.direction = -zone.direction;
  }
}

void renderBreathing(Zone& zone) {
  uint8_t breath = sin8(zone.step);
  int scale = map(breath, 0, 255, 10, constrain(zone.brightness, 0, 255));
  CRGB color = scaledColor(zone.r, zone.g, zone.b, scale);

  for (int i = zone.startPixel; i <= zone.endPixel; i++) {
    setVirtualPixel(i, color);
  }

  zone.step = (zone.step + max(1, 90 / max(10, zone.delayMs))) & 255;
}

void renderWave(Zone& zone) {
  int zoneLength = zone.endPixel - zone.startPixel + 1;
  if (zoneLength <= 0) return;

  for (int i = 0; i < zoneLength; i++) {
    uint8_t pos = (uint8_t)((i * 255 / max(zoneLength - 1, 1) + zone.step) & 255);
    setVirtualPixel(zone.startPixel + i, paletteColor(zone, pos));
  }

  zone.step = (zone.step + max(1, 120 / max(10, zone.delayMs))) & 255;
}

void renderChroma(Zone& zone) {
  int zoneLength = zone.endPixel - zone.startPixel + 1;
  if (zoneLength <= 0) return;

  for (int i = 0; i < zoneLength; i++) {
    uint8_t hue = (uint8_t)((zone.step + i * 9) & 255);
    setVirtualPixel(zone.startPixel + i, CHSV(hue, 255, constrain(zone.brightness, 0, 255)));
  }

  zone.step = (zone.step + max(1, 150 / max(10, zone.delayMs))) & 255;
}

void renderColorwaves(Zone& zone) {
  int zoneLength = zone.endPixel - zone.startPixel + 1;
  if (zoneLength <= 0) return;

  for (int i = 0; i < zoneLength; i++) {
    uint8_t pos = sin8(zone.step + i * 12);
    setVirtualPixel(zone.startPixel + i, paletteColor(zone, pos));
  }

  zone.step = (zone.step + max(1, 100 / max(10, zone.delayMs))) & 255;
}

void renderTwinkle(Zone& zone) {
  CRGB base = scaledColor(zone.r, zone.g, zone.b, max(8, zone.brightness / 6));
  for (int i = zone.startPixel; i <= zone.endPixel; i++) {
    setVirtualPixel(i, base);
  }

  int zoneLength = zone.endPixel - zone.startPixel + 1;
  int sparkles = max(1, zoneLength / 8);
  for (int i = 0; i < sparkles; i++) {
    int pixel = zone.startPixel + ((zone.step * 17 + i * 23) % zoneLength);
    uint8_t pos = (uint8_t)((zone.step * 9 + i * 47) & 255);
    setVirtualPixel(pixel, paletteColor(zone, pos));
  }

  zone.step = (zone.step + max(1, 60 / max(10, zone.delayMs))) & 255;
}

void renderConfetti(Zone& zone) {
  CRGB background = scaledColor(zone.r, zone.g, zone.b, max(0, zone.brightness / 10));
  for (int i = zone.startPixel; i <= zone.endPixel; i++) {
    setVirtualPixel(i, background);
  }

  int zoneLength = zone.endPixel - zone.startPixel + 1;
  int flecks = max(1, zoneLength / 10);
  for (int i = 0; i < flecks; i++) {
    int pixel = zone.startPixel + ((zone.step * 11 + i * 29) % zoneLength);
    uint8_t pos = (uint8_t)((zone.step * 13 + i * 61) & 255);
    setVirtualPixel(pixel, paletteColor(zone, pos));
  }

  zone.step = (zone.step + max(1, 80 / max(10, zone.delayMs))) & 255;
}

void startIdentify(int zoneIndex) {
  identifyState.active = true;
  identifyState.zoneIndex = zoneIndex;
  identifyState.lightsOn = true;
  identifyState.togglesRemaining = IDENTIFY_FLASH_COUNT;
  identifyState.lastToggleAt = millis();
}

void updateIdentifyState() {
  if (!identifyState.active) return;

  unsigned long now = millis();
  if (now - identifyState.lastToggleAt >= IDENTIFY_TOGGLE_MS) {
    identifyState.lastToggleAt = now;
    identifyState.lightsOn = !identifyState.lightsOn;
    identifyState.togglesRemaining--;
    if (identifyState.togglesRemaining <= 0) {
      identifyState.active = false;
      identifyState.zoneIndex = -1;
      identifyState.lightsOn = false;
    }
  }
}

void renderIdentifyOverlay() {
  if (!identifyState.active) return;
  if (!identifyState.lightsOn) return;
  if (identifyState.zoneIndex < 0 || identifyState.zoneIndex >= MAX_ZONES) return;
  if (!zones[identifyState.zoneIndex].exists) return;

  for (int i = zones[identifyState.zoneIndex].startPixel; i <= zones[identifyState.zoneIndex].endPixel; i++) {
    setVirtualPixel(i, CRGB::White);
  }
}

void setVirtualPixel(int pixelIndex, const CRGB& color) {
  if (pixelIndex < 0 || pixelIndex >= totalPixels()) return;

  int offset = 0;
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    if (!strips[i].active) continue;

    int stripStart = offset;
    int stripEnd = offset + strips[i].pixelCount - 1;
    if (pixelIndex >= stripStart && pixelIndex <= stripEnd) {
      strips[i].leds[pixelIndex - stripStart] = color;
      return;
    }
    offset += strips[i].pixelCount;
  }
}

void clearAll() {
  for (int i = 0; i < SUPPORTED_STRIP_COUNT; i++) {
    fill_solid(strips[i].leds, MAX_PIXELS_PER_STRIP, CRGB::Black);
  }
}

void showAll() {
  FastLED.show();
}

CRGB scaledColor(int r, int g, int b, int brightness) {
  CRGB color(constrain(r, 0, 255), constrain(g, 0, 255), constrain(b, 0, 255));
  color.nscale8_video(constrain(brightness, 0, 255));
  return color;
}

CRGB wheel(byte pos) {
  return CHSV(pos, 255, 255);
}

CRGB paletteColor(Zone& zone, uint8_t pos) {
  CRGB c1(zone.r, zone.g, zone.b);
  CRGB c2(zone.r2, zone.g2, zone.b2);
  CRGB c3(zone.r3, zone.g3, zone.b3);
  CRGB color;

  if (pos < 128) {
    color = blend(c1, c2, pos * 2);
  } else {
    color = blend(c2, c3, (pos - 128) * 2);
  }

  color.nscale8_video(constrain(zone.brightness, 0, 255));
  return color;
}
