# Skryfall — Database Schema Plan

## PostgreSQL Tables

### `cards`
Stores one row per Scryfall printing (not per oracle card).

| Column | Type | Nullable | Source |
|---|---|---|---|
| `id` | UUID PK | NO | `id` |
| `oracle_id` | UUID | NO | `oracle_id` |
| `name` | TEXT | NO | `name` |
| `mana_cost` | TEXT | YES | `mana_cost` (empty on lands) |
| `cmc` | FLOAT | NO | `cmc` |
| `type_line` | TEXT | NO | `type_line` |
| `oracle_text` | TEXT | YES | `oracle_text` |
| `flavor_text` | TEXT | YES | `flavor_text` |
| `power` | TEXT | YES | `power` (creatures only) |
| `toughness` | TEXT | YES | `toughness` (creatures only) |
| `loyalty` | TEXT | YES | `loyalty` (planeswalkers only) |
| `rarity` | TEXT | NO | `rarity` |
| `set_code` | TEXT | NO | `set` |
| `set_name` | TEXT | NO | `set_name` |
| `collector_number` | TEXT | NO | `collector_number` |
| `artist` | TEXT | NO | `artist` |
| `color_identity` | TEXT[] | NO | `color_identity` |
| `keywords` | TEXT[] | NO | `keywords` |
| `watermark` | TEXT | YES | `watermark` |
| `price_usd` | NUMERIC | YES | `prices.usd` |
| `price_usd_foil` | NUMERIC | YES | `prices.usd_foil` |
| `prints_search_uri` | TEXT | NO | `prints_search_uri` |
| `art_crop_url` | TEXT | NO | `image_uris.art_crop` |
| `cached_at` | TIMESTAMP | NO | server time on insert |

---

### `card_images`
Stores dithered 1-bit bitmaps for the ESP32.

| Column | Type | Nullable | Source |
|---|---|---|---|
| `id` | UUID PK | NO | generated |
| `card_id` | UUID FK | NO | → `cards.id` |
| `local_path` | TEXT | NO | path to file on disk/volume |
| `cached_at` | TIMESTAMP | NO | server time on insert |

---

### `symbols`
Mana symbol lookup. Seeded once from `/symbology`.

| Column | Type | Nullable | Source |
|---|---|---|---|
| `symbol` | TEXT PK | NO | `symbol` e.g. `{W}` |
| `label` | TEXT | NO | `english` e.g. `one white mana` |
| `svg_uri` | TEXT | YES | `svg_uri` |
| `cmc` | FLOAT | YES | `cmc` |
| `colors` | TEXT[] | YES | `colors` |

---

### `sets`
Set lookup. Seeded once from `/sets`.

| Column | Type | Nullable | Source |
|---|---|---|---|
| `code` | TEXT PK | NO | `code` e.g. `dtk` |
| `name` | TEXT | NO | `name` |
| `released_at` | DATE | YES | `released_at` |
| `set_type` | TEXT | YES | `set_type` |
| `icon_svg_uri` | TEXT | YES | `icon_svg_uri` |

---

### `settings`
Single-row app config table.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | INT PK | NO | always 1 |
| `mode` | TEXT | NO | `random`, `daily`, `pushed`, `cycle` |
| `current_card_id` | UUID FK | YES | → `cards.id` |
| `updated_at` | TIMESTAMP | NO | |

---

## Redis Keys

| Key | Value | TTL |
|---|---|---|
| `card:current` | JSON blob of current card | 24hr |
| `card:daily` | card id for daily mode | 24hr (midnight reset) |
| `image:{card_id}` | cached dithered bitmap bytes | 24hr |

---

## Notes
- `mana_cost` stored raw (`{2}{W}{U}`), resolved to display via `symbols` table
- Prices stored per printing — use `prints_search_uri` to find cheapest reprint at fetch time
- Card cache expires 24hr per Scryfall ToS — use `cached_at` to check staleness
- Images stored on disk volume, path stored in `card_images` table
- `settings` is always a single row (id=1), use upsert
