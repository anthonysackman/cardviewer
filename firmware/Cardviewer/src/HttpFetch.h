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
  http.setTimeout(20000);
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

inline bool httpGetBinary(const String &url, uint8_t **out, size_t *outLen) {
  *out = nullptr;
  *outLen = 0;
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  WiFiClientSecure secureClient;
  HTTPClient http;
  http.setTimeout(20000);
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
  if (len <= 0) {
    const size_t chunk = 4096;
    size_t cap = chunk;
    uint8_t *buf = (uint8_t *)malloc(cap);
    if (!buf) {
      http.end();
      return false;
    }
    size_t total = 0;
    while (http.connected() && (len > 0 || len == -1)) {
      size_t avail = stream->available();
      if (!avail) {
        delay(1);
        continue;
      }
      if (total + avail > cap) {
        cap = total + avail + chunk;
        uint8_t *nb = (uint8_t *)realloc(buf, cap);
        if (!nb) {
          free(buf);
          http.end();
          return false;
        }
        buf = nb;
      }
      int r = stream->readBytes(buf + total, avail);
      if (r <= 0) {
        break;
      }
      total += (size_t)r;
    }
    http.end();
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
  uint8_t *buf = (uint8_t *)malloc((size_t)len);
  if (!buf) {
    http.end();
    return false;
  }
  size_t read = stream->readBytes(buf, len);
  http.end();
  if (read != (size_t)len) {
    free(buf);
    return false;
  }
  *out = buf;
  *outLen = read;
  return true;
}

#endif
