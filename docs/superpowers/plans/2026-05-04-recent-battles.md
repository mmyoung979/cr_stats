# Recent Battles Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/battles` page showing the 10 most recent `pathOfLegend` battles among top-100 ranked players, with both players' name, tag, deck, crown count, and battle timestamp.

**Architecture:** Snapshot-driven — the existing cron (`update_cards.py`) iterates the same in-memory battlelog data it already fetches and inserts one row per `pathOfLegend` battle into a new `recent_battles` table with `ON CONFLICT DO NOTHING`. A new `/battles` Flask-RESTful endpoint serves the latest 10 rows (`ORDER BY battle_time DESC LIMIT 10`). React reuses the existing `App` chrome with a new `Battles` route + minimal `BattleCard` renderer.

**Tech Stack:** Python 3 + Flask-RESTful + psycopg2 + Postgres 17.5; React 18 + react-router v7 + Create React App; nginx for prod.

**Spec:** `docs/superpowers/specs/2026-05-04-recent-battles-design.md`

**Testing model:** The spec explicitly excludes unit tests for v1 (the existing test suite is a single sanity test). Each task ends with a manual smoke check using `psql`, `curl`, `dry_run.py`, or the browser before committing. **Do not skip the smoke checks** — they replace tests in this plan.

**Working assumption:** the docker stack is already running (`make up`). If not, run `make up` first.

---

## File Structure

**Create:**
- `backend/apis/recent_battles.py` — Flask-RESTful resource for `GET /battles`
- `frontend/src/components/Battles.js` — page component
- `frontend/src/components/BattleCard.js` — minimal single-card renderer

**Modify:**
- `backend/scripts/init_db.py` — add `recent_battles` table + index
- `backend/scripts/utils/data_utils.py` — add `get_battle_rows()` aggregator
- `backend/scripts/update_cards.py` — insert battle rows after existing inserts
- `backend/scripts/dry_run.py` — print first 2 rows from `get_battle_rows()` for smoke check
- `backend/app.py` — register `RecentBattles` resource at `/battles`
- `frontend/src/index.js` — add `/battles` route

---

## Task 1: Schema — `recent_battles` table

**Files:**
- Modify: `backend/scripts/init_db.py`

- [ ] **Step 1: Add table + index to `init_db.py`**

Replace the SQL string in `backend/scripts/init_db.py` so the file reads:

```python
# Local imports
from apis.utils.db_utils import make_connection

if __name__ == "__main__":
    with make_connection() as connection:
        with connection.cursor() as cursor:
            sql = """
            CREATE TABLE IF NOT EXISTS common_cards (
                id SERIAL PRIMARY KEY,
                cards JSON,
                timestamp timestamp with time zone
            );
            CREATE TABLE IF NOT EXISTS common_decks (
                id SERIAL PRIMARY KEY,
                decks JSON,
                timestamp timestamp with time zone
            );
            CREATE TABLE IF NOT EXISTS recent_battles (
                battle_time  TIMESTAMP WITH TIME ZONE NOT NULL,
                team_tag     TEXT NOT NULL,
                team_name    TEXT,
                team_deck    JSON NOT NULL,
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
            """
            cursor.execute(sql)
            connection.commit()
```

- [ ] **Step 2: Run the migration**

Run: `make init-db`
Expected output: `Database has been initialized`

- [ ] **Step 3: Verify the table and index exist**

Run:
```bash
docker-compose exec postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "\d recent_battles"
```
Expected: a table description showing the 10 columns above, the composite primary key `(battle_time, team_tag)`, and the index `recent_battles_battle_time_idx`.

If the columns or index are missing, fix the SQL and re-run `make init-db` (it's idempotent).

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/init_db.py
git commit -m "Add recent_battles table for /battles page"
```

---

## Task 2: Aggregator — `get_battle_rows()`

**Files:**
- Modify: `backend/scripts/utils/data_utils.py`
- Modify: `backend/scripts/dry_run.py`

- [ ] **Step 1: Add imports and `get_battle_rows()` to `data_utils.py`**

At the top of `backend/scripts/utils/data_utils.py`, add `from datetime import datetime, timezone` to the Python-imports block.

Then add this function at the bottom of the file (after `get_card_data`):

```python
def _battle_deck(side: dict) -> list[dict]:
    return [
        {
            NAME: card[NAME],
            "hasEvolution": card.get("maxEvolutionLevel") is not None,
            "icon": card["iconUrls"]["medium"],
            "evolvedIcon": card["iconUrls"].get("evolutionMedium"),
        }
        for card in side[CARDS]
    ]


def _parse_battle_time(raw: str) -> datetime:
    # Clash Royale format: "20260504T123045.000Z"
    return datetime.strptime(raw, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def get_battle_rows(battlelog_data):
    """Flatten battlelogs into one row per pathOfLegend battle.

    Returned dicts match the recent_battles table columns.
    """
    fetched_at = datetime.now(timezone.utc)
    rows = []
    for battlelog in battlelog_data:
        if not isinstance(battlelog, list):
            continue
        for battle in battlelog:
            if battle.get("type") != RANKED:
                continue
            team = battle.get("team") or []
            opp = battle.get("opponent") or []
            if not team or not opp:
                continue
            try:
                rows.append({
                    "battle_time": _parse_battle_time(battle["battleTime"]),
                    "team_tag": team[0]["tag"],
                    "team_name": team[0].get("name"),
                    "team_deck": _battle_deck(team[0]),
                    "team_crowns": team[0].get("crowns"),
                    "opp_tag": opp[0].get("tag"),
                    "opp_name": opp[0].get("name"),
                    "opp_deck": _battle_deck(opp[0]),
                    "opp_crowns": opp[0].get("crowns"),
                    "fetched_at": fetched_at,
                })
            except (KeyError, ValueError):
                continue
    return rows
```

Notes:
- `battlelog_data` items can be the API's error-shape dict instead of a list (e.g., 503s), hence the `isinstance` guard.
- `_battle_deck` produces the **same shape** as `get_deck_data`'s card dicts — frontend can rely on `name`/`icon`/`evolvedIcon`/`hasEvolution` fields.
- `team[0]` and `opp[0]` are guaranteed to exist after the `not team or not opp` check; the `try` covers an unexpected schema (missing `tag`, missing `cards`, malformed `battleTime`).

- [ ] **Step 2: Extend `dry_run.py` to print the first 2 battle rows**

Replace `backend/scripts/dry_run.py` with:

```python
#!/usr/bin/env python3

# Python imports
import json
from datetime import datetime

# Local imports
from scripts.utils.data_utils import (
    get_battlelog_data,
    get_battle_rows,
    get_card_data,
    get_deck_data,
)

if __name__ == "__main__":
    player_count: int = 50
    battlelog_data = get_battlelog_data(player_count)

    # card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    # print(card_data)

    # deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)
    # print(deck_data)

    rows = get_battle_rows(battlelog_data)
    print(f"battle_rows count: {len(rows)}")
    print("--- first 2 rows ---")

    def encode(obj):
        return obj.isoformat() if isinstance(obj, datetime) else str(obj)

    print(json.dumps(rows[:2], indent=2, default=encode))
```

- [ ] **Step 3: Run the dry run**

Run: `docker-compose exec backend python ./scripts/dry_run.py`

Expected:
- A `battle_rows count: N` line where N is in the dozens-to-hundreds (50 players × ~5 ranked battles each, with skips).
- Two JSON objects printed, each containing `battle_time` (ISO string), `team_tag`/`team_name`/`team_deck` (8 cards), `team_crowns`, `opp_tag`/`opp_name`/`opp_deck` (8 cards), `opp_crowns`, `fetched_at`.

If `count: 0`, double-check that the API key in `.env` is valid for the IP you're running on (the cards/decks tables would also be empty in that case). If a row has fewer than 8 cards, inspect the raw battlelog for the involved player tag — the spec accepts the row as-is.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/utils/data_utils.py backend/scripts/dry_run.py
git commit -m "Add get_battle_rows aggregator for recent battles"
```

---

## Task 3: Cron — insert battle rows in `update_cards.py`

**Files:**
- Modify: `backend/scripts/update_cards.py`

- [ ] **Step 1: Update `update_cards.py` to insert battle rows**

Replace `backend/scripts/update_cards.py` with:

```python
# Python imports
import json
from datetime import datetime

# Third party imports
from psycopg2.extras import Json, execute_values

# Local imports
from apis.utils.db_utils import make_connection
from scripts.utils.data_utils import (
    get_battle_rows,
    get_battlelog_data,
    get_card_data,
    get_deck_data,
)
from settings import TZ


BATTLE_INSERT_SQL = """
INSERT INTO recent_battles (
    battle_time, team_tag, team_name, team_deck, team_crowns,
    opp_tag, opp_name, opp_deck, opp_crowns, fetched_at
) VALUES %s
ON CONFLICT (battle_time, team_tag) DO NOTHING
"""


def update_common_cards_and_decks(player_count: int = 50):
    """
    Fetches battle log data, processes it to get common cards, common decks,
    and recent battles, and updates the database with the latest data.
    """
    battlelog_data = get_battlelog_data(player_count)
    card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)
    battle_rows = get_battle_rows(battlelog_data)

    with make_connection() as connection:
        with connection.cursor() as cursor:
            sql = f"""
            INSERT INTO common_cards(
                cards,
                timestamp
            )
            VALUES(
                '{card_data}',
                '{datetime.now(TZ)}'
            );
            INSERT INTO common_decks(
                decks,
                timestamp
            )
            VALUES(
                '{deck_data}',
                '{datetime.now(TZ)}'
            );
            """
            cursor.execute(sql)

            if battle_rows:
                values = [
                    (
                        r["battle_time"],
                        r["team_tag"],
                        r["team_name"],
                        Json(r["team_deck"]),
                        r["team_crowns"],
                        r["opp_tag"],
                        r["opp_name"],
                        Json(r["opp_deck"]),
                        r["opp_crowns"],
                        r["fetched_at"],
                    )
                    for r in battle_rows
                ]
                execute_values(cursor, BATTLE_INSERT_SQL, values)

            connection.commit()


if __name__ == "__main__":
    player_count: int = 100
    update_common_cards_and_decks(player_count)
    print("Common cards, decks, and recent battles updated successfully.")
```

Notes:
- `psycopg2.extras.execute_values` batches all rows into one round-trip — much faster than `executemany` for hundreds of rows.
- `Json()` wraps Python lists for JSON column inserts (psycopg2 won't auto-serialize).
- The existing two f-string INSERTs are left intact for this iteration to avoid scope creep; a future change can move them to parameterized form.

- [ ] **Step 2: Run the cron once**

Run: `make update-cards`
Expected: `Common cards, decks, and recent battles updated successfully.` then `Most recent cards have been updated`.

- [ ] **Step 3: Verify rows were inserted**

Run:
```bash
docker-compose exec postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "SELECT count(*) FROM recent_battles;"
```
Expected: a count in the dozens-to-hundreds (depends on how many of the top-100 had ranked battles in their last ~25 games).

Then:
```bash
docker-compose exec postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "SELECT battle_time, team_name, team_tag, team_crowns, opp_name, opp_tag, opp_crowns FROM recent_battles ORDER BY battle_time DESC LIMIT 3;"
```
Expected: 3 rows, latest first, all fields populated.

- [ ] **Step 4: Verify idempotency by re-running the cron**

Run:
```bash
docker-compose exec postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -tAc "SELECT count(*) FROM recent_battles;"
```
Save the number → `BEFORE`.

Run: `make update-cards`

Run the same `count(*)` query → `AFTER`.

Expected: `AFTER == BEFORE` (or marginally higher if new battles were played in the gap). If the count roughly doubled, the `ON CONFLICT` clause isn't matching — re-check the PK columns in `init_db.py` and the column order in `BATTLE_INSERT_SQL`.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/update_cards.py
git commit -m "Insert recent battles in cron run"
```

---

## Task 4: API endpoint — `GET /battles`

**Files:**
- Create: `backend/apis/recent_battles.py`
- Modify: `backend/app.py`

- [ ] **Step 1: Create the resource**

Create `backend/apis/recent_battles.py`:

```python
# Third party imports
from apis.utils.db_utils import make_connection
from flask_restful import Resource


class RecentBattles(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT battle_time, team_name, team_tag, team_deck, team_crowns,
                           opp_name, opp_tag, opp_deck, opp_crowns
                    FROM recent_battles
                    ORDER BY battle_time DESC
                    LIMIT 10
                    """
                )
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
            for (
                battle_time,
                team_name,
                team_tag,
                team_deck,
                team_crowns,
                opp_name,
                opp_tag,
                opp_deck,
                opp_crowns,
            ) in rows
        ]
```

`team_deck` / `opp_deck` come back as Python lists (psycopg2 decodes JSON columns automatically) and pass through `flask_restful` as-is.

- [ ] **Step 2: Register the resource in `app.py`**

Modify `backend/app.py` to add the import and the `add_resource` line so it reads:

```python
"""
Get analytics about top players in Clash Royale
"""

# Local imports
from __init__ import create_app
from apis.most_common_cards import MostCommonCards
from apis.most_common_decks import MostCommonDecks
from apis.recent_battles import RecentBattles

# Third party imports
from flask_restful import Api

# Instantiate app
app = create_app()
api = Api(app)
api.add_resource(MostCommonCards, "/cards")
api.add_resource(MostCommonDecks, "/decks")
api.add_resource(RecentBattles, "/battles")
```

- [ ] **Step 3: Verify gunicorn picked up the change**

The backend container runs gunicorn with `--reload`, so editing files in the bind-mounted source should reload automatically. Confirm:

```bash
docker-compose logs --tail=20 backend
```
Expected: a reload line mentioning `app.py` or `recent_battles.py`. If no reload is visible, restart: `docker-compose restart backend`.

- [ ] **Step 4: Smoke check the endpoint**

Run:
```bash
curl -s http://localhost:5001/battles | python3 -c "import json,sys; d=json.load(sys.stdin); print('len:', len(d)); print('first:', json.dumps(d[0], indent=2)[:600] if d else 'EMPTY')"
```
Expected: `len: 10` and a JSON dump of one battle showing `battle_time` (ISO), both names/tags, both `_deck` arrays, both `_crowns`. The first battle's `battle_time` should be the most recent.

If you get a 500, check `docker-compose logs --tail=50 backend` for the traceback. If `len: 0`, the `recent_battles` table is empty — re-run Task 3.

- [ ] **Step 5: Confirm existing endpoints still work**

```bash
curl -s -o /dev/null -w "/cards: %{http_code}\n/decks: %{http_code}\n" http://localhost:5001/cards http://localhost:5001/decks
```
Expected: both `200`.

- [ ] **Step 6: Commit**

```bash
git add backend/apis/recent_battles.py backend/app.py
git commit -m "Add /battles endpoint serving 10 most recent ranked battles"
```

---

## Task 5: Frontend — `BattleCard` component

**Files:**
- Create: `frontend/src/components/BattleCard.js`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/BattleCard.js`:

```jsx
import React from "react";

export default function BattleCard({ name, icon, evolvedIcon, hasEvolution, isEvolutionSlot }) {
    const showEvolved = isEvolutionSlot && hasEvolution && evolvedIcon;
    return (
        <div className="card my-2">
            <img
                src={showEvolved ? evolvedIcon : icon}
                className="card-img-top py-2"
                alt={name}
            />
            <div className="card-body p-2">
                <h6 className="card-title mb-0">{name}</h6>
            </div>
        </div>
    );
}
```

The first two slots in a Clash Royale deck (`idx < 2`) are evolution slots — the caller passes `isEvolutionSlot={idx < 2}`.

- [ ] **Step 2: Sanity-check the file compiles**

Run:
```bash
cd frontend && node -e "require('@babel/parser').parse(require('fs').readFileSync('src/components/BattleCard.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('ok')"
```
Expected: `ok`.

If you see `Cannot find module '@babel/parser'`, fall back to the smoke check in Task 6 — the dev server will surface any syntax errors there.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BattleCard.js
git commit -m "Add BattleCard component for /battles page"
```

---

## Task 6: Frontend — `Battles` page + `/battles` route

**Files:**
- Create: `frontend/src/components/Battles.js`
- Modify: `frontend/src/index.js`

- [ ] **Step 1: Create the `Battles` component**

Create `frontend/src/components/Battles.js`:

```jsx
import React, { Component } from "react";
import BattleCard from "./BattleCard";

export default class Battles extends Component {
    state = {
        loading: true,
        battles: null,
        error: null,
    };

    async componentDidMount() {
        try {
            const res = await fetch("http://localhost:5001/battles");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const battles = await res.json();
            this.setState({ loading: false, battles });
        } catch (err) {
            this.setState({ loading: false, error: err.message });
        }
    }

    renderDeck(deck) {
        return (
            <div className="row">
                {deck.map((card, idx) => (
                    <div key={idx} className="col-3">
                        <BattleCard
                            name={card.name}
                            icon={card.icon}
                            evolvedIcon={card.evolvedIcon}
                            hasEvolution={card.hasEvolution}
                            isEvolutionSlot={idx < 2}
                        />
                    </div>
                ))}
            </div>
        );
    }

    renderBattle(b, idx) {
        const teamWins = b.team_crowns > b.opp_crowns;
        const oppWins = b.opp_crowns > b.team_crowns;
        const draw = !teamWins && !oppWins;
        const when = new Date(b.battle_time).toUTCString();
        return (
            <div key={`${b.battle_time}-${b.team_tag}`} className="battle-section mb-4 text-white">
                <div className="battle-title mb-2">
                    Battle #{idx + 1} &mdash; {when}
                </div>
                <div className="battle-header mb-2">
                    <span>
                        {b.team_name} ({b.team_tag}){teamWins ? " — WINNER" : ""}
                    </span>
                    <span className="mx-3">
                        {b.team_crowns} – {b.opp_crowns}
                        {draw ? " (Draw)" : ""}
                    </span>
                    <span>
                        {b.opp_name} ({b.opp_tag}){oppWins ? " — WINNER" : ""}
                    </span>
                </div>
                <div className="row">
                    <div className="col-md-6">{this.renderDeck(b.team_deck)}</div>
                    <div className="col-md-6">{this.renderDeck(b.opp_deck)}</div>
                </div>
                <hr />
            </div>
        );
    }

    render() {
        if (this.state.loading) {
            return <div className="text-center text-white">Loading API data...</div>;
        }
        if (this.state.error) {
            return (
                <div className="text-center text-white">
                    Failed to load battles: {this.state.error}
                </div>
            );
        }
        return <div>{this.state.battles.map((b, i) => this.renderBattle(b, i))}</div>;
    }
}
```

- [ ] **Step 2: Add the route to `index.js`**

Modify `frontend/src/index.js` so the imports include `Battles` and the `<Routes>` block includes the new route:

```js
import React from "react";
import ReactDOM from "react-dom";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import TopCards from "./components/TopCards";
import TopDecks from "./components/TopDecks";
import Battles from "./components/Battles";

const root = document.getElementById("root");

ReactDOM.createRoot(root).render(
    <React.StrictMode>
        <BrowserRouter>
            <Routes>
                <Route index element={<App component={TopCards} />} />
                <Route path="decks" element={<App component={TopDecks} />} />
                <Route path="battles" element={<App component={Battles} />} />
            </Routes>
        </BrowserRouter>
    </React.StrictMode>
);

// (existing comments below stay as-is)
reportWebVitals();
```

(Keep the commented-out `ReactDOM.render(...)` block and the `reportWebVitals` comments that were already present — only the imports and the `<Routes>` block change.)

- [ ] **Step 3: Start the dev server**

In a new terminal (or background):
```bash
cd frontend && npm start
```
Wait for `Compiled successfully!` (typically 10-30s on first run). Any compile errors will show here.

- [ ] **Step 4: Browser smoke check — `/battles`**

Open http://localhost:3000/battles in a browser.

Expected:
- 10 numbered "Battle #N" rows.
- Each row shows: a UTC timestamp, both player names + tags, the score (`X – Y`), a "WINNER" label next to the higher-crown player (or "Draw" if equal), and two 2×4 grids of 8 card images.
- Card images for the first two slots show the evolved variant when the card has an evolution.

If the page is blank with a console error like "CORS" or "Failed to fetch", confirm the backend is reachable: `curl -s http://localhost:5001/battles | head -c 200`. If that works but the browser fetch fails, check the browser console for the actual error.

- [ ] **Step 5: Regression check — `/` and `/decks` still work**

In the browser:
- http://localhost:3000/ → existing TopCards page renders.
- http://localhost:3000/decks → existing TopDecks page renders.

If either is broken, revert `index.js` and re-add the route — the only change to `index.js` is the import + one route line.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Battles.js frontend/src/index.js
git commit -m "Add /battles page route and component"
```

---

## Task 7: Production build for nginx

**Files:**
- (none — build artifacts only)

The dockerized stack serves `frontend/build` via nginx. Until you rebuild, only the dev server on `:3000` shows the new route.

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npm run build
```
Expected: `Compiled successfully.` followed by a `File sizes after gzip` table. Build artifacts land in `frontend/build/`.

- [ ] **Step 2: Smoke check via nginx (port 80)**

```bash
curl -sI http://localhost/battles | head -1
```
Expected: `HTTP/1.1 200 OK` (or 301/302 redirect to a known location — depends on nginx config; either is fine as long as it's not 404).

Then in a browser, open http://localhost/battles and confirm the page renders the same as on `:3000`.

- [ ] **Step 3: Decide whether to commit `frontend/build/`**

```bash
git check-ignore -v frontend/build 2>&1 || echo "NOT IGNORED"
```
- If output starts with a `.gitignore` path → build is ignored. Skip the commit; rebuilding is a deployment step, not a code change.
- If output is `NOT IGNORED` → check `git status` for what's new in `frontend/build/`. The existing commits do not include build artifacts based on inspection of the repo before this work; if `git status` shows new build files, do **not** commit them ad hoc — surface this to the user and ask whether to add `frontend/build/` to `.gitignore` instead.

---

## Self-Review Notes

After plan completion, verify against the spec:

- ✅ `recent_battles` table with all 10 columns + composite PK + DESC index → Task 1
- ✅ `get_battle_rows()` filters to pathOfLegend, parses battleTime, builds shared deck shape → Task 2
- ✅ Cron piggy-backs on existing battlelog fetch, idempotent inserts via `ON CONFLICT DO NOTHING` → Task 3
- ✅ `GET /battles` returns 10 latest battles ordered by `battle_time DESC` → Task 4
- ✅ Dedicated `BattleCard` (not the existing `Card`) → Task 5
- ✅ `Battles` page with both decks, name+tag, timestamp, winner indicator (incl. draw) → Task 6
- ✅ Production build step called out for nginx serving → Task 7
- ✅ No regressions to `/` and `/decks` (verified in Task 6 step 5)
- ✅ All tasks end with a manual smoke check before committing
- ✅ No formal unit tests added (matches spec non-goal)
