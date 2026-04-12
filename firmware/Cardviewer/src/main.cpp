#include <Arduino.h>

#include <ArduinoJson.h>

#include <GxEPD2_BW.h>

#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>

#include <JPEGDEC.h>

#include <WiFi.h>
#include <esp_task_wdt.h>

#include "HttpFetch.h"

#include "secrets.h"



#ifndef CARDVIEWER_SKIP_HTTP

#define CARDVIEWER_SKIP_HTTP 0

#endif



#ifndef CARDVIEWER_FETCH_INTERVAL_MS

#define CARDVIEWER_FETCH_INTERVAL_MS 30000

#endif



constexpr int PIN_EPD_CS = 5;

constexpr int PIN_EPD_DC = 17;

constexpr int PIN_EPD_RST = 16;

constexpr int PIN_EPD_BUSY = 4;



using Driver = GxEPD2_420_GDEY042T81;

GxEPD2_BW<Driver, Driver::HEIGHT> display(Driver(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));



static const int EPD_W = 400;

static const int EPD_H = 300;



static const int ART_X = 0;

static const int ART_Y = 0;

static const int ART_W = 232;

static const int ART_H = EPD_H;

// Left: art box. Right column: anchor x, then chain baselines downward (Adafruit GFX y = baseline).
static const int DATA_GAP = 4;

static const int DATA_X = ART_W + DATA_GAP;

static const int DATA_W = EPD_W - DATA_X;

static const int COL_X = DATA_X;

static const int COL_TEXT_W = DATA_W - 4;

static const int TITLE_BASELINE_FIRST = 22;

static const int TITLE_LINE_STEP = 20;

static const int TITLE_MAX_LINES = 3;

static const int BODY_LINE_STEP = 14;

static const int BLOCK_GAP = 6;

// Footer block for set/collector (two lines, higher on panel than single-line-at-bottom)
static const int FOOTER_BASELINE_0 = EPD_H - 46;

static const int FOOTER_LINE_STEP = 12;

static const int FOOTER_MAX_LINES = 2;

static const int FOOTER_Y_MAX = EPD_H - 2;

// Oracle/body text must finish above footer
static const int BODY_BASELINE_MAX = FOOTER_BASELINE_0 - BLOCK_GAP - 4;

static const int ART_ROW_BYTES = (ART_W + 7) / 8;



// Decode JPEG once into this plane; drawPagedFull runs many times per full refresh

static uint8_t gArtBits[ART_ROW_BYTES * ART_H];

static bool gArtDecoded = false;



static float gScale = 1.0f;

static int gOffX = 0;

static int gOffY = 0;



static void setArtPixelInPlane(int lx, int ly, bool black) {

  if ((unsigned)lx >= (unsigned)ART_W || (unsigned)ly >= (unsigned)ART_H) {

    return;

  }

  size_t i = (size_t)ly * ART_ROW_BYTES + (size_t)(lx >> 3);

  uint8_t m = (uint8_t)(1u << (7 - (lx & 7)));

  if (black) {

    gArtBits[i] |= m;

  } else {

    gArtBits[i] &= (uint8_t)~m;

  }

}



static int gYieldCtr = 0;



static int jpegDrawCallback(JPEGDRAW *pDraw) {

  uint16_t *pix = pDraw->pPixels;

  for (int row = 0; row < pDraw->iHeight; row++) {

    for (int col = 0; col < pDraw->iWidth; col++) {

      uint16_t c = pix[row * pDraw->iWidth + col];

      int r = ((c >> 11) & 0x1f) << 3;

      int g = ((c >> 5) & 0x3f) << 2;

      int b = (c & 0x1f) << 3;

      int ylum = (r * 299 + g * 587 + b * 114) / 1000;

      float ix = (float)(pDraw->x + col);

      float iy = (float)(pDraw->y + row);

      int dx = gOffX + (int)(ix * gScale + 0.5f);

      int dy = gOffY + (int)(iy * gScale + 0.5f);

      if (dx < ART_X || dy < ART_Y || dx >= ART_X + ART_W || dy >= ART_Y + ART_H) {

        continue;

      }

      int lx = dx - ART_X;

      int ly = dy - ART_Y;

      setArtPixelInPlane(lx, ly, ylum < 140);

    }

  }

  if (++gYieldCtr >= 4) {
    gYieldCtr = 0;
    esp_task_wdt_reset();
    yield();
  }

  return 1;

}



template <typename F> void drawPagedFull(F f) {

  display.setFullWindow();

  display.firstPage();

  do {

    f();

  } while (display.nextPage());

}



static bool decodeJpegToArtPlane(uint8_t *data, size_t len) {

  memset(gArtBits, 0, sizeof(gArtBits));

  JPEGDEC jpeg;

  if (jpeg.openRAM(data, (int)len, jpegDrawCallback) != 1) {

    return false;

  }

  jpeg.setPixelType(RGB565_BIG_ENDIAN);

  int iw = jpeg.getWidth();

  int ih = jpeg.getHeight();

  if (iw <= 0 || ih <= 0) {

    jpeg.close();

    return false;

  }

  float sx = (float)ART_W / (float)iw;

  float sy = (float)ART_H / (float)ih;

  gScale = (sx < sy) ? sx : sy;

  int dw = (int)((float)iw * gScale + 0.5f);

  int dh = (int)((float)ih * gScale + 0.5f);

  gOffX = ART_X + (ART_W - dw) / 2;

  gOffY = ART_Y + (ART_H - dh) / 2;

  gYieldCtr = 0;

  int dr = jpeg.decode(0, 0, 0);

  jpeg.close();

  return dr == 1;

}



// Blit static gArtBits — many drawPixel calls; must feed task WDT (yield() alone is not enough on ESP32 Arduino).
static void drawArtPlaneToDisplay() {
  for (int y = 0; y < ART_H; y++) {
    for (int x = 0; x < ART_W; x++) {
      size_t i = (size_t)y * ART_ROW_BYTES + (size_t)(x >> 3);
      if ((gArtBits[i] >> (7 - (x & 7))) & 1) {
        display.drawPixel(ART_X + x, ART_Y + y, GxEPD_BLACK);
      }
      if ((x & 63) == 0) {
        esp_task_wdt_reset();
      }
    }
    esp_task_wdt_reset();
    yield();
  }
}



// font: Adafruit GFX font; chain returns next baseline below this block
static int printWrappedColumn(int x, int y, const String &text, int maxW, int lineH, int maxLines, int yMax,
                              const GFXfont *font) {

  display.setFont(font);

  display.setTextColor(GxEPD_BLACK);

  String rest = text;

  int cy = y;

  int lines = 0;

  while (rest.length() > 0 && lines < maxLines && cy + lineH <= yMax) {

    String line = rest;

    int16_t x1, y1;

    uint16_t tw, th;

    for (int n = (int)rest.length(); n > 0; n--) {

      line = rest.substring(0, n);

      display.getTextBounds(line.c_str(), x, cy, &x1, &y1, &tw, &th);

      if ((int)tw <= maxW || n == 1) {

        break;

      }

    }

    int cut = line.length();

    if (cut < (int)rest.length() && rest.charAt(cut) != ' ') {

      int sp = line.lastIndexOf(' ');

      if (sp > 0) {

        cut = sp;

        line = rest.substring(0, cut);

      }

    }

    if (cut <= 0 && rest.length() > 0) {
      cut = 1;
    }
    if (cut > (int)rest.length()) {
      cut = (int)rest.length();
    }

    display.setCursor(x, cy);

    display.print(line.c_str());

    rest = rest.substring(cut);

    rest.trim();

    cy += lineH;

    lines++;

  }

  return cy;

}



static String truncateToWidth(const String &s, int maxW) {

  if (s.length() == 0) {

    return s;

  }

  int16_t x1, y1;

  uint16_t tw, th;

  display.getTextBounds(s.c_str(), 0, 0, &x1, &y1, &tw, &th);

  if ((int)tw <= maxW) {

    return s;

  }

  for (int n = (int)s.length() - 1; n >= 1; n--) {

    String t = s.substring(0, n);

    t += "…";

    display.getTextBounds(t.c_str(), 0, 0, &x1, &y1, &tw, &th);

    if ((int)tw <= maxW) {

      return t;

    }

  }

  return "…";

}



void drawCardScreen(const String &json, uint8_t *imgData, size_t imgLen) {

  gArtDecoded = false;

  if (imgData && imgLen > 0) {
    gArtDecoded = decodeJpegToArtPlane(imgData, imgLen);
    free(imgData);
  }

  JsonDocument doc;

  DeserializationError err = deserializeJson(doc, json);

  if (err) {

    drawPagedFull([&] {

      display.fillScreen(GxEPD_WHITE);

      display.setFont(&FreeSans9pt7b);

      display.setTextColor(GxEPD_BLACK);

      display.setCursor(12, 40);

      display.print("JSON error");

    });

    return;

  }



  JsonObject panel = doc["panel"];

  String name = panel["name"].is<const char *>() ? String(panel["name"].as<const char *>()) : String("");

  String typeLine =

      panel["type_line"].is<const char *>() ? String(panel["type_line"].as<const char *>()) : String("");

  String oracle =

      panel["oracle_text"].is<const char *>() ? String(panel["oracle_text"].as<const char *>()) : String("");

  String pt = "";

  if (panel["power"].is<const char *>()) {

    pt = String(panel["power"].as<const char *>());

    pt += " / ";

    pt += panel["toughness"].is<const char *>() ? panel["toughness"].as<const char *>() : "?";

  }



  String setLine = "";

  if (panel["set_code"].is<const char *>()) {

    setLine = panel["set_code"].as<const char *>();

    if (panel["collector_number"].is<const char *>()) {

      setLine += " #";

      setLine += panel["collector_number"].as<const char *>();

    }

    if (panel["set_name"].is<const char *>()) {

      setLine += " · ";

      setLine += panel["set_name"].as<const char *>();

    }

  }



  String manaLine = "";

  if (panel["mana_symbols"].is<JsonArray>()) {

    JsonArray syms = panel["mana_symbols"].as<JsonArray>();

    for (size_t i = 0; i < syms.size(); i++) {

      JsonVariant v = syms[i];

      if (v.is<const char *>()) {

        manaLine += v.as<const char *>();

      }

    }

  }



  drawPagedFull([&] {

    display.fillScreen(GxEPD_WHITE);

    display.drawRect(ART_X, ART_Y, ART_W, ART_H, GxEPD_BLACK);



    if (gArtDecoded) {

      drawArtPlaneToDisplay();

    } else {

      display.setFont(&FreeSans9pt7b);

      display.setTextColor(GxEPD_BLACK);

      display.setCursor(ART_X + 8, ART_Y + ART_H / 2);

      display.print("No art");

    }



    int y = TITLE_BASELINE_FIRST;

    display.setTextColor(GxEPD_BLACK);



    y = printWrappedColumn(COL_X, y, name.length() ? name : String("?"), COL_TEXT_W, TITLE_LINE_STEP,

                           TITLE_MAX_LINES, BODY_BASELINE_MAX, &FreeSansBold12pt7b);

    y += BLOCK_GAP;



    display.setFont(&FreeSans9pt7b);

    if (manaLine.length() > 0) {

      String ml = truncateToWidth(manaLine, COL_TEXT_W);

      display.setCursor(COL_X, y);

      display.print(ml.c_str());

      y += BODY_LINE_STEP + BLOCK_GAP;

    }



    y = printWrappedColumn(COL_X, y, typeLine, COL_TEXT_W, BODY_LINE_STEP, 2, BODY_BASELINE_MAX,

                           &FreeSans9pt7b);

    y += BLOCK_GAP;



    if (pt.length() > 4) {

      display.setCursor(COL_X, y);

      display.print(pt.c_str());

      y += BODY_LINE_STEP + BLOCK_GAP;

    }



    if (oracle.length() > 0 && y < BODY_BASELINE_MAX - BODY_LINE_STEP) {

      int oracleMaxLines = (BODY_BASELINE_MAX - y) / BODY_LINE_STEP;

      if (oracleMaxLines > 10) {

        oracleMaxLines = 10;

      }

      printWrappedColumn(COL_X, y, oracle, COL_TEXT_W, BODY_LINE_STEP, oracleMaxLines, BODY_BASELINE_MAX,

                         &FreeSans9pt7b);

    }



    if (setLine.length() > 0) {

      printWrappedColumn(COL_X, FOOTER_BASELINE_0, setLine, COL_TEXT_W, FOOTER_LINE_STEP, FOOTER_MAX_LINES,

                         FOOTER_Y_MAX, &FreeSans9pt7b);

    }

  });

}



// Compact ``image`` mirrors Scryfall ``image_uris`` keys. Prefer full frame for the panel JPEG.
static const char *pickCardImageUrl(JsonVariant imgNode) {
  if (!imgNode.is<JsonObject>()) {
    return nullptr;
  }
  JsonObject img = imgNode.as<JsonObject>();
  static const char *const keys[] = {"normal", "png", "small", "large", "art_crop", "border_crop"};
  for (const char *k : keys) {
    const char *u = img[k].as<const char *>();
    if (u && u[0]) {
      return u;
    }
  }
  return nullptr;
}

static void fetchAndDrawCard() {

#if CARDVIEWER_SKIP_HTTP

  drawPagedFull([&] {

    display.fillScreen(GxEPD_WHITE);

    display.setFont(&FreeSans9pt7b);

    display.setCursor(12, 40);

    display.print("CARDVIEWER_SKIP_HTTP");

  });

  return;

#endif



  String base = String(COMPANION_API_BASE);

  if (base.endsWith("/")) {

    base.remove(base.length() - 1);

  }

  String url = base + "/scryfall/cards/random?format=compact";



  String json = httpGetString(url);

  uint8_t *imgBuf = nullptr;

  size_t imgLen = 0;



  if (json.length() > 0) {

    JsonDocument doc;

    DeserializationError je = deserializeJson(doc, json);

    if (!je) {

      const char *imgUrl = pickCardImageUrl(doc["image"]);

      if (imgUrl && strlen(imgUrl) > 0) {

        httpGetBinary(String(imgUrl), &imgBuf, &imgLen);

      }

    }

  }



  if (json.length() == 0) {

    drawPagedFull([&] {

      display.fillScreen(GxEPD_WHITE);

      display.setFont(&FreeSans9pt7b);

      display.setTextColor(GxEPD_BLACK);

      display.setCursor(12, 36);

      display.print("Fetch failed");

      display.setCursor(12, 56);

      display.print("Check API / network");

    });

  } else {

    drawCardScreen(json, imgBuf, imgLen);
  }
}



void setup() {

  Serial.begin(115200);

  delay(100);



  display.init(115200);

  display.setRotation(0);

  display.setTextWrap(false);



  if (strlen(WIFI_SSID) == 0 || strcmp(WIFI_SSID, "your-ssid") == 0) {

    drawPagedFull([&] {

      display.fillScreen(GxEPD_WHITE);

      display.setFont(&FreeSans9pt7b);

      display.setCursor(12, 40);

      display.print("Edit secrets.h WiFi");

    });

    return;

  }



  WiFi.mode(WIFI_STA);

  WiFi.begin(WIFI_SSID, WIFI_PASS);



  const unsigned long wifiTimeoutMs = 45000;

  unsigned long wifiStart = millis();

  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < wifiTimeoutMs) {

    delay(200);

    yield();

  }



  if (WiFi.status() != WL_CONNECTED) {

    drawPagedFull([&] {

      display.fillScreen(GxEPD_WHITE);

      display.setFont(&FreeSans9pt7b);

      display.setCursor(12, 40);

      display.print("WiFi failed");

    });

    return;

  }



  fetchAndDrawCard();

}



void loop() {

  delay(CARDVIEWER_FETCH_INTERVAL_MS);

  if (WiFi.status() == WL_CONNECTED) {

    fetchAndDrawCard();

  } else {

    WiFi.reconnect();

    unsigned long t = millis();

    while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) {

      delay(200);

      yield();

    }

    if (WiFi.status() == WL_CONNECTED) {

      fetchAndDrawCard();

    }

  }

}


