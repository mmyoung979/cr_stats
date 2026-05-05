# Recent Battles Page (`/battles`) — Design

**Date:** 2026-05-04
**Status:** Approved, ready for implementation plan
**Scope:** v1 — first iteration

## Summary

Add a new page at `/battles` showing the 10 most recent `pathOfLegend` battles played by the top 100 ranked players. Each row shows both players' name, tag, deck (8 cards), crown count, and the battle timestamp. Snapshot-driven, refreshed by the existing cron — no API-time calls to the Clash Royale API.

The existing `/decks` page (most-common decks aggregation) is kept unchanged.

## Goals

- Display 10 most recent ranked battles among top players, with both decks visible side-by-side.
- Reuse the existing cron pipeline — no extra Clash Royale API calls per refresh.
- Selection rule ("which 10") lives in SQL so it can be changed without redeploying the cron.

## Non-goals (v1)

- Pagination, auto-refresh, or filtering UI.
- Pruning of old rows (table will grow modestly; revisit later).
- Tests beyond the existing single sanity test.
- Authentication or rate limiting on the new endpoint (matches existing endpoints).
- Linking to player profiles.

## Architecture

```
update_cards.py (cron)
  └─ get_battlelog_data(100)              ← already runs
       ├─ get_card_data()  → common_cards   ← already runs
       ├─ get_deck_data()  → common_decks   ← already runs
       └─ get_battle_rows() → recent_battles ← NEW (one INSERT per pathOfLegend battle)

GET /battles  (new Flask-RESTful resource)
  └─ SELECT ... FROM recent_battles
     ORDER BY battle_time DESC LIMIT 10
  → JSON list

frontend/src/components/Battles.js  (new route /battles in index.js)
  └─ fetch("http://localhost:5001/battles") in componentDidMount
  → renders 10 battle rows: name + tag + deck for both players, timestamp, result
```

The new aggregator iterates the same in-memory `battlelog_data` already fetched in `update_cards.py` — no extra Clash Royale API calls and no extra latency in the cron run. Each `pathOfLegend` battle becomes one row with `ON CONFLICT DO NOTHING` on the primary key, so re-running the cron mid-day inserts only new battles.

## Database schema

Added to `backend/scripts/init_db.py` (idempotent):

```sql
CREATE TABLE IF NOT EXISTS recent_battles (
    battle_time  TIMESTAMP WITH TIME ZONE NOT NULL,
    team_tag     TEXT NOT NULL,
    team_name    TEXT,
    team_deck    JSON NOT NULL,    -- list of {name, icon, evolvedIcon, hasEvolution}
    team_crowns  INT,
    opp_tag      TEXT,
    opp_name     TEXT,
    opp_deck     JSON NOT NULL,
    opp_crowns   INT,
    fetched_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (battle_time, team_tag)
);
CREATE INDEX IF NOT EXISTS recent_battles_battle_time_idx
    ON recent_battles (battle_time DESC);
```

The composite PK `(battle_time, team_tag)` uniquely identifies a battle (a player cannot have two battles at the same instant) and provides idempotency on re-runs. The descending index keeps `ORDER BY battle_time DESC LIMIT 10` cheap as the table grows.

## Backend changes

### `backend/scripts/utils/data_utils.py`

Add `get_battle_rows(battlelog_data)` mirroring the existing `get_deck_data` / `get_card_data` style.

- Filter to `battle["type"] == RANKED` (`pathOfLegend`).
- Skip battles where `team` or `opponent` is empty.
- Parse Clash Royale's `battleTime` (`"YYYYMMDDTHHMMSS.000Z"`) into a timezone-aware `datetime`.
- For each side, build the deck JSON in the **same shape** `get_deck_data` already produces:
  ```json
  [{"name": ..., "icon": ..., "evolvedIcon": ..., "hasEvolution": ...}, ...]
  ```
  This lets the frontend reuse the existing `Card` component without changes.
- Return a list of dicts with the columns: `battle_time`, `team_tag`, `team_name`, `team_deck`, `team_crowns`, `opp_tag`, `opp_name`, `opp_deck`, `opp_crowns`.

### `backend/scripts/update_cards.py`

After the existing `common_cards` and `common_decks` INSERTs, insert all rows from `get_battle_rows(battlelog_data)`:

```sql
INSERT INTO recent_battles (...)
VALUES (%s, %s, ..., %s)
ON CONFLICT (battle_time, team_tag) DO NOTHING
```

Use `cursor.executemany` with parameterized queries (player names are user-provided strings; the existing f-string SQL pattern is unsafe for that data). The two existing INSERTs stay as-is for this iteration.

### `backend/apis/recent_battles.py` (new file)

```python
from apis.utils.db_utils import make_connection
from flask_restful import Resource


class RecentBattles(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT battle_time, team_name, team_tag, team_deck, team_crowns,
                           opp_name, opp_tag, opp_deck, opp_crowns
                    FROM recent_battles
                    ORDER BY battle_time DESC
                    LIMIT 10
                """)
                rows = cursor.fetchall()
        return [
            {
                "battle_time": battle_time.isoformat(),
                "team_name": team_name,
                "team_tag": team_tag,
                "team_deck": team_deck,
                "team_crowns": team_crowns,
                "opp_name": opp_name,
                "opp_tag": opp_tag,
                "opp_deck": opp_deck,
                "opp_crowns": opp_crowns,
            }
            for (battle_time, team_name, team_tag, team_deck, team_crowns,
                 opp_name, opp_tag, opp_deck, opp_crowns) in rows
        ]
```

The `team_deck` / `opp_deck` columns are already JSON; psycopg2 returns them as Python objects, so they pass through to the response as-is.

### `backend/app.py`

```python
from apis.recent_battles import RecentBattles
api.add_resource(RecentBattles, "/battles")
```

## Frontend changes

### `frontend/src/index.js`

Add one route:

```js
import Battles from "./components/Battles";
// ...
<Route path="battles" element={<App component={Battles} />} />
```

### `frontend/src/components/Battles.js` (new file)

Class component matching the style of `TopDecks.js` / `TopCards.js`:

```jsx
state = { loading: true, battles: null }

async componentDidMount() {
  const res = await fetch("http://localhost:5001/battles");
  this.setState({ loading: false, battles: await res.json() });
}
```

Render shape per battle row:

```
─────────────────────────────────────────────
Battle #1 — 2026-05-04 14:32 UTC
PlayerName (#TAG)  [WINNER]    3 – 0    OpponentName (#TAG)

[card][card][card][card]                    [card][card][card][card]
[card][card][card][card]                    [card][card][card][card]
─────────────────────────────────────────────
```

The `[WINNER]` badge is placed next to whichever player has the higher crown count (`team_crowns > opp_crowns` → team side; `<` → opponent side; `=` → render "Draw" centered between the names instead).

**New `BattleCard` component required.** The existing `Card` component is hardcoded to the aggregation context — it renders `"X/100 top players use Y"`, `(#rank)`, and an evolution-fraction string, none of which apply to a single battle. A new minimal `BattleCard` (icon + name, swapping to `evolvedIcon` when `idx < 2 && hasEvolution`) keeps the Battles view honest and avoids polluting `Card` with display-mode flags. Deck JSON shape is shared with `get_deck_data` output, but the renderer is not.

## Edge cases

| Case | Handling |
|------|----------|
| Battlelog has no pathOfLegend battles | Skip (matches existing `KeyError` handling pattern). |
| `opponent` array empty (player left mid-battle) | Skip that battle. |
| Same battle in two top players' battlelogs | PK `(battle_time, team_tag)` differs (each side appears as `team` in their own log), so both rows are inserted. This is desired — both perspectives are valid records. |
| Exact same row re-fetched in next cron run | `ON CONFLICT DO NOTHING` makes it a no-op. |
| Crown tie (rare in ranked) | Frontend renders "Draw" instead of a winner. |

## Testing

Manual smoke checks (the existing test suite is one sanity test; not expanding for v1):

1. `make init-db` — confirm `recent_battles` table + index via `\d recent_battles` in `psql`.
2. `docker-compose exec backend python ./scripts/dry_run.py` — extend the dry-run to also print the first 2 rows from `get_battle_rows()` (no DB write).
3. `make update-cards` — run the cron once. Then `SELECT count(*) FROM recent_battles` (expect hundreds) and spot-check the latest row.
4. Re-run `make update-cards` immediately — `count(*)` should be unchanged or barely higher (idempotency check).
5. `curl http://localhost:5001/battles | jq 'length'` → 10. `jq '.[0]'` → spot-check shape.
6. `cd frontend && npm start`, visit `localhost:3000/battles` — 10 rows render with both decks, names, tags, timestamp, winner indicator.
7. Visit `/` and `/decks` — confirm no regression on existing routes.

## Rollout

One PR, staged commits:

1. Schema change (`init_db.py`) + run `make init-db` on the host.
2. Backend (`data_utils.py`, `update_cards.py`, `apis/recent_battles.py`, `app.py`).
3. Cron run to populate the table.
4. Frontend (`Battles.js`, `BattleCard.js`, `index.js` route) + `npm run build` for the dockerized stack to serve the new route via nginx.

## Open questions / deferred

- **Selection rule beyond v1.** v1 is global `ORDER BY battle_time DESC LIMIT 10`. If this concentrates on 2-3 hyperactive players, switch to e.g. `DISTINCT ON (team_tag) ... ORDER BY team_tag, battle_time DESC` then re-sort and limit. SQL-only change, no schema or cron impact.
- **Pruning.** Add a `DELETE WHERE fetched_at < now() - interval '7 days'` to the cron once row count becomes a concern.
- **Cron cadence.** Inherits whatever the existing cron uses. If "recent" feels stale, the cadence is the lever.
