# Relational Data Model Design

**Date:** 2026-05-06

## Goal

Replace the JSON-snapshot data model (`common_cards`, `common_decks`, `recent_battles` with `json` columns) with a fully relational schema. Pull cards into a master catalog, model decks as identity rows with explicit form information, model players as identities, and treat aggregations as read-time queries over `battles` rather than periodically-rewritten JSON blobs.

## Goals (ranked)

1. Adding a card field becomes one `ALTER cards ADD COLUMN` + a one-time backfill from CR `/cards`. No re-cron, no snapshot replacement.
2. Card identity uses CR API's stable numeric `id`. Card renames don't break aggregations.
3. Aggregations (`/decks`, `/cards`) become SQL queries over a rolling time window. No staleness from old snapshots.
4. Two players running "the same deck" with different evo/hero variant choices are *different decks* (deck identity includes form). Two players running the same cards + same variant choices but different slot order within the regular slots are the *same deck*.
5. Schema changes ship through numbered SQL migration files with a tracking table.

## Non-Goals (v1)

- Snapshot history / trend charts — explicitly dropped.
- Per-player rank history (rank at battle time stays on the battle row; no longitudinal player.rank).
- Deck name strings (RoyaleAPI-style "EvoMortar Cart HeroGobs Bait").
- "Decks containing card X" filter UI (the `<@` array operator makes it cheap to add later).
- Backwards-compatible API contract — no external consumers.
- Caching at the read layer.
- Migration of existing data. We `wipe and re-cron`; battles older than the new ingest start are gone.

## Migration Strategy

**Wipe and re-cron.** Drop the existing `common_cards`, `common_decks`, `recent_battles` tables. Create the new schema empty. Run `make update-cards` to repopulate from CR API. Loses 7 months of `recent_battles` history (3,802 rows back to 2026-03-12). The `common_*` snapshots are throwaway by design (only the latest is ever read).

## Schema (4 tables)

```
┌────────────────────────────────────────────────────────────────────────┐
│ cards                      -- master card list                         │
├────────────────────────────────────────────────────────────────────────┤
│   id                  BIGINT PK         (CR API id, e.g. 26000010)     │
│   name                TEXT NOT NULL                                    │
│   rarity              TEXT NOT NULL                                    │
│   elixir_cost         INT                                              │
│   max_level           INT                                              │
│   has_evolution       BOOL NOT NULL                                    │
│   has_hero            BOOL NOT NULL                                    │
│   icon_url            TEXT                                             │
│   evolution_icon_url  TEXT                                             │
│   hero_icon_url       TEXT                                             │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ decks                      -- deck identity = (cards + form choices)   │
├────────────────────────────────────────────────────────────────────────┤
│   id                  BIGSERIAL PK                                     │
│   hash                CHAR(64) UNIQUE                                  │
│   card_ids            BIGINT[8] NOT NULL    (sorted, set of 8)         │
│   evo_card_ids        BIGINT[]  NOT NULL    (sorted subset; ≤ 3)       │
│   hero_card_ids       BIGINT[]  NOT NULL    (sorted subset; ≤ 2)       │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ players                                                                │
├────────────────────────────────────────────────────────────────────────┤
│   tag                 TEXT PK              (e.g. "#PPJU2YGP0")         │
│   name                TEXT                 (latest seen; players rename)│
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ battles                                                                │
├────────────────────────────────────────────────────────────────────────┤
│   timestamp           TIMESTAMPTZ NOT NULL                             │
│   team_tag            TEXT NOT NULL FK → players.tag                   │
│   opp_tag             TEXT          FK → players.tag                   │
│   team_deck_id        BIGINT NOT NULL FK → decks.id                    │
│   opp_deck_id         BIGINT NOT NULL FK → decks.id                    │
│   team_rank           INT                                              │
│   opp_rank            INT                                              │
│   team_crowns         INT                                              │
│   opp_crowns          INT                                              │
│   PRIMARY KEY (timestamp, team_tag)                                    │
└────────────────────────────────────────────────────────────────────────┘
```

### Deck identity rules

- Hash = `sha256(sorted(card_ids) || sorted(evo_card_ids) || sorted(hero_card_ids))`.
- Two decks with the same 8 cards + same evo subset + same hero subset → same `decks.id`.
- Different evo or hero choice → different `decks.id`.
- "Furnace-evo + Tesla-evo + 6 regulars" hashes the same regardless of which is in slot 0 vs slot 2.
- A card never belongs to both `evo_card_ids` and `hero_card_ids` simultaneously.

### Schema invariants (enforced in app, since Postgres CHECK can't express set ops cleanly)

- `length(card_ids) == 8`
- Every element of `evo_card_ids` is in `card_ids`. (`evo_card_ids ⊆ card_ids`)
- Every element of `hero_card_ids` is in `card_ids`. (`hero_card_ids ⊆ card_ids`)
- `evo_card_ids` and `hero_card_ids` share no elements.
- `length(hero_card_ids) ≤ 2`.

### Indexes

- `battles (timestamp DESC)` — recent-window scans.
- `battles (team_deck_id)` — `/decks` aggregation and recommendations group by this.
- `decks USING GIN (card_ids)` — supports `card_ids <@ owned_ids[]` subset filter for player recommendations.
- All FKs get implicit btree indexes via Postgres.

### `META_WINDOW_DAYS`

A new constant in `backend/settings.py`, default `7`. Bounds read-time aggregations:

```python
META_WINDOW_DAYS = 7
```

## Migration Infrastructure

### Files

- `backend/scripts/migrations/001_initial.sql` — all 4 tables + indexes + the `schema_migrations` tracking table.
- `backend/scripts/migrate.py` — runner that applies any unapplied migration files in order, recording each in `schema_migrations`.
- `Makefile` target `make migrate`.

### Tracking table

```sql
CREATE TABLE schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Runner behavior

`migrate.py` walks `backend/scripts/migrations/*.sql` in lexical order. For each file not in `schema_migrations`, it executes the file inside a transaction and inserts the filename. If a file fails, the transaction rolls back; subsequent runs retry. Idempotent.

### One-time deploy steps (manual)

1. `git pull`
2. `docker-compose exec backend python ./scripts/migrate.py drop_legacy` — drops the old `common_cards`, `common_decks`, `recent_battles` tables. Confirms with prompt.
3. `make migrate` — applies `001_initial.sql`.
4. `make update-cards` — first ingest populates `cards`, `players`, `decks`, `battles`.
5. `/decks` and `/cards` return empty until the window has data; that's a few cron runs.

`init_db.py` is deleted; schema lives in migrations now. `Makefile`'s `init-db` target is replaced with `migrate`.

## Ingestion (Cron Flow)

```
1. Refresh `cards` from CR /cards (upsert by id).
2. Get top-N player tags + their PoL ranks.
3. Fetch battlelogs (parallel, unchanged from today).
4. For each battle in battlelogs:
   a. Compute team and opp deck identities via deck_inference():
      - Sort card_ids ascending.
      - Determine evo_card_ids: card in slot 0 if cards.has_evolution; or
        card in slots 1/2 with cards.has_evolution AND NOT cards.has_hero
        (per existing slot rule from variants.py).
      - Determine hero_card_ids: card in slots 1/2 with cards.has_hero.
      - Hash.
   b. Upsert decks: INSERT ON CONFLICT (hash) DO NOTHING RETURNING id;
      if no id returned, SELECT id WHERE hash = $1.
   c. Upsert players: (team_tag, team_name) and (opp_tag, opp_name) with
      ON CONFLICT (tag) DO UPDATE SET name = EXCLUDED.name.
   d. Insert battle: ON CONFLICT (timestamp, team_tag) DO NOTHING.
```

No aggregation step. No truncation. Append-and-upsert only. Wrap each cron run in two transactions: one for the `cards` refresh, one for the deck/player/battle ingest cycle.

### Helpers in `data_utils.py`

- `refresh_cards_catalog()` — wraps CR `/cards`, upserts `cards` table.
- `infer_deck(battle_side_cards)` → `(card_ids, evo_card_ids, hero_card_ids, hash)`. Uses the existing `slot_active_variant` rule to derive form sets from CR battle slot data.
- `upsert_deck(conn, card_ids, evo_card_ids, hero_card_ids, hash)` → `deck_id`.
- `upsert_player(conn, tag, name)` — single statement.
- `insert_battle(conn, battle_row)` — `ON CONFLICT DO NOTHING`.

### Helpers deleted

- `_battle_deck` — superseded by `infer_deck` + `upsert_deck`.
- `get_card_data`, `get_deck_data` — aggregation moves to read time.
- `get_battle_rows` — refactored: returns deck-id-keyed rows instead of inlined deck JSON.

## Read API

The frontend contract stays the same. Endpoints rebuild their JSON shapes from the new schema.

### `GET /decks`

```sql
WITH recent_team_decks AS (
    SELECT team_deck_id AS deck_id, team_tag
    FROM battles
    WHERE timestamp > NOW() - %s::interval
)
SELECT
    d.id, d.hash, d.card_ids, d.evo_card_ids, d.hero_card_ids,
    COUNT(*) AS count,
    array_agg(DISTINCT rtd.team_tag) AS player_tags
FROM recent_team_decks rtd
JOIN decks d ON d.id = rtd.deck_id
GROUP BY d.id
ORDER BY count DESC
LIMIT 50;
```

The Flask resource then loads involved cards in one extra query (`SELECT * FROM cards WHERE id = ANY(...)`) and assembles the JSON the frontend expects:

```json
[
  {
    "count": 12,
    "cards": [
      {
        "name": "Royal Giant",
        "icon": "...",
        "hasEvolution": true,
        "hasHero": false,
        "evolvedIcon": "...",
        "heroIcon": null,
        "elixirCost": 6,
        "activeForm": "evolution"
      }
    ],
    "players": ["#ABC", "#DEF"]
  }
]
```

`activeForm` is computed in the resource via membership in `evo_card_ids` / `hero_card_ids`. Was implicit slot-based on the frontend before — now explicit so the frontend doesn't need to recompute the variant rule.

### `GET /cards`

```sql
WITH deck_slots AS (
    SELECT
        b.team_deck_id AS deck_id,
        c.id AS card_id,
        d.evo_card_ids,
        d.hero_card_ids
    FROM battles b
    JOIN decks d ON d.id = b.team_deck_id,
    UNNEST(d.card_ids) AS c(id)
    WHERE b.timestamp > NOW() - %s::interval
)
SELECT
    card_id,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE card_id = ANY(evo_card_ids))  AS evolution_count,
    COUNT(*) FILTER (WHERE card_id = ANY(hero_card_ids)) AS hero_count
FROM deck_slots
GROUP BY card_id
ORDER BY count DESC;
```

Resource joins to `cards` for icon/name/elixir_cost.

### `GET /battles`

```sql
SELECT
    b.timestamp, b.team_tag, p1.name AS team_name, b.team_rank, b.team_crowns,
    b.team_deck_id,
    b.opp_tag, p2.name AS opp_name, b.opp_rank, b.opp_crowns,
    b.opp_deck_id
FROM battles b
LEFT JOIN players p1 ON p1.tag = b.team_tag
LEFT JOIN players p2 ON p2.tag = b.opp_tag
ORDER BY b.timestamp DESC
LIMIT 10;
```

Resource fetches the two referenced deck rows + the involved cards, assembles deck JSON in the same shape as `/decks`.

### `GET /player/<tag>`

CR API call unchanged. The recommendation engine now queries the schema:

```sql
SELECT
    d.id, d.hash, d.card_ids, d.evo_card_ids, d.hero_card_ids,
    COUNT(*) AS count
FROM battles b
JOIN decks d ON d.id = b.team_deck_id
WHERE b.timestamp > NOW() - %s::interval
  AND d.card_ids <@ %s::bigint[]   -- subset operator: every card_id is owned
GROUP BY d.id
ORDER BY count DESC
LIMIT 50;
```

Then in Python, `pick_recommended_decks` scores each candidate against the player's `evolution_level_by_name` (still bitmask logic), computes `fully_playable` / `missing_variants` / `avg_level`, sorts by `(fully_playable desc, count desc)`, slices to 3.

The `<@` array-subset operator pushes the ownership filter into Postgres.

### Shared rendering helper

Both `/decks` and `/battles` need to convert (deck row + cards table) into the frontend's per-card JSON shape. Extract one helper:

```python
def hydrate_deck(deck_row, cards_by_id):
    """Returns a list of 8 card dicts in render order:
       evos first, then heroes (sorted by elixir cost), then regulars
       (sorted by elixir cost). Each dict includes activeForm derived
       from membership in deck_row['evo_card_ids'] / deck_row['hero_card_ids']."""
```

Lives in `apis/utils/decks.py`. Used by `/decks`, `/battles`, and `/player/<tag>` recommendations.

## Edge Cases

| Case | Behavior |
|---|---|
| First cron run after wipe — `battles` empty | `/decks` and `/cards` return `[]`; UI shows existing "Loading…" / empty states. |
| Window has no battles yet | Same — empty aggregations until the second cron run inside the window. |
| Player renames mid-window | `players.name` updated by upsert; battles join to current name. |
| Battle has no opponent | Skip the row entirely (matches today's behavior in `get_battle_rows`). |
| Battle's opp deck never seen before | Cron upserts the deck row before inserting the battle. FK satisfied. |
| Cron partial failure mid-batch | Wrap each cron run in transactions. Roll back on error; next run retries. |
| Card removed from CR | `cards` row stays — historical battles still reference it. |
| Schema migration mid-cron | Cron reads `schema_migrations` at startup, exits if any unapplied migration exists. Manual `make migrate` then `make update-cards`. |

## Testing

### Unit tests

- **`test_recommendation.py`** — 14 tests, signatures adapted. `pick_recommended_decks` stays a pure function: input is a list of candidate deck dicts (`{id, hash, card_ids, evo_card_ids, hero_card_ids}`) plus player ownership info; output is the scored/sorted list. The DB query that fetches candidates lives in `player.py`.
- **`test_variants.py`** — 13 tests, unchanged. `slot_active_variant` and `is_variant_unlocked` survive as ingestion-side helpers (used by `infer_deck` to derive form sets from raw CR battle slot data).
- **`test_deck_inference.py`** — new. ~6 cases: no variants, evo-only, hero-only, mixed (1 evo + 1 hero), dual-variant card placement, full 3 variant slots populated.
- **`test_hydrate_deck.py`** — new. ~5 cases: render order (evos → heroes → regulars by elixir), `activeForm` derivation, missing card data fallback (graceful), empty deck (defensive), all-regulars deck.
- **`test_sanity.py`** — 1, unchanged.

**Total: ~39 backend unit tests.**

No SQL integration tests. The new resource SQL is plain `SELECT … GROUP BY …` — verified by curl smoke tests in the deploy steps. If we add CI later, testcontainers / pytest-postgresql can supplement.

### Manual smoke tests (after deploy)

- `make migrate` succeeds with no errors; `schema_migrations` has `001_initial.sql`.
- `make update-cards` succeeds; `cards` populated (~150 rows), `players` populated, `decks` populated, `battles` populated.
- `curl http://localhost:5001/decks` returns `[]` initially, populated within a few cron runs.
- `curl http://localhost:5001/cards` returns `[]` initially, populated within a few cron runs.
- `curl http://localhost:5001/battles` returns recent N battles.
- `curl "http://localhost:5001/player/%23PPJU2YGP0"` returns identity + recommendations once `decks` has data.
- `/cards`, `/decks`, `/battles`, `/player/<tag>` pages render correctly.
- `/decks` overlay (with player tag set) shows yellow "no evo"/"no hero" badges where appropriate.
