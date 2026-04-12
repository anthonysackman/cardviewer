# Skryfall — Database Schema Plan

## PostgreSQL Tables

### `cards`
Stores one row per API printing (not per oracle card).

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
| `set_code` | TEXT FK | NO | `set` → `sets.code` |
| `set_name` | TEXT | NO | `set_name` (denormalized snapshot at ingest) |
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
| `card_id` | UUID FK | NO | → `cards.id` (ON DELETE CASCADE) |
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
| `current_card_id` | UUID FK | YES | → `cards.id` (ON DELETE SET NULL) |
| `updated_at` | TIMESTAMP | NO | |

---

## Foreign keys

| Child table | Column(s) | Parent | ON DELETE |
|---|---|---|---|
| `cards` | `set_code` | `sets.code` | RESTRICT (default) |
| `card_images` | `card_id` | `cards.id` | CASCADE |
| `settings` | `current_card_id` | `cards.id` | SET NULL |

---

## Constraints and indexes

| Name | Definition |
|---|---|
| `uq_cards_set_collector` | UNIQUE (`set_code`, `collector_number`) |
| `ix_cards_oracle_id` | INDEX on `oracle_id` |
| `ix_cards_cached_at` | INDEX on `cached_at` (staleness / eviction) |

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
- Card cache expires 24hr per upstream API ToS — use `cached_at` to check staleness
- Images stored on disk volume, path stored in `card_images` table
- `settings` is always a single row (id=1), use upsert
- `set_name` on `cards` is denormalized; authoritative set metadata lives in `sets`
- Migrations: Docker Compose runs the `migrate` service (`alembic upgrade head`) after Postgres is healthy and before `api` starts; locally use `python -m alembic upgrade head` from `companion/api` with `DATABASE_URL` if needed

---

## Companion API — compact card (ESP)

`GET /scryfall/cards/random?format=compact` returns `schema`, `id`, `layout`, `image` (`status`, `art_crop`), `panel` (name, `mana_symbols` as ordered `{…}` tokens, `cmc`, type/oracle/P/T/loyalty, sorted `color_identity`, set line, etc.). Default without `format=compact` returns full upstream `{ "card": … }`.
