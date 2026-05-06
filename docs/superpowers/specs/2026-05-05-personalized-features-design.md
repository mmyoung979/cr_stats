# Personalized Features Design

**Date:** 2026-05-05

## Goal

Let a logged-in player see the meta through the lens of their own collection: which top decks they can actually play (overlaid on `/decks`) and a personal page (`/player/<tag>`) recommending the three most popular meta decks they fully own.

## Non-Goals (v1)

- Server-side caching of Clash Royale API responses
- Hero/evolution unlock indicators in the overlay (base ownership is sufficient — if you own the card you can play the slot)
- "Compare two players" views
- Persisted recommendations (recomputed on every page load)
- Showing the player's current deck or a full collection grid on `/player/<tag>`
- Any account / auth concept — the tag in `localStorage` is the entire identity model

## Architecture Overview

A new "personalized" layer that opts in once a player tag is set:

- **Navbar tag input** persists the tag to `localStorage` under `cr_stats_player_tag`. All other pages read it and decorate themselves when present.
- **One backend endpoint** — `GET /player/<urlEncodedTag>` — proxies the Clash Royale `/players/<tag>` API, joins the player's collection against the latest `common_decks` snapshot, and returns `{ identity, cards, recommended_decks }`.
- **`/decks` page** uses `.cards` to overlay ownership + level badges on each card, with a toggle to suppress.
- **`/player/<tag>` page** is a new route rendering the identity header + the 3 recommended decks via the existing `Deck` component.

No new tables, no cron changes, no schema migration. The `common_decks` snapshot is the single source of meta-deck truth; player data is always live.

## Backend

### New endpoint: `GET /player/<path:tag>`

Lives in **`backend/apis/player.py`** as a Flask-RESTful Resource. The CR API is the source of truth for player data; we never persist it.

```python
class Player(Resource):
    def get(self, tag):
        cr = requests.get(f"{API_URL}/players/{quote_plus(tag)}", headers=HEADERS)
        if cr.status_code == 404:
            return {"error": "player not found"}, 404
        if cr.status_code != 200:
            return {"error": "upstream error"}, 502
        player = cr.json()

        owned_card_names = {c["name"] for c in player.get("cards", [])}
        level_by_name = {c["name"]: c["level"] for c in player.get("cards", [])}

        with make_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM common_decks ORDER BY timestamp DESC LIMIT 1")
            row = cur.fetchone()
        decks = row[0] if row else []

        recommended = pick_recommended_decks(decks, owned_card_names, level_by_name, limit=3)

        return {
            "identity": {
                "name": player.get("name"),
                "tag": player.get("tag"),
                "trophies": player.get("trophies"),
                "pol_rank": (player.get("currentPathOfLegendSeasonResult") or {}).get("rank"),
            },
            "cards": [
                {"name": c["name"], "level": c["level"], "maxLevel": c["maxLevel"]}
                for c in player.get("cards", [])
            ],
            "recommended_decks": recommended,
        }
```

Response shape:

```json
{
  "identity": {
    "name": "daimyo",
    "tag": "#PPJU2YGP0",
    "trophies": 7234,
    "pol_rank": 142
  },
  "cards": [
    { "name": "Furnace", "level": 13, "maxLevel": 14 }
  ],
  "recommended_decks": [
    {
      "count": 12,
      "cards": [ { "name": "...", "icon": "...", "hasEvolution": true, ... } ],
      "players": ["#ABC", "#DEF"],
      "avg_level": 13.5
    }
  ]
}
```

Imports follow project convention (rooted at `backend/`):
```python
from apis.utils.db_utils import make_connection
from apis.utils.recommendation import pick_recommended_decks
from settings import API_URL, HEADERS
```

### New helper: `pick_recommended_decks`

Lives in **`backend/apis/utils/recommendation.py`** as a pure function so it can be unit-tested without DB or HTTP.

```python
def pick_recommended_decks(all_decks, owned_card_names, level_by_name, limit=3):
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

### Wiring

**`backend/app.py`** registers `Player` at `/player/<path:tag>`. The `path:` converter accepts forward slashes and (after URL decoding by Flask) the leading `#` arrives intact when sent encoded as `%23`.

## Frontend

### File map

```
frontend/src/
├── utils/playerTag.js          (new)
├── components/
│   ├── Header.js               (mod)  — add PlayerTagInput + "My Profile" NavLink
│   ├── PlayerTagInput.js       (new)  — controlled input, persists on change
│   ├── Deck.js                 (mod)  — accept optional `ownership` prop
│   ├── TopDecks.js             (mod)  — fetch player on mount, render overlay toggle
│   └── Player.js               (new)  — /player/:tag page
└── index.js                    (mod)  — add `<Route path="player/:tag" ... />`
```

### `utils/playerTag.js`

Single source for tag storage. Normalizes input (strips a leading `#`, then prepends one) so we always store the canonical form `#PPJU2YGP0`.

```js
const KEY = "cr_stats_player_tag";

export const getPlayerTag = () => localStorage.getItem(KEY);

export const setPlayerTag = (raw) => {
    const stripped = raw.trim().replace(/^#/, "");
    localStorage.setItem(KEY, `#${stripped}`);
};

export const clearPlayerTag = () => localStorage.removeItem(KEY);
```

### `Deck.js` — gain optional `ownership` prop

Existing call sites stay unchanged (`<Deck cards={...} />`). When `ownership` is supplied as a `{ [cardName]: { level, maxLevel } }` map (only for owned cards):

- Owned cards render a small dark badge in the corner showing `level` (e.g., `13`).
- Missing cards (key absent in `ownership`) render a `"Missing"` badge and the icon at `opacity-25`.
- The card wrapper becomes `position-relative` so badges can be `position-absolute`.

```jsx
function ownershipBadge(card, ownership) {
    if (!ownership) return null;
    const info = ownership[card.name];
    if (!info) {
        return <span className="badge bg-danger position-absolute top-0 end-0">Missing</span>;
    }
    return <span className="badge bg-dark position-absolute top-0 end-0">{info.level}</span>;
}
```

### `TopDecks.js` — overlay + toggle

On mount, if `getPlayerTag()` returns a tag, fetch `http://localhost:5001/player/<encoded>` and stash the response. Build `ownershipMap = { [card.name]: { level, maxLevel } }` from `response.cards`.

State adds:
- `overlayOn` — boolean, initialized from `localStorage.cr_stats_overlay_on` (default `true` when a tag exists, `false` otherwise).
- `playerData` / `playerError` — for the fetch.

Render an "Overlay" form-switch above the deck list when `playerData` is loaded; toggling persists to `localStorage`. Pass `ownership={overlayOn ? ownershipMap : undefined}` to each `<Deck>`.

If the fetch returns 404 (invalid tag), render a small dismissible banner above the deck list: *"Player tag '<tag>' not found — fix it in the navbar."* — and skip the overlay.

### `Player.js` (new)

Class component, since we need React 7's `useParams` we wrap with a small functional shim:

```jsx
function withParams(Component) {
    return (props) => <Component {...props} params={useParams()} />;
}
```

`componentDidMount` fetches `http://localhost:5001/player/<encoded params.tag>`. Renders:

- **Header** — `<h2>{name}</h2>`, muted tag, then `Trophies: N` and `Path of Legend Rank: #N` (only when `pol_rank` is non-null).
- **Three deck blocks** — each `<Deck cards={d.cards} />` preceded by `Avg level: X.Y` and `Used by N top players`.
- **Empty case** — when `recommended_decks` is `[]`, show *"No full meta deck matches your collection yet."*
- **Loading / not-found / error** states mirror `Battles.js`.

Exported as `withParams(Player)`.

### `Header.js`

Adds a `<PlayerTagInput />` to the right of the existing nav links and a "My Profile" `<NavLink>` that:
- Is hidden when no tag is set.
- Links to `/player/<encoded tag>` when a tag is set.

`PlayerTagInput` is a controlled `<input>` initialized from `getPlayerTag()`. On blur or Enter, calls `setPlayerTag` (or `clearPlayerTag` when emptied). Triggers a top-level re-render via a small `useState` + `window.dispatchEvent(new Event("cr-stats-tag-change"))` pattern; `Header` and consumers listen on the event so navbar + page sync without a router-level context.

### `index.js`

```jsx
<Route path="player/:tag" element={<App component={Player} />} />
```

## Edge Cases

| Case | Where | Behavior |
|---|---|---|
| Tag pasted without `#` | `setPlayerTag` | Normalized on save: stripped, then prepended. |
| Invalid tag (CR returns 404) | Backend → 404 | `/player/:tag` shows "Player not found." `/decks` shows a dismissible banner and renders without overlay. |
| CR API 5xx / rate limit | Backend → 502 | Both pages show "Couldn't load player data — Clash Royale API is unavailable." No retry/backoff in v1. |
| Player owns no full meta deck | `recommended_decks: []` | `/player` shows "No full meta deck matches your collection yet." |
| `common_decks` empty (fresh DB) | Backend returns `recommended_decks: []` | Same UX as above. |
| Player has no PoL rank | `pol_rank: null` | Identity header omits the rank line. |
| User clears tag mid-session | `clearPlayerTag` + event | "My Profile" link disappears; `TopDecks` drops overlay. `/player/:tag` URLs are still navigable directly. |
| Tag set but page doesn't read it | `/cards`, `/battles` | No-op. They never read the tag. |

## Testing

**Automated** — `backend/tests/test_recommendation.py` covers `pick_recommended_decks`:
- Full-meta-owned → returned, ranked by `count` descending.
- Missing one card → excluded.
- Player owns multiple playable decks → top `limit` returned.
- Empty `all_decks` → `[]`.
- Empty `owned_card_names` → `[]`.
- Tie on `count` → stable order (input order preserved).

No frontend tests (consistent with current repo).

**Manual verification checklist** (after each major task):
- Set tag `#PPJU2YGP0` in navbar → tag persists across refresh.
- Visit `/decks` → each deck shows level badges on owned cards, dimmed icons on missing cards. Toggle off → badges/dimming disappear; toggle persists across refresh.
- Visit `/player/%23PPJU2YGP0` → header + 3 deck blocks render.
- Set bogus tag `#ZZZZZZZZ` → `/decks` shows banner, `/player/...` shows "not found."
- Clear tag → "My Profile" link disappears; `/decks` overlay disappears; `/cards` and `/battles` unaffected.
