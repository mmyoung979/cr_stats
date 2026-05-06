# Deck Stats Panel Design

**Date:** 2026-05-06

## Goal

Render each deck on `/decks` and `/player/<tag>` in a RoyaleAPI-style two-column layout: deck grid on the left, a small stats panel on the right. v1 stats are **avg elixir** and **4-card cycle**.

## Non-Goals (v1)

- Other stats (win rate, deck name, deck tier, etc.).
- `/battles` layout changes — its winner-on-left two-deck layout doesn't fit the pattern.
- Backend computation of the stats — frontend computes from `cards[].elixirCost`.
- Caching `elixirCost` on the frontend — it's already in the snapshot response.
- Re-tuning column widths if the cards look cramped (easy follow-up).

## Architecture Overview

Two changes:

- **Backend ingestion** — `_battle_deck` and `get_deck_data` in `backend/scripts/utils/data_utils.py` start including `elixirCost` per card. After deploy, run `make update-cards` once to repopulate `common_decks` (cron picks it up daily anyway). No schema change — `cards` is a JSON column.
- **Frontend** — new shared `DeckStats` component takes a `cards` array and renders avg elixir + 4-card cycle. `TopDecks.js` and `Player.js` switch each deck to a Bootstrap row: deck grid in `col-md-9`, `<DeckStats>` in `col-md-3`. Header line ("Deck #N · used by N top players …") stays above the row. Existing per-deck metadata (players list on `/decks`, missing-variants caption on `/player`) stays in the left column.

Stats are computed in the frontend from `cards[].elixirCost`. No new endpoint, no backend math.

## Backend

### `backend/scripts/utils/data_utils.py`

Two functions gain `"elixirCost": card.get("elixirCost")` in their per-card dict.

`_battle_deck` (used by `recent_battles` ingestion):

```python
def _battle_deck(side: dict) -> list[dict]:
    return [
        {
            NAME: card[NAME],
            "hasEvolution": card["iconUrls"].get("evolutionMedium") is not None,
            "hasHero": card["iconUrls"].get("heroMedium") is not None,
            "icon": card["iconUrls"]["medium"],
            "evolvedIcon": card["iconUrls"].get("evolutionMedium"),
            "heroIcon": card["iconUrls"].get("heroMedium"),
            "elixirCost": card.get("elixirCost"),
        }
        for card in side[CARDS]
    ]
```

`get_deck_data` (used by `common_decks` ingestion) gains the same key inside its `CARDS:` list comprehension.

### Deploy steps

After merging:
1. Backend reload picks up the new `data_utils.py` automatically (gunicorn `--reload`).
2. Run `make update-cards` once to repopulate `common_decks` and `recent_battles` snapshots with the new field.
3. Cron continues daily refresh as normal.

No tests change. `data_utils.py` does not have unit tests in this repo. `pick_recommended_decks` does not read `elixirCost`, so its tests stay valid.

## Frontend

### File map

```
frontend/src/components/
├── DeckStats.js             (new)
├── TopDecks.js              (mod)
└── Player.js                (mod)
```

### `DeckStats.js`

Pure component, defensive against missing `elixirCost` (snapshots not yet refreshed):

```jsx
import React from "react";

function avgElixir(cards) {
    const costs = cards.map((c) => c.elixirCost).filter((x) => typeof x === "number");
    if (costs.length === 0) return null;
    return (costs.reduce((a, b) => a + b, 0) / costs.length).toFixed(1);
}

function fourCardCycle(cards) {
    const costs = cards.map((c) => c.elixirCost).filter((x) => typeof x === "number");
    if (costs.length < 4) return null;
    const cheapest = [...costs].sort((a, b) => a - b).slice(0, 4);
    return cheapest.reduce((a, b) => a + b, 0).toFixed(1);
}

export default function DeckStats({ cards }) {
    const avg = avgElixir(cards);
    const cycle = fourCardCycle(cards);
    return (
        <div className="text-white">
            <div>Avg elixir: {avg ?? "—"}</div>
            <div>4-card cycle: {cycle ?? "—"}</div>
        </div>
    );
}
```

The avg uses card count (typically 8). The 4-card cycle is the sum of the 4 cheapest cards' elixir costs (the minimum elixir to play four cards once each, getting back to a key card).

### `TopDecks.js`

Inside the existing `decks.map(...)` block, wrap the deck grid + players list in a Bootstrap row and add the stats column. The full updated block:

```jsx
{decks.map((deck, idx) => (
    <div key={idx} className="mb-5 text-white">
        <div className="mb-2">
            <span className="fw-bold">Deck #{idx + 1}</span>
            <span className="text-muted ms-2">
                used by {deck.count} top{" "}
                {deck.count === 1 ? "player" : "players"}
            </span>
        </div>
        <div className="row">
            <div className="col-md-9">
                <Deck cards={deck.cards} ownership={ownership} />
                <div className="text-muted small mt-2">
                    {deck.players.join(", ")}
                </div>
            </div>
            <div className="col-md-3">
                <DeckStats cards={deck.cards} />
            </div>
        </div>
        <hr className="mt-4" />
    </div>
))}
```

Add `import DeckStats from "./DeckStats";` at the top.

### `Player.js`

Inside the existing `recommended_decks.map(...)` block, wrap the missing-variants caption + deck grid in a `col-md-9` and add the stats column. The full updated block:

```jsx
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
        <div className="row">
            <div className="col-md-9">
                {deck.missing_variants.length > 0 && (
                    <div className="small text-warning mb-2">
                        Missing:{" "}
                        {deck.missing_variants
                            .map((m) => `${m.variant === "hero" ? "hero" : "evo"} ${m.name}`)
                            .join(", ")}
                    </div>
                )}
                <Deck cards={deck.cards} />
            </div>
            <div className="col-md-3">
                <DeckStats cards={deck.cards} />
            </div>
        </div>
        <hr className="mt-4" />
    </div>
))
```

Add `import DeckStats from "./DeckStats";` at the top.

`/battles` is unchanged.

## Edge Cases

| Case | Behavior |
|---|---|
| Old snapshot rows without `elixirCost` (pre-refresh) | `DeckStats` shows `—` for both numbers. Self-corrects on next refresh. |
| Card with `elixirCost: 0` (Mirror, Heal Spirit) | `typeof x === "number"` passes 0 → included in avg and cycle. |
| Deck has fewer than 4 priced cards | `4-card cycle: —` (avg still renders if any prices exist). |
| Mobile (< `md` breakpoint) | Bootstrap stacks columns; stats appear below the deck. |
| `/battles` page | Unaffected. |

## Testing

**Automated:** none. `data_utils.py` has no existing tests (consistent with current repo). Frontend has no test infrastructure.

**Manual verification** after deploy + `make update-cards`:
- Visit `/decks` — each deck shows two-column layout with avg elixir + 4-card cycle on the right.
- Visit `/player/%23PPJU2YGP0` — same layout. Missing-variants caption still appears above the deck inside the left column.
- Resize viewport to mobile width — stats column drops below the deck.
- Cards still render at reasonable size in `col-md-9` (~75% of previous width).
- `/battles` looks unchanged.
