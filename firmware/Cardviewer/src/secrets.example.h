#pragma once

// Copy to secrets.h and fill in. Do not commit real credentials.

#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-password"

// Companion API base (no trailing slash). The firmware appends "/scryfall/cards/...".
// - Behind nginx (compose): use http://HOST/api — same origin as /api/scryfall/... in a browser.
// - Direct to Sanic port: http://HOST:8000
#define COMPANION_API_BASE "http://192.168.1.100/api"
