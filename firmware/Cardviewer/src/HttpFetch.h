#ifndef HTTP_FETCH_H
#define HTTP_FETCH_H

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>

inline String httpGetString(const String &url) {
  if (WiFi.status() != WL_CONNECTED) {
    return "";
  }
  WiFiClientSecure secureClient;
  HTTPClient http;
  http.setTimeout(30000);
  bool https = url.startsWith("https://");
  if (https) {
    secureClient.setInsecure();
    if (!http.begin(secureClient, url)) {
      Serial.println("[HTTP] begin() failed (https)");
      return "";
    }
  } else {
    if (!http.begin(url)) {
      Serial.println("[HTTP] begin() failed (http)");
      return "";
    }
  }
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    Serial.printf("[HTTP] GET status %d (expected 200): %s\n", code, url.c_str());
    http.end();
    return "";
  }
  String payload = http.getString();
  http.end();
  return payload;
}

// Read exactly `len` bytes from stream (handles partial TLS reads).
inline bool httpReadExact(WiFiClient *stream, uint8_t *buf, size_t len) {
  size_t got = 0;
  unsigned long t0 = millis();
  while (got < len && millis() - t0 < 45000u) {
    int n = stream->readBytes(buf + got, len - got);
    if (n > 0) {
      got += (size_t)n;
      continue;
    }
    delay(1);
    if (!stream->available() && !stream->connected()) {
      break;
    }
  }
  return got == len;
}

// Unknown length / chunked: read until connection ends and no data pending.
inline bool httpReadToBuffer(WiFiClient *stream, HTTPClient *http, uint8_t **out, size_t *outLen) {
  const size_t chunk = 4096;
  size_t cap = chunk;
  uint8_t *buf = (uint8_t *)malloc(cap);
  if (!buf) {
    return false;
  }
  size_t total = 0;
  unsigned long t0 = millis();
  unsigned long lastProgress = millis();
  const unsigned long overallTimeout = 60000u;
  const unsigned long stallTimeout = 20000u;

  while (millis() - t0 < overallTimeout) {
    size_t avail = stream->available();
    if (avail == 0) {
      if (!http->connected()) {
        break;
      }
      if (millis() - lastProgress > stallTimeout) {
        Serial.println("[HTTP] binary read stalled (timeout)");
        break;
      }
      delay(2);
      continue;
    }
    if (total + avail > cap) {
      cap = total + avail + chunk;
      uint8_t *nb = (uint8_t *)realloc(buf, cap);
      if (!nb) {
        free(buf);
        return false;
      }
      buf = nb;
    }
    int r = stream->readBytes(buf + total, avail);
    if (r <= 0) {
      break;
    }
    total += (size_t)r;
    lastProgress = millis();
  }
  if (total == 0) {
    free(buf);
    *out = nullptr;
    *outLen = 0;
    return false;
  }
  *out = buf;
  *outLen = total;
  return true;
}

inline bool httpGetBinaryOnce(const String &url, uint8_t **out, size_t *outLen) {
  *out = nullptr;
  *outLen = 0;
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  WiFiClientSecure secureClient;
  HTTPClient http;
  http.setTimeout(30000);
  bool https = url.startsWith("https://");
  if (https) {
    secureClient.setInsecure();
    if (!http.begin(secureClient, url)) {
      Serial.println("[HTTP] binary begin() failed (https)");
      return false;
    }
  } else {
    if (!http.begin(url)) {
      Serial.println("[HTTP] binary begin() failed (http)");
      return false;
    }
  }
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    Serial.printf("[HTTP] binary GET status %d\n", code);
    http.end();
    return false;
  }
  int len = http.getSize();
  WiFiClient *stream = http.getStreamPtr();
  if (stream == nullptr) {
    http.end();
    return false;
  }
  if (len > 0) {
    uint8_t *buf = (uint8_t *)malloc((size_t)len);
    if (!buf) {
      http.end();
      return false;
    }
    if (!httpReadExact(stream, buf, (size_t)len)) {
      Serial.printf("[HTTP] binary short read got < %d bytes\n", len);
      free(buf);
      http.end();
      return false;
    }
    http.end();
    *out = buf;
    *outLen = (size_t)len;
    return true;
  }
  // Chunked or unknown length (getSize() <= 0): previous loop used (len > 0 || len == -1)
  // which never runs when len==0, and could exit early while data was still in flight.
  bool ok = httpReadToBuffer(stream, &http, out, outLen);
  http.end();
  return ok;
}

inline bool httpGetBinary(const String &url, uint8_t **out, size_t *outLen) {
  *out = nullptr;
  *outLen = 0;
  const int maxAttempts = 3;
  for (int attempt = 0; attempt < maxAttempts; ++attempt) {
    if (attempt > 0) {
      delay(300);
      Serial.printf("[HTTP] binary retry %d/%d\n", attempt + 1, maxAttempts);
    }
    uint8_t *buf = nullptr;
    size_t n = 0;
    if (httpGetBinaryOnce(url, &buf, &n)) {
      *out = buf;
      *outLen = n;
      return true;
    }
    if (buf) {
      free(buf);
    }
  }
  return false;
}

#endif
