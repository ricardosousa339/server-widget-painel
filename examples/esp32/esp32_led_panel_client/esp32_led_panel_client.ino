#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <mbedtls/base64.h>
#include <time.h>

#include <vector>
#include <cstring>
#include <cctype>

const char* WIFI_SSID = "SEU_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA";

const char* API_HOST = "192.168.0.100";
const uint16_t API_PORT = 8000;
const char* API_SCREEN_PATH = "/screen?img_mode=rgb565_base64";

constexpr uint16_t PANEL_WIDTH = 64;
constexpr uint16_t PANEL_HEIGHT = 32;
constexpr uint16_t PANEL_CHAIN = 1;
constexpr uint16_t COVER_SIZE = 32;
constexpr uint16_t COVER_TARGET_SIZE = 26;
constexpr int16_t TEXT_LEFT_X = 27;
constexpr int16_t TITLE_Y = 8;
constexpr int16_t AUTHOR_Y = 19;
constexpr int16_t PROGRESS_Y = 29;

// Busca de dados em baixa frequencia para spotify/clock.
constexpr uint32_t SOURCE_POLL_INTERVAL_MS = 1500;
// Quando custom_gif estiver ativo, aumenta o polling para animacao mais fluida.
constexpr uint32_t SOURCE_POLL_INTERVAL_GIF_MS = 90;
// Render local em alta frequencia para scroll suave pixel-a-pixel.
constexpr uint32_t RENDER_INTERVAL_MS = 33;
constexpr uint32_t HTTP_TIMEOUT_MS = 1800;
constexpr uint32_t API_STALE_TIMEOUT_MS = 5000;
constexpr size_t JSON_DOC_CAPACITY = 16 * 1024;
constexpr uint32_t TITLE_SCROLL_TICK_MS = 70;
constexpr uint32_t AUTHOR_SCROLL_TICK_MS = 90;
constexpr uint32_t NTP_RETRY_INTERVAL_MS = 5000;
constexpr uint32_t NTP_RESYNC_INTERVAL_MS = 3600000;

const char* TZ_INFO = "UTC0";  // Exemplo BRT: "BRT3"
const char* NTP_SERVER_1 = "pool.ntp.org";
const char* NTP_SERVER_2 = "time.google.com";

HUB75_I2S_CFG mxconfig(PANEL_WIDTH, PANEL_HEIGHT, PANEL_CHAIN);
MatrixPanel_I2S_DMA* display = nullptr;

enum WidgetKind {
  WidgetNone,
  WidgetClock,
  WidgetSpotify,
  WidgetCustomGif,
};

struct RenderState {
  WidgetKind widget = WidgetNone;
  String widgetName = "none";

  String timeText = "--:--";
  String dateText = "--/--";
  String weekdayText = "---";

  String title = "-";
  String author = "-";
  uint32_t progressMs = 0;
  uint32_t durationMs = 0;

  bool hasCover = false;
  std::vector<uint16_t> coverScaled565;

  bool hasCustomFrame = false;
  uint16_t customFrameW = 0;
  uint16_t customFrameH = 0;
  std::vector<uint16_t> customFrame565;
};

RenderState gState;

String gTitleMarqueeKey = "";
String gAuthorMarqueeKey = "";
uint32_t gTitleStartedMs = 0;
uint32_t gAuthorStartedMs = 0;

uint32_t lastSourcePollMs = 0;
uint32_t lastRenderMs = 0;
uint32_t lastSourceSuccessMs = 0;
uint32_t lastNtpAttemptMs = 0;
uint32_t lastNtpResyncMs = 0;
bool ntpConfigured = false;
bool ntpSynced = false;

void connectWiFi();
bool fetchScreenPayload(String& payload);
bool updateStateFromPayload(const String& payload);
void renderCurrentFrame(uint32_t nowMs);
bool renderLocalClockFallback();
bool getLocalClockStrings(String& timeOut, String& dateOut, String& weekdayOut);
void maintainNtpClock(uint32_t nowMs);
void renderClockFrame();
void renderMediaFrame(bool isSpotify, uint32_t nowMs);
void renderCustomGifFrame();
void drawCoverScaled(int16_t x0, int16_t y0);
bool decodeAndScaleCover(const JsonObjectConst& cover, std::vector<uint16_t>& out);
bool decodeRgb565Frame(
  const JsonObjectConst& frame,
  std::vector<uint16_t>& out,
  uint16_t& outW,
  uint16_t& outH
);
uint16_t measureTextWidth(const String& text);
void drawMarqueeText(
  const String& text,
  int16_t baseX,
  int16_t y,
  int16_t visibleWidth,
  uint32_t nowMs,
  uint32_t tickMs,
  uint8_t gapChars,
  String& stateKey,
  uint32_t& stateStartedMs,
  uint16_t color
);
String compactArtistName(const String& artist);
void renderStatus(const char* line1, const char* line2 = "");
bool decodeBase64(const char* encoded, std::vector<uint8_t>& out);

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
  display->setTextSize(1);

  gState.coverScaled565.reserve(static_cast<size_t>(COVER_TARGET_SIZE) * COVER_TARGET_SIZE);
  gState.customFrame565.reserve(static_cast<size_t>(PANEL_WIDTH) * PANEL_HEIGHT);

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
  maintainNtpClock(now);

  const uint32_t sourcePollInterval =
    (gState.widget == WidgetCustomGif) ? SOURCE_POLL_INTERVAL_GIF_MS : SOURCE_POLL_INTERVAL_MS;

  if (now - lastSourcePollMs >= sourcePollInterval) {
    lastSourcePollMs = now;

    String payload;
    if (fetchScreenPayload(payload) && updateStateFromPayload(payload)) {
      lastSourceSuccessMs = now;
    }
  }

  if (now - lastRenderMs >= RENDER_INTERVAL_MS) {
    lastRenderMs = now;
    renderCurrentFrame(now);
  }

  delay(1);
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
    configTzTime(TZ_INFO, NTP_SERVER_1, NTP_SERVER_2);
    ntpConfigured = true;
    lastNtpAttemptMs = millis();
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

bool updateStateFromPayload(const String& payload) {
  DynamicJsonDocument doc(JSON_DOC_CAPACITY);
  const DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.printf("JSON invalido: %s\n", err.c_str());
    return false;
  }

  const char* widget = doc["widget"] | "none";
  const JsonObjectConst data = doc["data"].as<JsonObjectConst>();

  gState.widgetName = widget;

  if (strcmp(widget, "spotify") == 0) {
    gState.widget = WidgetSpotify;
    gState.title = data["track"] | "-";
    gState.author = compactArtistName(data["artist"] | "-");
    gState.progressMs = data["progress_ms"] | 0;
    gState.durationMs = data["duration_ms"] | 0;

    if (data["cover"].is<JsonObjectConst>()) {
      gState.hasCover = decodeAndScaleCover(data["cover"].as<JsonObjectConst>(), gState.coverScaled565);
    } else {
      gState.hasCover = false;
      gState.coverScaled565.clear();
    }

    gState.hasCustomFrame = false;
    gState.customFrameW = 0;
    gState.customFrameH = 0;
    gState.customFrame565.clear();
    return true;
  }

  if (strcmp(widget, "clock") == 0) {
    gState.widget = WidgetClock;
    gState.timeText = data["time"] | "--:--";
    gState.dateText = data["date"] | "--/--";
    gState.weekdayText = data["weekday"] | "---";
    gState.hasCover = false;
    gState.coverScaled565.clear();

    gState.hasCustomFrame = false;
    gState.customFrameW = 0;
    gState.customFrameH = 0;
    gState.customFrame565.clear();
    return true;
  }

  if (strcmp(widget, "custom_gif") == 0) {
    gState.widget = WidgetCustomGif;
    gState.title = data["name"] | "custom_gif";
    gState.author = "-";
    gState.progressMs = 0;
    gState.durationMs = 0;

    gState.hasCover = false;
    gState.coverScaled565.clear();

    if (data["frame"].is<JsonObjectConst>()) {
      gState.hasCustomFrame = decodeRgb565Frame(
        data["frame"].as<JsonObjectConst>(),
        gState.customFrame565,
        gState.customFrameW,
        gState.customFrameH
      );
    } else {
      gState.hasCustomFrame = false;
      gState.customFrameW = 0;
      gState.customFrameH = 0;
      gState.customFrame565.clear();
    }
    return true;
  }

  gState.widget = WidgetNone;
  gState.widgetName = "none";
  gState.hasCover = false;
  gState.coverScaled565.clear();
  gState.hasCustomFrame = false;
  gState.customFrameW = 0;
  gState.customFrameH = 0;
  gState.customFrame565.clear();
  return true;
}

void renderCurrentFrame(uint32_t nowMs) {
  if (!display) {
    return;
  }

  const bool apiStale = (lastSourceSuccessMs == 0) || ((nowMs - lastSourceSuccessMs) > API_STALE_TIMEOUT_MS);
  if (apiStale) {
    if (!renderLocalClockFallback()) {
      renderStatus("API OFF", "NTP sync...");
    }
    return;
  }

  if (gState.widget == WidgetSpotify) {
    renderMediaFrame(true, nowMs);
    return;
  }

  if (gState.widget == WidgetClock) {
    renderClockFrame();
    return;
  }

  if (gState.widget == WidgetCustomGif) {
    renderCustomGifFrame();
    return;
  }

  renderStatus("Sem widget", gState.widgetName.c_str());
}

void renderClockFrame() {
  display->clearScreen();

  display->setTextColor(display->color565(255, 255, 255));
  display->setCursor(3, 3);
  display->print(gState.timeText);

  display->setCursor(3, 21);
  display->print(gState.weekdayText);

  display->setCursor(34, 21);
  display->print(gState.dateText);
}

void renderCustomGifFrame() {
  if (!display) {
    return;
  }

  if (!gState.hasCustomFrame || gState.customFrameW == 0 || gState.customFrameH == 0) {
    renderStatus("GIF invalido", "sem frame");
    return;
  }

  const size_t expected = static_cast<size_t>(gState.customFrameW) * gState.customFrameH;
  if (gState.customFrame565.size() != expected) {
    renderStatus("GIF invalido", "frame corrompido");
    return;
  }

  display->clearScreen();

  for (uint16_t y = 0; y < PANEL_HEIGHT; y++) {
    const uint16_t srcY = static_cast<uint16_t>(
      (static_cast<uint32_t>(y) * gState.customFrameH) / PANEL_HEIGHT
    );

    for (uint16_t x = 0; x < PANEL_WIDTH; x++) {
      const uint16_t srcX = static_cast<uint16_t>(
        (static_cast<uint32_t>(x) * gState.customFrameW) / PANEL_WIDTH
      );

      const size_t srcIndex = static_cast<size_t>(srcY) * gState.customFrameW + srcX;
      if (srcIndex >= gState.customFrame565.size()) {
        continue;
      }

      display->drawPixel(x, y, gState.customFrame565[srcIndex]);
    }
  }
}

void maintainNtpClock(uint32_t nowMs) {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (!ntpConfigured) {
    configTzTime(TZ_INFO, NTP_SERVER_1, NTP_SERVER_2);
    ntpConfigured = true;
    lastNtpAttemptMs = nowMs;
    return;
  }

  const time_t epoch = time(nullptr);
  if (epoch > 1700000000) {
    ntpSynced = true;
  }

  if (!ntpSynced) {
    if (nowMs - lastNtpAttemptMs >= NTP_RETRY_INTERVAL_MS) {
      configTzTime(TZ_INFO, NTP_SERVER_1, NTP_SERVER_2);
      lastNtpAttemptMs = nowMs;
    }
    return;
  }

  if (nowMs - lastNtpResyncMs >= NTP_RESYNC_INTERVAL_MS) {
    configTzTime(TZ_INFO, NTP_SERVER_1, NTP_SERVER_2);
    lastNtpResyncMs = nowMs;
  }
}

bool getLocalClockStrings(String& timeOut, String& dateOut, String& weekdayOut) {
  const time_t epoch = time(nullptr);
  if (epoch <= 1700000000) {
    return false;
  }

  struct tm localTm;
  if (!localtime_r(&epoch, &localTm)) {
    return false;
  }

  char hhmm[6] = {0};
  char date[6] = {0};
  char weekday[8] = {0};

  if (strftime(hhmm, sizeof(hhmm), "%H:%M", &localTm) == 0) {
    return false;
  }
  if (strftime(date, sizeof(date), "%d/%m", &localTm) == 0) {
    return false;
  }
  if (strftime(weekday, sizeof(weekday), "%a", &localTm) == 0) {
    return false;
  }

  for (size_t i = 0; weekday[i] != '\0'; i++) {
    weekday[i] = static_cast<char>(toupper(static_cast<unsigned char>(weekday[i])));
  }

  timeOut = hhmm;
  dateOut = date;
  weekdayOut = weekday;
  return true;
}

bool renderLocalClockFallback() {
  String hhmm;
  String date;
  String weekday;
  if (!getLocalClockStrings(hhmm, date, weekday)) {
    return false;
  }

  display->clearScreen();
  display->setTextColor(display->color565(255, 255, 255));
  display->setCursor(3, 3);
  display->print(hhmm);

  display->setCursor(3, 21);
  display->print(weekday);

  display->setCursor(34, 21);
  display->print(date);

  // Indicador discreto de fallback local quando a API está indisponivel.
  display->setTextColor(display->color565(255, 120, 120));
  display->setCursor(52, 3);
  display->print("L");
  return true;
}

void renderMediaFrame(bool isSpotify, uint32_t nowMs) {
  const uint16_t white = display->color565(255, 255, 255);
  const uint16_t progressBase = display->color565(52, 52, 52);
  const uint16_t progressFill = display->color565(55, 226, 131);

  display->clearScreen();
  display->fillRect(TEXT_LEFT_X, 0, PANEL_WIDTH - TEXT_LEFT_X, PANEL_HEIGHT, display->color565(0, 0, 0));

  const int16_t textBaseX = TEXT_LEFT_X + 1;
  const int16_t visibleWidth = PANEL_WIDTH - textBaseX;

  drawMarqueeText(
    gState.title,
    textBaseX,
    TITLE_Y,
    visibleWidth,
    nowMs,
    TITLE_SCROLL_TICK_MS,
    3,
    gTitleMarqueeKey,
    gTitleStartedMs,
    white
  );

  drawMarqueeText(
    gState.author,
    textBaseX,
    AUTHOR_Y,
    visibleWidth,
    nowMs,
    AUTHOR_SCROLL_TICK_MS,
    3,
    gAuthorMarqueeKey,
    gAuthorStartedMs,
    white
  );

  if (isSpotify && gState.durationMs > 0) {
    const int16_t progressWidth = PANEL_WIDTH - TEXT_LEFT_X - 2;
    display->drawFastHLine(TEXT_LEFT_X, PROGRESS_Y, progressWidth, progressBase);

    const float ratio = static_cast<float>(gState.progressMs) / static_cast<float>(gState.durationMs);
    const float safeRatio = ratio < 0.0f ? 0.0f : (ratio > 1.0f ? 1.0f : ratio);
    const int16_t filled = static_cast<int16_t>(safeRatio * progressWidth);

    if (filled > 0) {
      display->drawFastHLine(TEXT_LEFT_X, PROGRESS_Y, filled, progressFill);
    }
  }

  if (gState.hasCover) {
    drawCoverScaled(0, (PANEL_HEIGHT - COVER_TARGET_SIZE) / 2);
  }
}

bool decodeAndScaleCover(const JsonObjectConst& cover, std::vector<uint16_t>& out) {
  const uint16_t w = cover["w"] | 0;
  const uint16_t h = cover["h"] | 0;
  const char* enc = cover["enc"] | "";
  const char* base64Data = cover["data"] | "";

  if (!base64Data || strcmp(enc, "rgb565_base64") != 0 || w == 0 || h == 0) {
    return false;
  }

  std::vector<uint8_t> raw;
  if (!decodeBase64(base64Data, raw)) {
    return false;
  }

  const size_t expected = static_cast<size_t>(w) * static_cast<size_t>(h) * 2;
  if (raw.size() != expected) {
    return false;
  }

  out.assign(static_cast<size_t>(COVER_TARGET_SIZE) * COVER_TARGET_SIZE, 0);

  for (uint16_t y = 0; y < COVER_TARGET_SIZE; y++) {
    const uint16_t srcY = static_cast<uint16_t>((static_cast<uint32_t>(y) * h) / COVER_TARGET_SIZE);
    for (uint16_t x = 0; x < COVER_TARGET_SIZE; x++) {
      const uint16_t srcX = static_cast<uint16_t>((static_cast<uint32_t>(x) * w) / COVER_TARGET_SIZE);
      const size_t srcIndex = (static_cast<size_t>(srcY) * w + srcX) * 2;
      if (srcIndex + 1 >= raw.size()) {
        return false;
      }

      const uint16_t color = (static_cast<uint16_t>(raw[srcIndex]) << 8) | raw[srcIndex + 1];
      out[static_cast<size_t>(y) * COVER_TARGET_SIZE + x] = color;
    }
  }

  return true;
}

bool decodeRgb565Frame(
  const JsonObjectConst& frame,
  std::vector<uint16_t>& out,
  uint16_t& outW,
  uint16_t& outH
) {
  const uint16_t w = frame["w"] | 0;
  const uint16_t h = frame["h"] | 0;
  const char* enc = frame["enc"] | "";
  const char* base64Data = frame["data"] | "";

  if (!base64Data || strcmp(enc, "rgb565_base64") != 0 || w == 0 || h == 0) {
    outW = 0;
    outH = 0;
    out.clear();
    return false;
  }

  std::vector<uint8_t> raw;
  if (!decodeBase64(base64Data, raw)) {
    outW = 0;
    outH = 0;
    out.clear();
    return false;
  }

  const size_t expected = static_cast<size_t>(w) * static_cast<size_t>(h) * 2;
  if (raw.size() != expected) {
    outW = 0;
    outH = 0;
    out.clear();
    return false;
  }

  out.assign(static_cast<size_t>(w) * h, 0);
  for (size_t pixel = 0; pixel < out.size(); pixel++) {
    const size_t srcIndex = pixel * 2;
    out[pixel] = (static_cast<uint16_t>(raw[srcIndex]) << 8) | raw[srcIndex + 1];
  }

  outW = w;
  outH = h;
  return true;
}

void drawCoverScaled(int16_t x0, int16_t y0) {
  if (!display || !gState.hasCover) {
    return;
  }

  const size_t expected = static_cast<size_t>(COVER_TARGET_SIZE) * COVER_TARGET_SIZE;
  if (gState.coverScaled565.size() != expected) {
    return;
  }

  for (uint16_t y = 0; y < COVER_TARGET_SIZE; y++) {
    for (uint16_t x = 0; x < COVER_TARGET_SIZE; x++) {
      const uint16_t color = gState.coverScaled565[static_cast<size_t>(y) * COVER_TARGET_SIZE + x];
      display->drawPixel(x0 + x, y0 + y, color);
    }
  }
}

uint16_t measureTextWidth(const String& text) {
  if (!display) {
    return 0;
  }

  int16_t x1 = 0;
  int16_t y1 = 0;
  uint16_t w = 0;
  uint16_t h = 0;
  display->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  return w;
}

void drawMarqueeText(
  const String& text,
  int16_t baseX,
  int16_t y,
  int16_t visibleWidth,
  uint32_t nowMs,
  uint32_t tickMs,
  uint8_t gapChars,
  String& stateKey,
  uint32_t& stateStartedMs,
  uint16_t color
) {
  if (!display) {
    return;
  }

  String content = text;
  content.trim();
  if (content.length() == 0) {
    content = "-";
  }

  const uint16_t textWidth = measureTextWidth(content);
  if (textWidth <= static_cast<uint16_t>(visibleWidth)) {
    display->setTextColor(color);
    display->setCursor(baseX, y);
    display->print(content);
    return;
  }

  if (stateKey != content || stateStartedMs == 0) {
    stateKey = content;
    stateStartedMs = nowMs;
  }

  uint16_t spaceWidth = measureTextWidth(" ");
  if (spaceWidth == 0) {
    spaceWidth = 6;
  }

  uint16_t gapPx = static_cast<uint16_t>(spaceWidth * gapChars);
  if (gapPx < 4) {
    gapPx = 4;
  }

  const uint32_t travel = static_cast<uint32_t>(textWidth) + gapPx;
  const uint32_t safeTick = tickMs < 10 ? 10 : tickMs;
  const uint32_t phase = ((nowMs - stateStartedMs) / safeTick) % travel;
  const int16_t x = static_cast<int16_t>(baseX - phase);

  display->setTextColor(color);
  display->setCursor(x, y);
  display->print(content);
  display->setCursor(static_cast<int16_t>(x + travel), y);
  display->print(content);
}

String compactArtistName(const String& artist) {
  String normalized = artist;
  normalized.trim();

  while (normalized.indexOf("  ") >= 0) {
    normalized.replace("  ", " ");
  }

  if (normalized.length() == 0) {
    return "-";
  }

  const int firstSpace = normalized.indexOf(' ');
  if (firstSpace < 0) {
    return normalized;
  }

  int secondStart = firstSpace + 1;
  while (secondStart < normalized.length() && normalized.charAt(secondStart) == ' ') {
    secondStart++;
  }

  if (secondStart >= normalized.length()) {
    return normalized.substring(0, firstSpace);
  }

  String result = normalized.substring(0, firstSpace);
  result += " ";
  result += normalized.charAt(secondStart);
  result += ".";
  return result;
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
