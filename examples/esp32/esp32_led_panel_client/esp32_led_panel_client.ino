#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <mbedtls/base64.h>

#include <vector>
#include <cstring>

const char* WIFI_SSID = "SEU_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA";

const char* API_HOST = "192.168.0.100";
const uint16_t API_PORT = 8000;
const char* API_SCREEN_PATH = "/screen?img_mode=rgb565_base64";

constexpr uint16_t PANEL_WIDTH = 64;
constexpr uint16_t PANEL_HEIGHT = 32;
constexpr uint16_t PANEL_CHAIN = 1;
constexpr uint16_t COVER_SIZE = 32;

constexpr uint32_t POLL_INTERVAL_MS = 2000;
constexpr uint32_t HTTP_TIMEOUT_MS = 4500;
constexpr size_t JSON_DOC_CAPACITY = 16 * 1024;

HUB75_I2S_CFG mxconfig(PANEL_WIDTH, PANEL_HEIGHT, PANEL_CHAIN);
MatrixPanel_I2S_DMA* display = nullptr;

uint32_t lastPollMs = 0;

void connectWiFi();
bool fetchScreenPayload(String& payload);
bool renderPayload(const String& payload);
bool renderCover(const JsonObjectConst& cover, const char* label);
void renderClock(const JsonObjectConst& data);
void renderStatus(const char* line1, const char* line2 = "");
bool decodeBase64(const char* encoded, std::vector<uint8_t>& out);
void drawRgb565Buffer(const std::vector<uint8_t>& rgb565, int16_t x0, int16_t y0, uint16_t w, uint16_t h);

void setup() {
  Serial.begin(115200);

  // Customize HUB75 GPIO mapping here if needed for your board.
  display = new MatrixPanel_I2S_DMA(mxconfig);
  if (!display->begin()) {
    Serial.println("Falha ao inicializar painel HUB75");
    return;
  }

  display->setBrightness8(96);
  display->clearScreen();
  display->setTextWrap(false);

  renderStatus("Booting...", "WiFi connect");
  connectWiFi();
}

void loop() {
  if (!display) {
    delay(2000);
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  const uint32_t now = millis();
  if (now - lastPollMs < POLL_INTERVAL_MS) {
    delay(10);
    return;
  }

  lastPollMs = now;

  String payload;
  if (!fetchScreenPayload(payload)) {
    renderStatus("HTTP error", "check API");
    return;
  }

  if (!renderPayload(payload)) {
    renderStatus("Parse/render", "failed");
  }
}

void connectWiFi() {
  if (!display) {
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  renderStatus("Connecting...", WIFI_SSID);
  Serial.printf("Conectando no WiFi: %s\n", WIFI_SSID);

  const uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) {
    delay(250);
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi conectado. IP local: %s\n", WiFi.localIP().toString().c_str());
    renderStatus("WiFi OK", WiFi.localIP().toString().c_str());
    delay(400);
  } else {
    Serial.println("Falha ao conectar no WiFi");
    renderStatus("WiFi failed", "retrying");
    delay(500);
  }
}

bool fetchScreenPayload(String& payload) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  const String url = String("http://") + API_HOST + ":" + String(API_PORT) + API_SCREEN_PATH;
  if (!http.begin(url)) {
    return false;
  }

  const int statusCode = http.GET();
  if (statusCode != HTTP_CODE_OK) {
    Serial.printf("GET /screen falhou. HTTP=%d\n", statusCode);
    http.end();
    return false;
  }

  payload = http.getString();
  http.end();
  return true;
}

bool renderPayload(const String& payload) {
  DynamicJsonDocument doc(JSON_DOC_CAPACITY);
  const DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.printf("JSON invalido: %s\n", err.c_str());
    return false;
  }

  const char* widget = doc["widget"] | "none";
  const JsonObjectConst data = doc["data"].as<JsonObjectConst>();

  if ((strcmp(widget, "spotify") == 0 || strcmp(widget, "book") == 0) && data["cover"].is<JsonObjectConst>()) {
    const JsonObjectConst cover = data["cover"].as<JsonObjectConst>();
    const char* label = strcmp(widget, "spotify") == 0 ? "SPOT" : "BOOK";
    return renderCover(cover, label);
  }

  if (strcmp(widget, "clock") == 0) {
    renderClock(data);
    return true;
  }

  renderStatus("Unknown widget", widget);
  return false;
}

bool renderCover(const JsonObjectConst& cover, const char* label) {
  const uint16_t w = cover["w"] | 0;
  const uint16_t h = cover["h"] | 0;
  const char* enc = cover["enc"] | "";
  const char* base64Data = cover["data"] | "";

  if (strcmp(enc, "rgb565_base64") != 0) {
    Serial.printf("Encoding nao suportado no sketch: %s\n", enc);
    return false;
  }

  if (w != COVER_SIZE || h != COVER_SIZE) {
    Serial.printf("Dimensao de capa inesperada: %ux%u\n", w, h);
    return false;
  }

  std::vector<uint8_t> rgb565;
  if (!decodeBase64(base64Data, rgb565)) {
    Serial.println("Falha ao decodificar base64");
    return false;
  }

  const size_t expected = static_cast<size_t>(w) * static_cast<size_t>(h) * 2;
  if (rgb565.size() != expected) {
    Serial.printf("Tamanho RGB565 inesperado: %u (esperado %u)\n", static_cast<unsigned>(rgb565.size()), static_cast<unsigned>(expected));
    return false;
  }

  display->clearScreen();
  drawRgb565Buffer(rgb565, 0, 0, w, h);

  display->setTextColor(display->color565(255, 220, 80));
  display->setCursor(35, 8);
  display->print(label);
  display->setTextColor(display->color565(120, 210, 255));
  display->setCursor(35, 20);
  display->print("LIVE");

  return true;
}

void renderClock(const JsonObjectConst& data) {
  const char* hhmm = data["time"] | "--:--";
  const char* sec = data["seconds"] | "--";
  const char* date = data["date"] | "--/--";
  const char* weekday = data["weekday"] | "---";

  display->clearScreen();

  display->setTextColor(display->color565(255, 230, 90));
  display->setCursor(2, 8);
  display->print(hhmm);

  display->setTextColor(display->color565(130, 210, 255));
  display->setCursor(40, 8);
  display->print(sec);

  display->setTextColor(display->color565(180, 255, 180));
  display->setCursor(2, 20);
  display->print(date);

  display->setTextColor(display->color565(255, 170, 170));
  display->setCursor(40, 20);
  display->print(weekday);
}

void renderStatus(const char* line1, const char* line2) {
  if (!display) {
    return;
  }

  display->clearScreen();
  display->setTextColor(display->color565(255, 255, 255));
  display->setCursor(2, 10);
  display->print(line1);

  if (line2 && line2[0] != '\0') {
    display->setTextColor(display->color565(120, 200, 255));
    display->setCursor(2, 22);
    display->print(line2);
  }
}

bool decodeBase64(const char* encoded, std::vector<uint8_t>& out) {
  if (!encoded) {
    return false;
  }

  const size_t inLen = strlen(encoded);
  size_t outLen = 0;

  int rc = mbedtls_base64_decode(
    nullptr,
    0,
    &outLen,
    reinterpret_cast<const unsigned char*>(encoded),
    inLen
  );

  if (rc != MBEDTLS_ERR_BASE64_BUFFER_TOO_SMALL && rc != 0) {
    return false;
  }

  out.resize(outLen);
  rc = mbedtls_base64_decode(
    out.data(),
    out.size(),
    &outLen,
    reinterpret_cast<const unsigned char*>(encoded),
    inLen
  );

  if (rc != 0) {
    return false;
  }

  out.resize(outLen);
  return true;
}

void drawRgb565Buffer(const std::vector<uint8_t>& rgb565, int16_t x0, int16_t y0, uint16_t w, uint16_t h) {
  for (uint16_t y = 0; y < h; y++) {
    for (uint16_t x = 0; x < w; x++) {
      const size_t i = (static_cast<size_t>(y) * w + x) * 2;
      if (i + 1 >= rgb565.size()) {
        return;
      }

      // Backend envia RGB565 em big-endian: high byte, depois low byte.
      const uint16_t color = (static_cast<uint16_t>(rgb565[i]) << 8) | rgb565[i + 1];
      display->drawPixel(x0 + x, y0 + y, color);
    }
  }
}
