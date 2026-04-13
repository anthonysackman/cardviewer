#include <Arduino.h>

#include <ctype.h>
#include <limits.h>

#include <ArduinoJson.h>

#include <GxEPD2_BW.h>

#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSerifBold12pt7b.h>

#include <JPEGDEC.h>

#include <WiFi.h>
#include <esp_task_wdt.h>
#include <pgmspace.h>

#include "HttpFetch.h"

#include "ManaSprites.h"

#include "secrets.h"



#ifndef CARDVIEWER_SKIP_HTTP

#define CARDVIEWER_SKIP_HTTP 0

#endif



#ifndef CARDVIEWER_FETCH_INTERVAL_MS

#define CARDVIEWER_FETCH_INTERVAL_MS 60000

#endif



// Set to 0 to disable [cv]/[card]/[epd] trace lines (heap + milestones). Unknown mana still logs once per card (page 0).

#ifndef CARDVIEWER_DEBUG_TRACE

#define CARDVIEWER_DEBUG_TRACE 1

#endif



#if CARDVIEWER_DEBUG_TRACE

template <typename... Args>
static inline void cv_log(const char *fmt, Args... args) {
  Serial.printf(fmt, args...);
  Serial.flush();
}

#define CV_LOG(...) cv_log(__VA_ARGS__)

static inline void cv_trace(const char *tag) {
  Serial.printf("[cv] %s heap=%u\n", tag, (unsigned)ESP.getFreeHeap());
  Serial.flush();
}

#else

#define CV_LOG(...) ((void)0)

static inline void cv_trace(const char *) {}

#endif



static volatile int g_epdPageIndex = 0;

#define MAX_MANA_TOK 24

// Keep mana token strings off the drawCardScreen stack (default loop stack is 8KB; large String[] frames overflow).
static String g_manaTok[MAX_MANA_TOK];
static String g_manaGen[MAX_MANA_TOK];
static String g_manaCol[MAX_MANA_TOK];

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
static const int ORACLE_LINE_STEP = 12;

static const int BLOCK_GAP = 6;

// Tighter gap title -> mana row; extra gap after mana before type line (set in drawManaCostRow).
static const int TITLE_TO_MANA_GAP = 2;

// Footer block pinned to panel bottom.
static const int FOOTER_SET_BASELINE = EPD_H - 14;
static const int FOOTER_META_BASELINE = FOOTER_SET_BASELINE - 12;

static const int FOOTER_LINE_STEP = 12;

static const int FOOTER_MAX_LINES = 1;

static const int FOOTER_Y_MAX = EPD_H - 2;

// Oracle/body text must finish above footer
static const int BODY_BASELINE_MAX = FOOTER_META_BASELINE - BLOCK_GAP - 2;

static const int ART_ROW_BYTES = (ART_W + 7) / 8;



// Decode JPEG once into this plane; drawPagedFull runs many times per full refresh

static uint8_t gArtBits[ART_ROW_BYTES * ART_H];

static bool gArtDecoded = false;

// JPEGDEC embeds a large JPEGIMAGE (~22KB). Placing it on the loop stack overflows
// CONFIG_ARDUINO_LOOP_STACK_SIZE (16KB) and crashes (often LoadProhibited at 0x0).
static JPEGDEC g_jpegDecoder;



static float gScale = 1.0f;

static int gOffX = 0;

static int gOffY = 0;

static int gCbMaxX = 0;

static int gCbMaxY = 0;

static const int ART_LUMA_THRESHOLD = 118;



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

  if (!pDraw || !pDraw->pPixels) {

    return 0;

  }

  uint16_t *pix = pDraw->pPixels;

  int blockMaxX = pDraw->x + pDraw->iWidth;
  int blockMaxY = pDraw->y + pDraw->iHeight;
  if (blockMaxX > gCbMaxX) {
    gCbMaxX = blockMaxX;
  }
  if (blockMaxY > gCbMaxY) {
    gCbMaxY = blockMaxY;
  }

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

      setArtPixelInPlane(lx, ly, ylum < ART_LUMA_THRESHOLD);

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

  int page = 0;

  do {

    g_epdPageIndex = page;

#if CARDVIEWER_DEBUG_TRACE

    CV_LOG("[epd] page %d heap=%u\n", page, (unsigned)ESP.getFreeHeap());

#endif

    f();

    page++;

  } while (display.nextPage());

}



static const char *jpegDecErrorName(int e) {
  switch (e) {
    case JPEG_SUCCESS:
      return "SUCCESS";
    case JPEG_INVALID_PARAMETER:
      return "INVALID_PARAMETER";
    case JPEG_DECODE_ERROR:
      return "DECODE_ERROR";
    case JPEG_UNSUPPORTED_FEATURE:
      return "UNSUPPORTED_FEATURE";
    case JPEG_INVALID_FILE:
      return "INVALID_FILE";
    case JPEG_ERROR_MEMORY:
      return "ERROR_MEMORY";
    default:
      return "?";
  }
}

// JPEGDEC DecodeJPEG() ORs JPEG_SCALE_EIGHTH only for SOF2 (progressive) images; callbacks
// then use coordinates in (width/8)x(height/8) space. getJPEGType() usually matches, but the
// static JPEGDEC instance can disagree with the current buffer; misclassifying baseline as
// progressive applies 8x gScale to full-res coords -> sparse dot pattern. Misclassifying
// progressive as baseline clips most pixels -> empty box. SOF in the buffer is authoritative.
static bool jpegIsProgressiveSOF2(const uint8_t *d, size_t len) {
  if (len < 4 || d[0] != 0xff || d[1] != 0xd8) {
    return false;
  }
  size_t i = 2;
  while (i + 3 < len && i < 4096) {
    if (d[i] != 0xff) {
      i++;
      continue;
    }
    i++;
    while (i < len && d[i] == 0xff) {
      i++;
    }
    if (i >= len) {
      break;
    }
    uint8_t m = d[i++];
    if (m == 0xd8 || m == 0xd9) {
      continue;
    }
    if (m >= 0xd0 && m <= 0xd7) {
      continue;
    }
    if (i + 1 >= len) {
      break;
    }
    uint16_t segLen = (uint16_t)((d[i] << 8) | d[i + 1]);
    if (segLen < 2) {
      return false;
    }
    if (m == 0xc2) {
      return true;
    }
    if (m == 0xc0 || m == 0xc1) {
      return false;
    }
    if (m == 0xda) {
      // Start Of Scan — entropy data follows; SOF must appear before this. If we get here
      // without returning from SOF, do not scan further (avoids false FF C2 in bitstream).
      return false;
    }
    i += segLen;
  }
  return false;
}

static unsigned artPlaneBlackPixelCount() {
  unsigned n = 0;
  size_t nb = (size_t)ART_ROW_BYTES * ART_H;
  for (size_t i = 0; i < nb; i++) {
    n += (unsigned)__builtin_popcount((unsigned)gArtBits[i]);
  }
  return n;
}

// Returns true if decode succeeded (dr==1). Fills gArtBits on success.
static bool decodeJpegToArtPlaneAttempt(uint8_t *data, size_t len, int progressiveMul, int pixelType, int *outIw,
                                        int *outIh, int *outObsW, int *outObsH) {

  memset(gArtBits, 0, sizeof(gArtBits));

  JPEGDEC &jpeg = g_jpegDecoder;

  if (jpeg.openRAM(data, (int)len, jpegDrawCallback) != 1) {

    unsigned b0 = (len >= 1 && data) ? data[0] : 0;

    unsigned b1 = (len >= 2 && data) ? data[1] : 0;

    unsigned b2 = (len >= 3 && data) ? data[2] : 0;

    unsigned b3 = (len >= 4 && data) ? data[3] : 0;

    CV_LOG("[art] openRAM failed len=%u err=%d %s magic=%02X%02X%02X%02X (JPEG FF D8 FF; PNG 89 50 4E 47)\n",

           (unsigned)len, jpeg.getLastError(), jpegDecErrorName(jpeg.getLastError()), b0, b1, b2, b3);

    return false;

  }

  jpeg.setPixelType(pixelType);

  int iw = jpeg.getWidth();

  int ih = jpeg.getHeight();

  if (iw <= 0 || ih <= 0) {

    CV_LOG("[art] bad dimensions iw=%d ih=%d\n", iw, ih);

    jpeg.close();

    return false;

  }

  float sx = (float)ART_W / (float)iw;

  float sy = (float)ART_H / (float)ih;

  float baseScale = (sx < sy) ? sx : sy;

  gScale = baseScale * (float)progressiveMul;

  int dw = (int)((float)iw * baseScale + 0.5f);

  int dh = (int)((float)ih * baseScale + 0.5f);

  gOffX = ART_X + (ART_W - dw) / 2;

  gOffY = ART_Y + (ART_H - dh) / 2;

  gYieldCtr = 0;
  gCbMaxX = 0;
  gCbMaxY = 0;

  int dr = jpeg.decode(0, 0, 0);

  if (dr != 1) {

    CV_LOG("[art] decode returned %d err=%d %s (expect 1)\n", dr, jpeg.getLastError(),

           jpegDecErrorName(jpeg.getLastError()));

  }

  jpeg.close();

  if (outIw) {
    *outIw = iw;
  }
  if (outIh) {
    *outIh = ih;
  }
  if (outObsW) {
    *outObsW = gCbMaxX;
  }
  if (outObsH) {
    *outObsH = gCbMaxY;
  }

  return dr == 1;

}

static bool decodeJpegToArtPlane(uint8_t *data, size_t len) {

  // Try both scale multipliers and both RGB565 endianness values, then choose using
  // callback geometry (observed block coords) + ink coverage. Runtime geometry is more
  // reliable than static SOF probing across diverse JPEG metadata layouts.
  const int mulA = 1;
  const int mulB = 8;
  const int ptBe = RGB565_BIG_ENDIAN;
  const int ptLe = RGB565_LITTLE_ENDIAN;
  const unsigned minBlack = 300u;
  const int minCovPct = 30;
  const int minWFrac = ART_W / 3;
  const int minHFrac = ART_H / 3;

  struct {
    int mul;
    int pt;
    unsigned black;
    int obsW;
    int obsH;
    int iw;
    int ih;
    int covPct;
    bool mulMatch;
    long score;
  } best = {mulA, ptBe, 0u, 0, 0, 0, 0, 0, false, LONG_MIN};

  bool anyDecodeOk = false;

  const int orderMul[] = {mulA, mulB, mulA, mulB};
  const int orderPt[] = {ptBe, ptBe, ptLe, ptLe};

  for (int attempt = 0; attempt < 4; attempt++) {
    int mul = orderMul[attempt];
    int pt = orderPt[attempt];
    int iw = 0;
    int ih = 0;
    int obsW = 0;
    int obsH = 0;
    if (!decodeJpegToArtPlaneAttempt(data, len, mul, pt, &iw, &ih, &obsW, &obsH)) {
      continue;
    }
    anyDecodeOk = true;
    unsigned n = artPlaneBlackPixelCount();
    int covPct = (int)((100ull * n) / (unsigned long long)(ART_W * ART_H));
    int inferredMul = 1;
    if (obsW > 0 && obsH > 0 && iw > 0 && ih > 0) {
      float rw = (float)iw / (float)obsW;
      float rh = (float)ih / (float)obsH;
      float ravg = (rw + rh) * 0.5f;
      inferredMul = (ravg > 3.0f) ? 8 : 1;
    }
    bool mulMatch = (mul == inferredMul);
    bool coverageOk = covPct >= minCovPct && n >= minBlack && obsW >= minWFrac && obsH >= minHFrac;
    long score = (long)n + (long)covPct * 20L + (mulMatch ? 200000L : 0L) + (coverageOk ? 50000L : 0L);

    CV_LOG("[art] attempt mul=%d inferred=%d %s black=%u cov=%d%% obs=%dx%d src=%dx%d score=%ld\n", mul,
           inferredMul, (pt == ptBe) ? "RGB565_BE" : "RGB565_LE", n, covPct, obsW, obsH, iw, ih, score);

    if (score > best.score) {
      best.mul = mul;
      best.pt = pt;
      best.black = n;
      best.obsW = obsW;
      best.obsH = obsH;
      best.iw = iw;
      best.ih = ih;
      best.covPct = covPct;
      best.mulMatch = mulMatch;
      best.score = score;
    }
  }

  if (best.score > LONG_MIN) {
    CV_LOG("[art] selected mul=%d %s black=%u cov=%d%% obs=%dx%d src=%dx%d mul_match=%d\n", best.mul,
           (best.pt == ptBe) ? "RGB565_BE" : "RGB565_LE", best.black, best.covPct, best.obsW, best.obsH,
           best.iw, best.ih, best.mulMatch ? 1 : 0);
    return decodeJpegToArtPlaneAttempt(data, len, best.mul, best.pt, nullptr, nullptr, nullptr, nullptr);
  }

  if (anyDecodeOk) {
    CV_LOG("[art] decode had no selectable best attempt\n");
    return false;
  }

  return false;

}



// Blit static gArtBits — many drawPixel calls; must feed task WDT (yield() alone is not enough on ESP32 Arduino).
static bool loadRawArtPlane(const uint8_t *data, size_t len) {
  size_t need = sizeof(gArtBits);
  if (!data || len != need) {
    CV_LOG("[art] raw plane size mismatch got=%u need=%u\n", (unsigned)len, (unsigned)need);
    return false;
  }
  memcpy(gArtBits, data, need);
  CV_LOG("[art] raw plane load ok bytes=%u\n", (unsigned)len);
  return true;
}

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

  display.setTextSize(1);
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



static String manaInnerFromToken(const char *tok) {

  if (!tok || tok[0] != '{') {

    return String();

  }

  const char *end = strchr(tok + 1, '}');

  if (!end) {

    return String();

  }

  String s;

  for (const char *p = tok + 1; p < end; ++p) {

    s += *p;

  }

  return s;

}



static bool manaAllDigits(const String &s) {

  if (s.length() == 0) {

    return false;

  }

  for (unsigned i = 0; i < s.length(); i++) {

    if (!isdigit((unsigned char)s[i])) {

      return false;

    }

  }

  return true;

}



// Generic/numeric mana first, then colored / hybrid (Scryfall order within each group).

static bool manaIsGenericInner(const String &inner) {

  if (inner.length() == 0 || inner.indexOf('/') >= 0) {

    return false;

  }

  if (manaAllDigits(inner)) {

    return true;

  }

  if (inner.length() == 1) {

    char c = (char)toupper((unsigned char)inner[0]);

    if (c == 'X' || c == 'Y' || c == 'Z') {

      return true;

    }

  }

  return false;

}



static uint8_t g_manaBlitRam[MANA_BMP_BYTES];

static void blitMana(const uint8_t *bmp, int x, int y) {

  memcpy_P(g_manaBlitRam, bmp, MANA_BMP_BYTES);

  display.drawBitmap(x, y, g_manaBlitRam, MANA_BMP_W, MANA_BMP_H, GxEPD_BLACK);

}



// Scryfall cost letters -> terrain sprites: W Plains(P), U Island(I), B Swamp(S), R Mountain(M), G Forest(F), C.

static const uint8_t *manaDispSpriteForScryfallLetter(char c) {

  switch ((char)toupper((unsigned char)c)) {

  case 'W':

    return MANA_DISP_P;

  case 'U':

    return MANA_DISP_I;

  case 'B':

    return MANA_DISP_S;

  case 'R':

    return MANA_DISP_M;

  case 'G':

    return MANA_DISP_F;

  case 'C':

    return MANA_DISP_C;

  default:

    return nullptr;

  }

}



static const uint8_t *manaGenSprite(int n) {

  switch (n) {

  case 0:

    return MANA_SPRITE_GEN_0;

  case 1:

    return MANA_SPRITE_GEN_1;

  case 2:

    return MANA_SPRITE_GEN_2;

  case 3:

    return MANA_SPRITE_GEN_3;

  case 4:

    return MANA_SPRITE_GEN_4;

  case 5:

    return MANA_SPRITE_GEN_5;

  case 6:

    return MANA_SPRITE_GEN_6;

  case 7:

    return MANA_SPRITE_GEN_7;

  case 8:

    return MANA_SPRITE_GEN_8;

  case 9:

    return MANA_SPRITE_GEN_9;

  case 10:

    return MANA_SPRITE_GEN_10;

  case 11:

    return MANA_SPRITE_GEN_11;

  case 12:

    return MANA_SPRITE_GEN_12;

  case 13:

    return MANA_SPRITE_GEN_13;

  case 14:

    return MANA_SPRITE_GEN_14;

  case 15:

    return MANA_SPRITE_GEN_15;

  case 16:

    return MANA_SPRITE_GEN_16;

  case 17:

    return MANA_SPRITE_GEN_17;

  case 18:

    return MANA_SPRITE_GEN_18;

  case 19:

    return MANA_SPRITE_GEN_19;

  case 20:

    return MANA_SPRITE_GEN_20;

  default:

    return nullptr;

  }

}



static void drawTextCenteredInPip(int cx, int cy, const String &s, uint8_t textSize = 1) {

  display.setFont(nullptr);

  display.setTextSize(textSize);

  display.setTextColor(GxEPD_BLACK);

  int16_t x1, y1;

  uint16_t tw, th;

  display.getTextBounds(s.c_str(), 0, 0, &x1, &y1, &tw, &th);

  int tx = cx - (int)tw / 2 - (int)x1;

  int ty = cy - (int)th / 2 - (int)y1;

  display.setCursor(tx, ty);

  display.print(s.c_str());
  display.setTextSize(1);

}



// Map hybrid halves to terrain letters (S snow -> W glyph for display).

static String manaHybridDisplayPart(const String &part) {

  if (part.length() != 1) {

    return part;

  }

  char c = (char)toupper((unsigned char)part[0]);

  switch (c) {

  case 'W':

    return "P";

  case 'U':

    return "I";

  case 'B':

    return "S";

  case 'R':

    return "M";

  case 'G':

    return "F";

  case 'C':

    return "C";

  case 'S':

    return "W";

  default:

    return part;

  }

}



static void drawManaHybridPip(int x, int y, const String &left, const String &right) {

  int cx = x + MANA_BMP_W / 2;

  int cy = y + MANA_BMP_H / 2;

  int r = MANA_BMP_W / 2;

  display.fillCircle(cx, cy, r - 1, GxEPD_WHITE);

  display.drawCircle(cx, cy, r, GxEPD_BLACK);

  display.drawLine(cx, cy - r, cx, cy + r, GxEPD_BLACK);

  drawTextCenteredInPip(cx - r / 2, cy, manaHybridDisplayPart(left), 2);

  drawTextCenteredInPip(cx + r / 2, cy, manaHybridDisplayPart(right), 2);

}



// Returns true if a pip was drawn (known symbol).

static bool drawOneManaPip(int x, int y, const String &full) {

  String inner = manaInnerFromToken(full.c_str());

  if (inner.length() == 0) {

    return false;

  }

  if (inner.indexOf('/') >= 0) {

    int slash = inner.indexOf('/');

    String right = inner.substring(slash + 1);

    if (right.indexOf('/') >= 0) {

      return false;

    }

    String left = inner.substring(0, slash);

    left.trim();

    right.trim();

    if (left.length() == 0 || right.length() == 0) {

      return false;

    }

    drawManaHybridPip(x, y, left, right);

    return true;

  }

  if (inner.length() == 1) {

    char c = (char)toupper((unsigned char)inner[0]);

    if (c == 'X') {

      blitMana(MANA_SPRITE_GEN_X, x, y);

      return true;

    }

    if (c == 'Y' || c == 'Z') {

      return false;

    }

    if (c == 'S') {

      blitMana(MANA_DISP_SNOW, x, y);

      return true;

    }

    const uint8_t *pip = manaDispSpriteForScryfallLetter(c);

    if (pip) {

      blitMana(pip, x, y);

      return true;

    }

  }

  if (manaAllDigits(inner)) {

    int n = inner.toInt();

    const uint8_t *g = manaGenSprite(n);

    if (g) {

      blitMana(g, x, y);

      return true;

    }

  }

  return false;

}



// Generics left, colored/hybrid right; unknown symbols logged and concatenated for raw fallback line.

static int drawManaCostRow(int colX, int yBaseline, const String *tok, int n, int nGeneric) {

  if (n <= 0) {

    return yBaseline;

  }

#if CARDVIEWER_DEBUG_TRACE

  if (g_epdPageIndex == 0) {

    CV_LOG("[mana] cost row n=%d nGeneric=%d heap=%u\n", n, nGeneric, (unsigned)ESP.getFreeHeap());

  }

#endif

  const int pipGap = 3;

  const int groupGap = 4;

  const int pipStep = MANA_BMP_W + pipGap;

  int maxPips = (COL_TEXT_W + pipGap) / pipStep;

  if (maxPips < 1) {

    maxPips = 1;

  }

  const int MANA_PIP_LIFT = 16;

  int yTop = yBaseline - MANA_PIP_LIFT;

  int cx = colX;

  String unknownRaw;

  int drawn = 0;

  for (int i = 0; i < n; i++) {

    if (drawn >= maxPips) {

      unknownRaw += tok[i];

      continue;

    }

    if (i == nGeneric && nGeneric > 0) {

      cx += groupGap;

    }

    if (drawOneManaPip(cx, yTop, tok[i])) {

      cx += pipStep;

      drawn++;

    } else {

      if (g_epdPageIndex == 0) {

        Serial.printf("[mana] unknown symbol: %s\n", tok[i].c_str());

        Serial.flush();

      }

      unknownRaw += tok[i];

    }

  }

  const int MANA_GAP_AFTER_ROW = BLOCK_GAP + 8;

  int yNext = yBaseline;

  if (drawn > 0) {

    yNext = yTop + MANA_BMP_H + MANA_GAP_AFTER_ROW;

  }

  if (unknownRaw.length() > 0) {

    display.setFont(&FreeSans9pt7b);

    display.setTextColor(GxEPD_BLACK);

    String show = truncateToWidth(unknownRaw, COL_TEXT_W);

    int yRaw = (drawn > 0) ? yNext : yBaseline;

    display.setCursor(colX, yRaw);

    display.print(show.c_str());

    yNext = yRaw + BODY_LINE_STEP + BLOCK_GAP;

  }

  if (drawn == 0 && unknownRaw.length() == 0) {

    return yBaseline;

  }

  return yNext;

}



void drawCardScreen(const String &json, uint8_t *imgData, size_t imgLen, const String &imgKey) {

  CV_LOG("[card] enter img=%p len=%u json_len=%u heap=%u\n", imgData, (unsigned)imgLen, (unsigned)json.length(),

         (unsigned)ESP.getFreeHeap());

  gArtDecoded = false;

  if (imgData && imgLen > 0) {
    if (imgKey == "display_bw_raw") {
      gArtDecoded = loadRawArtPlane(imgData, imgLen);
      if (!gArtDecoded) {
        CV_LOG("[art] raw load failed, trying jpeg decode fallback\n");
        gArtDecoded = decodeJpegToArtPlane(imgData, imgLen);
      }
    } else {
      gArtDecoded = decodeJpegToArtPlane(imgData, imgLen);
    }
    free(imgData);
  } else {

    CV_LOG("[card] skip art decode (no buffer or len=0)\n");

  }

  CV_LOG("[card] after art decode decoded=%d heap=%u\n", gArtDecoded ? 1 : 0, (unsigned)ESP.getFreeHeap());

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

  cv_trace("json parsed");

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

  if (panel["set_name"].is<const char *>()) {

    setLine = String(panel["set_name"].as<const char *>());

  }

  String releaseYear = "";
  if (panel["released_at"].is<const char *>()) {
    String released = String(panel["released_at"].as<const char *>());
    if (released.length() >= 4) {
      releaseYear = released.substring(0, 4);
    }
  }

  String priceUsd = "";
  if (panel["price_usd"].is<const char *>()) {
    priceUsd = String(panel["price_usd"].as<const char *>());
  }

  String footerMeta = "";
  if (priceUsd.length() > 0) {
    footerMeta = "$";
    footerMeta += priceUsd;
  }
  if (releaseYear.length() > 0) {
    if (footerMeta.length() > 0) {
      footerMeta += " • ";
    }
    footerMeta += releaseYear;
  }

  int nMana = 0;

  int nManaGeneric = 0;

  {

    int ng = 0;

    int nc = 0;

    if (panel["mana_symbols"].is<JsonArray>()) {

      JsonArray syms = panel["mana_symbols"].as<JsonArray>();

      for (size_t i = 0; i < syms.size(); i++) {

        JsonVariant v = syms[i];

        if (!v.is<const char *>()) {

          continue;

        }

        String t = String(v.as<const char *>());

        String inner = manaInnerFromToken(t.c_str());

        if (inner.length() == 0) {

          continue;

        }

        if (manaIsGenericInner(inner)) {

          if (ng < MAX_MANA_TOK) {

            g_manaGen[ng++] = t;

          }

        } else {

          if (nc < MAX_MANA_TOK) {

            g_manaCol[nc++] = t;

          }

        }

      }

    }

    for (int i = 0; i < ng; i++) {

      g_manaTok[nMana++] = g_manaGen[i];

    }

    nManaGeneric = nMana;

    for (int i = 0; i < nc; i++) {

      g_manaTok[nMana++] = g_manaCol[i];

    }

  }

  CV_LOG("[card] before paged draw nMana=%d nManaGeneric=%d heap=%u\n", nMana, nManaGeneric,

         (unsigned)ESP.getFreeHeap());

  drawPagedFull([&] {

    display.setTextSize(1);
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

                           TITLE_MAX_LINES, BODY_BASELINE_MAX, &FreeSerifBold12pt7b);

    y += TITLE_TO_MANA_GAP;



    display.setFont(&FreeSans9pt7b);

    if (nMana > 0) {

      y = drawManaCostRow(COL_X, y, g_manaTok, nMana, nManaGeneric);

    }



    y = printWrappedColumn(COL_X, y, typeLine, COL_TEXT_W, BODY_LINE_STEP, 2, BODY_BASELINE_MAX,

                           &FreeSans9pt7b);

    y += BLOCK_GAP;



    if (pt.length() > 4) {

      display.setCursor(COL_X, y);

      display.print(pt.c_str());

      y += BODY_LINE_STEP + BLOCK_GAP;

    }



    if (oracle.length() > 0 && y < BODY_BASELINE_MAX - ORACLE_LINE_STEP) {

      int oracleMaxLines = (BODY_BASELINE_MAX - y) / ORACLE_LINE_STEP;

      if (oracleMaxLines > 10) {

        oracleMaxLines = 10;

      }

      printWrappedColumn(COL_X, y, oracle, COL_TEXT_W, ORACLE_LINE_STEP, oracleMaxLines, BODY_BASELINE_MAX,

                         &FreeSans9pt7b);

    }



    if (footerMeta.length() > 0) {
      printWrappedColumn(COL_X, FOOTER_META_BASELINE, footerMeta, COL_TEXT_W, FOOTER_LINE_STEP, 1,
                         FOOTER_Y_MAX, &FreeSans9pt7b);
    }

    if (setLine.length() > 0) {

      printWrappedColumn(COL_X, FOOTER_SET_BASELINE, setLine, COL_TEXT_W, FOOTER_LINE_STEP, FOOTER_MAX_LINES,

                         FOOTER_Y_MAX, &FreeSans9pt7b);

    }

  });

}



// Compact ``image`` mirrors Scryfall ``image_uris`` keys. Prefer full frame for the panel JPEG.
static const char *pickCardImageUrl(JsonVariant imgNode, const char **outKey) {
  if (outKey) {
    *outKey = nullptr;
  }
  if (!imgNode.is<JsonObject>()) {
    return nullptr;
  }
  JsonObject img = imgNode.as<JsonObject>();
  static const char *const keys[] = {"display_bw_raw", "display_bw", "display", "normal", "large", "png", "small",
                                     "art_crop", "border_crop"};
  for (const char *k : keys) {
    const char *u = img[k].as<const char *>();
    if (u && u[0]) {
      if (outKey) {
        *outKey = k;
      }
      return u;
    }
  }
  return nullptr;
}

static void cv_log_url_trunc(const char *prefix, const char *url) {
  if (!url || !url[0]) {
    CV_LOG("%s (empty)\n", prefix);
    return;
  }
  size_t n = strlen(url);
  if (n <= 100) {
    CV_LOG("%s %s\n", prefix, url);
  } else {
    CV_LOG("%s %.48s...%s\n", prefix, url, url + n - 45);
  }
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

  CV_LOG("[fetch] GET /scryfall/... compact len=%u heap=%u\n", (unsigned)json.length(), (unsigned)ESP.getFreeHeap());

  uint8_t *imgBuf = nullptr;

  size_t imgLen = 0;
  String pickedImageKey = "";



  if (json.length() > 0) {

    JsonDocument doc;

    DeserializationError je = deserializeJson(doc, json);

    if (!je) {

      const char *pickedKey = nullptr;

      const char *imgUrl = pickCardImageUrl(doc["image"], &pickedKey);

      if (imgUrl && strlen(imgUrl) > 0) {

        if (pickedKey) {

          CV_LOG("[fetch] image key=%s\n", pickedKey);
          pickedImageKey = String(pickedKey);

        }

        cv_log_url_trunc("[fetch] art URL", imgUrl);

        bool artOk = httpGetBinary(String(imgUrl), &imgBuf, &imgLen);

        if (!artOk) {

          CV_LOG("[fetch] art GET binary failed (non-200, stream, or OOM) heap=%u\n",

                 (unsigned)ESP.getFreeHeap());

        } else {

          unsigned m0 = imgLen >= 1 && imgBuf ? imgBuf[0] : 0;

          unsigned m1 = imgLen >= 2 && imgBuf ? imgBuf[1] : 0;

          unsigned m2 = imgLen >= 3 && imgBuf ? imgBuf[2] : 0;

          unsigned m3 = imgLen >= 4 && imgBuf ? imgBuf[3] : 0;

          CV_LOG("[fetch] art GET ok bytes=%u magic=%02X%02X%02X%02X heap=%u\n", (unsigned)imgLen, m0, m1, m2, m3,

                 (unsigned)ESP.getFreeHeap());

        }

      } else {

        CV_LOG("[fetch] no image URL (compact JSON missing image or empty keys)\n");

      }

    } else {

      CV_LOG("[fetch] compact JSON parse error: %s\n", je.c_str());

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

    cv_trace("fetch ok, drawCardScreen");

    drawCardScreen(json, imgBuf, imgLen, pickedImageKey);
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


