# Personalized Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a logged-in player overlay their card collection on the existing `/decks` page and see a personal `/player/<tag>` page recommending the top 3 popular meta decks they fully own.

**Architecture:** A single new backend endpoint `GET /player/<tag>` proxies the Clash Royale `/players/<tag>` API, joins the player's collection against the latest `common_decks` snapshot, and returns identity + cards + 3 recommended decks. The frontend stores the player tag in `localStorage`, decorates `/decks` with ownership/level badges (with a toggle), and adds a `/player/:tag` route.

**Tech Stack:** Python 3, Flask-RESTful, psycopg2 (Postgres 17), React 18 class components, react-router v7, Bootstrap 5.1.1, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-05-05-personalized-features-design.md`

**Important codebase conventions:**
- Backend imports are rooted at `backend/` (e.g. `from apis.utils.db_utils import make_connection`, not `backend.apis...`). The Dockerfile sets `WORKDIR /usr/src/` and `PYTHONPATH=/usr/src/cr_stats`.
- The `common_decks` table column is **`decks`** (not `data`). Read pattern is `SELECT decks FROM common_decks ORDER BY timestamp DESC LIMIT 1` then `results[0][0]`.
- All Postgres connections go through `apis.utils.db_utils.make_connection()` used as a context manager.
- Backend tests use `unittest`, run via `docker-compose exec backend python -m unittest <path>`.
- React components are class-based; existing pattern lives in `frontend/src/components/Battles.js` and `TopDecks.js`.
- Frontend dev server runs from `frontend/` via `npm start` (port 3000) and hits `http://localhost:5001` for the API.
- After backend changes, the gunicorn `--reload` flag picks them up automatically (no rebuild). After frontend changes, run `cd frontend && npm run build` for the dockerized stack to pick them up via the nginx bind mount.

---

## File Structure

**New files:**
- `backend/apis/utils/recommendation.py` — pure function `pick_recommended_decks` (filter + rank + slice).
- `backend/apis/player.py` — Flask-RESTful Resource at `/player/<path:tag>`.
- `backend/tests/test_recommendation.py` — unit tests for `pick_recommended_decks`.
- `frontend/src/utils/playerTag.js` — localStorage helpers + custom-event dispatch.
- `frontend/src/components/PlayerTagInput.js` — controlled navbar input.
- `frontend/src/components/Player.js` — `/player/:tag` page.

**Modified files:**
- `backend/app.py` — register the `Player` resource.
- `frontend/src/components/Header.js` — mount `PlayerTagInput` + conditional "My Profile" link.
- `frontend/src/components/Deck.js` — accept optional `ownership` prop.
- `frontend/src/components/TopDecks.js` — fetch player on mount, render overlay toggle, pass `ownership` to `Deck`.
- `frontend/src/index.js` — add `<Route path="player/:tag" ... />`.

---

## Task 1: `pick_recommended_decks` (TDD)

**Files:**
- Create: `backend/apis/utils/recommendation.py`
- Create: `backend/tests/test_recommendation.py`

- [ ] **Step 1: Write the first failing test (full-ownership, ranked by count)**

Create `backend/tests/test_recommendation.py`:

```python
from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_names, count, players=None):
    return {
        "count": count,
        "cards": [{"name": n, "icon": f"{n}.png"} for n in card_names],
        "players": players or [],
    }


class TestPickRecommendedDecks(TestCase):
    def test_full_ownership_ranked_by_count_descending(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [
            _deck(cards, count=3),
            _deck(cards, count=10),
            _deck(cards, count=7),
        ]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, limit=3)

        self.assertEqual([d["count"] for d in result], [10, 7, 3])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker-compose exec -T backend python -m unittest backend.tests.test_recommendation -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apis.utils.recommendation'`.

- [ ] **Step 3: Create the minimal implementation**

Create `backend/apis/utils/recommendation.py`:

```python
def pick_recommended_decks(all_decks, owned_card_names, level_by_name, limit=3):
    """Return the top `limit` decks the player can fully play, ranked by popularity.

    A deck is "playable" iff every card in it is in `owned_card_names`. Each
    returned deck is the original dict augmented with `avg_level` (mean of
    `level_by_name[name]` across the deck's cards, rounded to 1 decimal).
    Sort is stable on `count` descending — ties preserve input order.
    """
    playable = []
    for deck in all_decks:
        names = [c["name"] for c in deck["cards"]]
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        playable.append({**deck, "avg_level": round(avg_level, 1)})
    playable.sort(key=lambda d: d["count"], reverse=True)
    return playable[:limit]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker-compose exec -T backend python -m unittest backend.tests.test_recommendation -v`
Expected: PASS, 1 test ran.

- [ ] **Step 5: Add the remaining tests**

Append to `backend/tests/test_recommendation.py`:

```python
    def test_excludes_decks_missing_any_card(self):
        deck_owned = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        deck_missing = _deck(["A", "B", "C", "D", "E", "F", "G", "Z"], count=99)
        owned = {"A", "B", "C", "D", "E", "F", "G", "H"}
        levels = {n: 14 for n in owned}

        result = pick_recommended_decks([deck_missing, deck_owned], owned, levels, limit=3)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [_deck(cards, count=i) for i in range(1, 11)]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(pick_recommended_decks([], {"A"}, {"A": 14}), [])

    def test_no_owned_cards_returns_empty(self):
        deck = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        self.assertEqual(pick_recommended_decks([deck], set(), {}), [])

    def test_avg_level_computed_and_rounded(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(cards, count=1)
        owned = set(cards)
        # Levels: 14,14,14,14,14,14,14,1 -> mean 12.375 -> rounds to 12.4
        levels = {n: 14 for n in cards}
        levels["H"] = 1

        result = pick_recommended_decks([deck], owned, levels, limit=1)

        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        first = _deck(cards, count=5, players=["#FIRST"])
        second = _deck(cards, count=5, players=["#SECOND"])
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks([first, second], owned, levels, limit=2)

        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])
```

- [ ] **Step 6: Run the full test suite to verify all pass**

Run: `docker-compose exec -T backend python -m unittest backend.tests.test_recommendation -v`
Expected: PASS, 7 tests ran (1 from Step 1 + 6 added in Step 5).

- [ ] **Step 7: Commit**

```bash
git add backend/apis/utils/recommendation.py backend/tests/test_recommendation.py
git commit -m "Add pick_recommended_decks helper"
```

---

## Task 2: `GET /player/<tag>` endpoint

**Files:**
- Create: `backend/apis/player.py`
- Modify: `backend/app.py`

- [ ] **Step 1: Create the resource**

Create `backend/apis/player.py`:

```python
# Python imports
from urllib.parse import quote_plus

# Third party imports
import requests
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.recommendation import pick_recommended_decks
from settings import API_URL, HEADERS


class Player(Resource):
    def get(self, tag):
        # `tag` arrives URL-decoded by Flask (e.g. "#PPJU2YGP0"). The CR API
        # itself wants the leading # encoded as %23, so re-encode here.
        cr = requests.get(
            f"{API_URL}/players/{quote_plus(tag)}",
            headers=HEADERS,
            timeout=10,
        )
        if cr.status_code == 404:
            return {"error": "player not found"}, 404
        if cr.status_code != 200:
            return {"error": "upstream error"}, 502
        player = cr.json()

        cards = player.get("cards", []) or []
        owned_card_names = {c["name"] for c in cards}
        level_by_name = {c["name"]: c["level"] for c in cards}

        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT decks FROM common_decks ORDER BY timestamp DESC LIMIT 1"
                )
                row = cursor.fetchone()
        decks = row[0] if row else []

        recommended = pick_recommended_decks(
            decks, owned_card_names, level_by_name, limit=3
        )

        pol = player.get("currentPathOfLegendSeasonResult") or {}
        return {
            "identity": {
                "name": player.get("name"),
                "tag": player.get("tag"),
                "trophies": player.get("trophies"),
                "pol_rank": pol.get("rank"),
            },
            "cards": [
                {"name": c["name"], "level": c["level"], "maxLevel": c["maxLevel"]}
                for c in cards
            ],
            "recommended_decks": recommended,
        }
```

- [ ] **Step 2: Register the route**

Edit `backend/app.py` — add the import and `add_resource` call so the file looks like:

```python
"""
Get analytics about top players in Clash Royale
"""

# Local imports
from __init__ import create_app
from apis.most_common_cards import MostCommonCards
from apis.most_common_decks import MostCommonDecks
from apis.player import Player
from apis.recent_battles import RecentBattles

# Third party imports
from flask_restful import Api

# Instantiate app
app = create_app()
api = Api(app)
api.add_resource(MostCommonCards, "/cards")
api.add_resource(MostCommonDecks, "/decks")
api.add_resource(RecentBattles, "/battles")
api.add_resource(Player, "/player/<path:tag>")
```

- [ ] **Step 3: Smoke-test the endpoint**

Run (gunicorn `--reload` should already be live):

```bash
curl -s "http://localhost:5001/player/%23PPJU2YGP0" | python -m json.tool | head -40
```

Expected: JSON with top-level keys `identity`, `cards`, `recommended_decks`. `identity.name` should be a string (e.g. `"daimyo"`). `cards` should be a non-empty list. `recommended_decks` may be `[]` or contain up to 3 entries each with `count`, `cards`, `players`, `avg_level`.

If you get HTML/HTTP 500, check `docker-compose logs backend --tail=30`.

- [ ] **Step 4: Smoke-test a bad tag**

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/player/%23ZZZZZZZZ"
```

Expected: `404`.

- [ ] **Step 5: Confirm existing tests still pass**

Run: `docker-compose exec -T backend python -m unittest backend.tests.test_recommendation backend.tests.test_sanity -v`
Expected: PASS, 8 tests ran.

- [ ] **Step 6: Commit**

```bash
git add backend/apis/player.py backend/app.py
git commit -m "Add GET /player/<tag> endpoint"
```

---

## Task 3: `playerTag` localStorage utility

**Files:**
- Create: `frontend/src/utils/playerTag.js`

- [ ] **Step 1: Create the directory**

Run: `mkdir -p frontend/src/utils`

- [ ] **Step 2: Create the helper module**

Create `frontend/src/utils/playerTag.js`:

```js
// Single source of truth for the active player's tag. Stored canonical with
// a leading "#" (e.g. "#PPJU2YGP0"). Components subscribe to "cr-stats-tag-change"
// on `window` so the navbar input and consumers stay in sync without a router-
// level context.

const KEY = "cr_stats_player_tag";
const EVENT_NAME = "cr-stats-tag-change";

export function getPlayerTag() {
    return localStorage.getItem(KEY);
}

export function setPlayerTag(raw) {
    const stripped = (raw || "").trim().replace(/^#/, "");
    if (!stripped) {
        clearPlayerTag();
        return;
    }
    localStorage.setItem(KEY, `#${stripped}`);
    window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearPlayerTag() {
    localStorage.removeItem(KEY);
    window.dispatchEvent(new Event(EVENT_NAME));
}

export function subscribePlayerTag(handler) {
    window.addEventListener(EVENT_NAME, handler);
    return () => window.removeEventListener(EVENT_NAME, handler);
}

export function encodePlayerTag(tag) {
    // The Clash Royale player tag's "#" must be %23 in URLs.
    return encodeURIComponent(tag);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/playerTag.js
git commit -m "Add playerTag localStorage utility"
```

---

## Task 4: Navbar tag input + "My Profile" link

**Files:**
- Create: `frontend/src/components/PlayerTagInput.js`
- Modify: `frontend/src/components/Header.js`

- [ ] **Step 1: Create the input component**

Create `frontend/src/components/PlayerTagInput.js`:

```jsx
import React, { useEffect, useState } from "react";
import {
    clearPlayerTag,
    getPlayerTag,
    setPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

export default function PlayerTagInput() {
    const [value, setValue] = useState(getPlayerTag() || "");

    // Stay in sync if another component clears or sets the tag.
    useEffect(() => subscribePlayerTag(() => setValue(getPlayerTag() || "")), []);

    const commit = () => {
        if (value.trim()) {
            setPlayerTag(value);
        } else {
            clearPlayerTag();
        }
    };

    return (
        <input
            type="text"
            className="form-control form-control-sm"
            style={{ maxWidth: "10rem" }}
            placeholder="#YOURTAG"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    commit();
                    e.target.blur();
                }
            }}
            aria-label="Player tag"
        />
    );
}
```

- [ ] **Step 2: Mount the input in the navbar and add the conditional link**

Replace `frontend/src/components/Header.js` entirely with:

```jsx
import React, { Component } from "react";
import { Link, NavLink } from "react-router";
import PlayerTagInput from "./PlayerTagInput";
import {
    encodePlayerTag,
    getPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

const navLinkClass = ({ isActive }) =>
    "nav-link" + (isActive ? " active" : "");

export default class Header extends Component {
    state = { tag: getPlayerTag() };

    componentDidMount() {
        this.unsubscribe = subscribePlayerTag(() =>
            this.setState({ tag: getPlayerTag() })
        );
    }

    componentWillUnmount() {
        if (this.unsubscribe) this.unsubscribe();
    }

    render() {
        const { tag } = this.state;
        return (
            <header>
                <link
                    href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.1/dist/css/bootstrap.min.css"
                    rel="stylesheet"
                    integrity="sha384-F3w7mX95PdgyTmZZMECAngseQB83DfGTowi0iMjiWaeVhAn4FJkqJByhZMI3AhiU"
                    crossOrigin="anonymous"
                />
                <nav className="navbar navbar-expand-md navbar-dark bg-dark">
                    <div className="container">
                        <Link to="/" className="navbar-brand">
                            Clash Royale Stats
                        </Link>
                        <button
                            className="navbar-toggler"
                            type="button"
                            data-bs-toggle="collapse"
                            data-bs-target="#cr-navmenu"
                            aria-controls="cr-navmenu"
                            aria-expanded="false"
                            aria-label="Toggle navigation"
                        >
                            <span className="navbar-toggler-icon"></span>
                        </button>
                        <div className="collapse navbar-collapse" id="cr-navmenu">
                            <ul className="navbar-nav me-auto">
                                <li className="nav-item">
                                    <NavLink to="/" end className={navLinkClass}>
                                        Cards
                                    </NavLink>
                                </li>
                                <li className="nav-item">
                                    <NavLink to="/decks" className={navLinkClass}>
                                        Decks
                                    </NavLink>
                                </li>
                                <li className="nav-item">
                                    <NavLink to="/battles" className={navLinkClass}>
                                        Battles
                                    </NavLink>
                                </li>
                                {tag && (
                                    <li className="nav-item">
                                        <NavLink
                                            to={`/player/${encodePlayerTag(tag)}`}
                                            className={navLinkClass}
                                        >
                                            My Profile
                                        </NavLink>
                                    </li>
                                )}
                            </ul>
                            <div className="d-flex">
                                <PlayerTagInput />
                            </div>
                        </div>
                    </div>
                </nav>
            </header>
        );
    }
}
```

(Note: `ms-auto` on the `<ul>` was changed to `me-auto` so the input sits on the right.)

- [ ] **Step 3: Build the frontend so the dockerized stack picks up changes**

Run: `cd frontend && npm run build`
Expected: build succeeds. (If running `npm start` for dev instead, the rebuild is automatic.)

- [ ] **Step 4: Manual smoke test**

Open the site (`http://localhost` for dockerized, `http://localhost:3000` for `npm start`):
1. Navbar shows the input on the right and no "My Profile" link.
2. Type `PPJU2YGP0` (no `#`) and press Enter → "My Profile" link appears.
3. Refresh the page → input still shows `#PPJU2YGP0`, "My Profile" still present.
4. Clear the input and tab out → "My Profile" disappears.
5. DevTools → Application → Local Storage → confirm key `cr_stats_player_tag` toggles between `"#PPJU2YGP0"` and absent.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlayerTagInput.js frontend/src/components/Header.js
git commit -m "Add player tag input to navbar"
```

---

## Task 5: `Deck` component gains `ownership` prop

**Files:**
- Modify: `frontend/src/components/Deck.js`

- [ ] **Step 1: Update `Deck.js` to accept and render `ownership`**

Replace `frontend/src/components/Deck.js` entirely with:

```jsx
import React from "react";

// Per-slot variant rule:
// slot 0 = evolution slot, slot 1 = hero (evo as fallback for malformed
// decks), slot 2 = hero or evo (hero default when both unlocked), else regular.
function pickIcon({ slotIndex, icon, evolvedIcon, heroIcon, hasEvolution, hasHero }) {
    if (slotIndex === 0) {
        return hasEvolution && evolvedIcon ? evolvedIcon : icon;
    }
    if (slotIndex === 1 || slotIndex === 2) {
        if (hasHero && heroIcon) return heroIcon;
        if (hasEvolution && evolvedIcon) return evolvedIcon;
    }
    return icon;
}

function ownershipBadge(card, ownership) {
    if (!ownership) return null;
    const info = ownership[card.name];
    if (!info) {
        return (
            <span className="badge bg-danger position-absolute top-0 end-0 m-1">
                Missing
            </span>
        );
    }
    return (
        <span className="badge bg-dark position-absolute top-0 end-0 m-1">
            {info.level}
        </span>
    );
}

export default function Deck({ cards, ownership }) {
    return (
        <div className="row g-2">
            {cards.map((card, idx) => {
                const handleError = (e) => {
                    if (e.target.src !== card.icon) {
                        e.target.src = card.icon;
                    }
                };
                const missing = ownership && !ownership[card.name];
                return (
                    <div key={idx} className="col-3 position-relative">
                        <img
                            src={pickIcon({ ...card, slotIndex: idx })}
                            alt={card.name}
                            className={`img-fluid${missing ? " opacity-25" : ""}`}
                            loading="lazy"
                            decoding="async"
                            onError={handleError}
                        />
                        {ownershipBadge(card, ownership)}
                    </div>
                );
            })}
        </div>
    );
}
```

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Manual sanity check (no functional change yet)**

Open `/decks` and `/battles` — both should look identical to before this change (no `ownership` prop is being passed yet, so the badges/dimming code paths don't activate).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Deck.js
git commit -m "Deck component supports optional ownership overlay"
```

---

## Task 6: `/decks` overlay + toggle

**Files:**
- Modify: `frontend/src/components/TopDecks.js`

- [ ] **Step 1: Replace `TopDecks.js` with the overlay-aware version**

Replace `frontend/src/components/TopDecks.js` entirely with:

```jsx
import React, { Component } from "react";
import Deck from "./Deck";
import {
    encodePlayerTag,
    getPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

const OVERLAY_KEY = "cr_stats_overlay_on";

function readOverlayPref(tag) {
    if (!tag) return false;
    const stored = localStorage.getItem(OVERLAY_KEY);
    if (stored === null) return true; // default ON when a tag is set
    return stored === "1";
}

function writeOverlayPref(on) {
    localStorage.setItem(OVERLAY_KEY, on ? "1" : "0");
}

export default class TopDecks extends Component {
    state = {
        loading: true,
        top_decks: null,
        playerData: null,
        playerError: null,
        playerLoading: false,
        overlayOn: readOverlayPref(getPlayerTag()),
        tag: getPlayerTag(),
    };

    async componentDidMount() {
        this.unsubscribe = subscribePlayerTag(() => {
            const tag = getPlayerTag();
            this.setState(
                {
                    tag,
                    overlayOn: readOverlayPref(tag),
                    playerData: null,
                    playerError: null,
                },
                () => this.fetchPlayer()
            );
        });

        // Decks fetch and player fetch happen in parallel.
        const decksPromise = fetch("http://localhost:5001/decks").then((r) =>
            r.json()
        );
        const [decks] = await Promise.all([decksPromise, this.fetchPlayer()]);
        this.setState({ loading: false, top_decks: decks });
    }

    componentWillUnmount() {
        if (this.unsubscribe) this.unsubscribe();
    }

    async fetchPlayer() {
        const tag = getPlayerTag();
        if (!tag) {
            this.setState({ playerData: null, playerError: null, playerLoading: false });
            return;
        }
        this.setState({ playerLoading: true, playerError: null });
        try {
            const res = await fetch(
                `http://localhost:5001/player/${encodePlayerTag(tag)}`
            );
            if (res.status === 404) {
                this.setState({
                    playerData: null,
                    playerError: "not_found",
                    playerLoading: false,
                });
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const playerData = await res.json();
            this.setState({ playerData, playerError: null, playerLoading: false });
        } catch (err) {
            this.setState({
                playerData: null,
                playerError: err.message,
                playerLoading: false,
            });
        }
    }

    toggleOverlay = () => {
        this.setState(
            (prev) => ({ overlayOn: !prev.overlayOn }),
            () => writeOverlayPref(this.state.overlayOn)
        );
    };

    buildOwnershipMap() {
        const { playerData } = this.state;
        if (!playerData) return null;
        const map = {};
        for (const c of playerData.cards) {
            map[c.name] = { level: c.level, maxLevel: c.maxLevel };
        }
        return map;
    }

    renderControls() {
        const { tag, playerData, playerError, overlayOn } = this.state;
        if (!tag) return null;
        if (playerError === "not_found") {
            return (
                <div className="alert alert-warning py-2 mb-3">
                    Player tag <code>{tag}</code> not found — fix it in the navbar.
                </div>
            );
        }
        if (playerError) {
            return (
                <div className="alert alert-danger py-2 mb-3">
                    Couldn't load player data: {playerError}
                </div>
            );
        }
        if (!playerData) return null;
        return (
            <div className="form-check form-switch mb-3 text-white">
                <input
                    className="form-check-input"
                    type="checkbox"
                    role="switch"
                    id="overlayToggle"
                    checked={overlayOn}
                    onChange={this.toggleOverlay}
                />
                <label className="form-check-label" htmlFor="overlayToggle">
                    Show ownership overlay ({playerData.identity.name})
                </label>
            </div>
        );
    }

    render() {
        if (this.state.loading) {
            return (
                <div className="text-center text-white">Loading API data...</div>
            );
        }
        const decks = [...this.state.top_decks].sort(
            (a, b) => b.count - a.count
        );
        const ownership = this.state.overlayOn ? this.buildOwnershipMap() : null;
        return (
            <div>
                {this.renderControls()}
                {decks.map((deck, idx) => (
                    <div key={idx} className="mb-5 text-white">
                        <div className="mb-2">
                            <span className="fw-bold">Deck #{idx + 1}</span>
                            <span className="text-muted ms-2">
                                used by {deck.count} top{" "}
                                {deck.count === 1 ? "player" : "players"}
                            </span>
                        </div>
                        <Deck cards={deck.cards} ownership={ownership} />
                        <div className="text-muted small mt-2">
                            {deck.players.join(", ")}
                        </div>
                        <hr className="mt-4" />
                    </div>
                ))}
            </div>
        );
    }
}
```

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Manual verification**

1. With **no tag** set: visit `/decks` — page renders exactly as before, no toggle visible.
2. Set tag `#PPJU2YGP0` in navbar → revisit `/decks`. A "Show ownership overlay (daimyo)" toggle appears, on by default. Decks show level badges on owned cards and dim missing cards.
3. Toggle off → badges and dimming disappear; toggle remains where it was. Refresh → overlay is still off.
4. Toggle back on → state persists across refresh.
5. Set bogus tag `#ZZZZZZZZ` → `/decks` shows "Player tag #ZZZZZZZZ not found" warning instead of toggle. Decks still render without overlay.
6. Clear tag from navbar → toggle and warning disappear instantly without page reload.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TopDecks.js
git commit -m "Add ownership overlay to /decks with toggle"
```

---

## Task 7: `/player/:tag` page

**Files:**
- Create: `frontend/src/components/Player.js`
- Modify: `frontend/src/index.js`

- [ ] **Step 1: Create the Player page**

Create `frontend/src/components/Player.js`:

```jsx
import React, { Component } from "react";
import { useParams } from "react-router";
import Deck from "./Deck";
import { encodePlayerTag } from "../utils/playerTag";

function withParams(Component) {
    return function Wrapped(props) {
        const params = useParams();
        return <Component {...props} params={params} />;
    };
}

class Player extends Component {
    state = { loading: true, data: null, error: null, notFound: false };

    componentDidMount() {
        this.load();
    }

    componentDidUpdate(prev) {
        if (prev.params.tag !== this.props.params.tag) {
            this.setState({ loading: true, data: null, error: null, notFound: false });
            this.load();
        }
    }

    async load() {
        const { tag } = this.props.params;
        try {
            const res = await fetch(
                `http://localhost:5001/player/${encodePlayerTag(tag)}`
            );
            if (res.status === 404) {
                this.setState({ loading: false, notFound: true });
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this.setState({ loading: false, data });
        } catch (err) {
            this.setState({ loading: false, error: err.message });
        }
    }

    render() {
        const { loading, data, error, notFound } = this.state;
        if (loading) {
            return <div className="text-center text-white">Loading API data...</div>;
        }
        if (notFound) {
            return (
                <div className="text-center text-white">
                    Player not found — check the tag.
                </div>
            );
        }
        if (error) {
            return (
                <div className="text-center text-white">
                    Couldn't load player data: {error}
                </div>
            );
        }
        const { identity, recommended_decks } = data;
        return (
            <div className="text-white">
                <div className="mb-4">
                    <h2 className="mb-1">{identity.name}</h2>
                    <div className="text-muted">{identity.tag}</div>
                    <div className="mt-2">Trophies: {identity.trophies}</div>
                    {identity.pol_rank != null && (
                        <div>Path of Legend Rank: #{identity.pol_rank}</div>
                    )}
                </div>
                <h4 className="mb-3">Recommended Decks</h4>
                {recommended_decks.length === 0 ? (
                    <div className="text-muted">
                        No full meta deck matches your collection yet.
                    </div>
                ) : (
                    recommended_decks.map((deck, idx) => (
                        <div key={idx} className="mb-5">
                            <div className="mb-2">
                                <span className="fw-bold">Deck #{idx + 1}</span>
                                <span className="text-muted ms-2">
                                    used by {deck.count} top{" "}
                                    {deck.count === 1 ? "player" : "players"}
                                </span>
                                <span className="text-muted ms-2">
                                    · avg level {deck.avg_level}
                                </span>
                            </div>
                            <Deck cards={deck.cards} />
                            <hr className="mt-4" />
                        </div>
                    ))
                )}
            </div>
        );
    }
}

export default withParams(Player);
```

- [ ] **Step 2: Add the route**

Replace `frontend/src/index.js` entirely with:

```jsx
import React from "react";
import ReactDOM from "react-dom";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import TopCards from "./components/TopCards";
import TopDecks from "./components/TopDecks";
import Battles from "./components/Battles";
import Player from "./components/Player";

const root = document.getElementById("root");

ReactDOM.createRoot(root).render(
    <React.StrictMode>
        <BrowserRouter>
            <Routes>
                <Route index element={<App component={TopCards} />} />
                <Route path="decks" element={<App component={TopDecks} />} />
                <Route path="battles" element={<App component={Battles} />} />
                <Route path="player/:tag" element={<App component={Player} />} />
            </Routes>
        </BrowserRouter>
    </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

// Cache Clash Royale card icons via a tiny service worker.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/sw.js")
            .catch((err) => console.error("SW registration failed:", err));
    });
}
```

- [ ] **Step 3: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual verification**

1. With tag `#PPJU2YGP0` set, click "My Profile" in the navbar → lands on `/player/%23PPJU2YGP0`. Page shows name, tag, trophies, and 3 deck blocks (or "No full meta deck matches your collection yet" if applicable). Each deck shows count + avg level.
2. Visit `/player/%23ZZZZZZZZ` directly → shows "Player not found — check the tag." (Confirms the route works without a tag set in localStorage.)
3. Clear tag in navbar → "My Profile" link disappears. Direct URL navigation to `/player/%23PPJU2YGP0` still works (route is independent of localStorage).
4. Verify `/cards`, `/decks`, `/battles` are unaffected by this change.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Player.js frontend/src/index.js
git commit -m "Add /player/:tag page with recommended decks"
```

---

## Done

After Task 7, the feature is complete. Run a final end-to-end pass:

1. Clear localStorage entirely. Visit `/cards`, `/decks`, `/battles`, `/` — all should look identical to pre-feature state.
2. Type `PPJU2YGP0` into the navbar, press Enter.
3. Visit `/decks` — overlay on, badges visible.
4. Toggle overlay off, refresh — toggle stays off.
5. Toggle overlay on, refresh — toggle stays on.
6. Click "My Profile" — `/player/%23PPJU2YGP0` shows identity + 3 recs (or empty-state message).
7. Backend tests: `docker-compose exec -T backend python -m unittest backend.tests.test_recommendation backend.tests.test_sanity -v` — 8 tests, all pass.
