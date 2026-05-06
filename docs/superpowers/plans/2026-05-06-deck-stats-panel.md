# Deck Stats Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render each deck on `/decks` and `/player/<tag>` in a two-column layout — deck grid on the left, a stats panel (avg elixir + 4-card cycle) on the right.

**Architecture:** Backend ingestion (`_battle_deck` and `get_deck_data` in `data_utils.py`) starts including `elixirCost` per card. A new shared `DeckStats` React component computes both stats from the cards array. `TopDecks.js` and `Player.js` wrap their deck grids in a Bootstrap `row` (`col-md-9` deck, `col-md-3` stats).

**Tech Stack:** Python 3, React 18 class components, Bootstrap 5.1.1, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-05-06-deck-stats-panel-design.md`

**Important codebase conventions:**
- Backend imports rooted at `backend/`.
- The `common_decks` table column is `decks` (JSON), `recent_battles.team_deck` / `opp_deck` are JSON. Adding a per-card field is additive (no migration).
- After backend ingestion changes, run `make update-cards` once to repopulate snapshots. Cron picks it up daily anyway.
- Frontend has no test infrastructure.
- Build the frontend with `cd frontend && npm run build` after JS changes.
- Working directory: `/Users/matthewyoung/Documents/GitHub/cr_stats`. Committing to master.

---

## File Structure

**New files:**
- `frontend/src/components/DeckStats.js` — pure component: takes `cards`, renders avg elixir + 4-card cycle.

**Modified files:**
- `backend/scripts/utils/data_utils.py` — `_battle_deck` and `get_deck_data` per-card dict gain `"elixirCost": card.get("elixirCost")`.
- `frontend/src/components/TopDecks.js` — wrap deck grid + players list in `col-md-9`, add `<DeckStats>` in `col-md-3`.
- `frontend/src/components/Player.js` — wrap missing-variants caption + deck grid in `col-md-9`, add `<DeckStats>` in `col-md-3`.

---

## Task 1: Backend — add `elixirCost` to ingestion

**Files:**
- Modify: `backend/scripts/utils/data_utils.py`

- [ ] **Step 1: Edit `_battle_deck`**

In `backend/scripts/utils/data_utils.py`, find `_battle_deck`. Add the `"elixirCost": card.get("elixirCost"),` line at the end of the per-card dict. The full function should be:

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

- [ ] **Step 2: Edit `get_deck_data`**

In the same file, find the per-card dict inside `get_deck_data` (the `CARDS:` list comprehension). Add the same `"elixirCost": card.get("elixirCost"),` line. The relevant comprehension should become:

```python
            deck_data[deck_hash] = {
                COUNT: 0,
                CARDS: [
                    {
                        NAME: card[NAME],
                        "hasEvolution": card["iconUrls"].get("evolutionMedium") is not None,
                        "hasHero": card["iconUrls"].get("heroMedium") is not None,
                        "icon": card["iconUrls"]["medium"],
                        "evolvedIcon": card["iconUrls"].get("evolutionMedium"),
                        "heroIcon": card["iconUrls"].get("heroMedium"),
                        "elixirCost": card.get("elixirCost"),
                    }
                    for card in deck
                ],
                "players": [],
            }
```

- [ ] **Step 3: Run existing backend tests to make sure nothing broke**

```bash
docker-compose exec -T backend python -m unittest tests.test_recommendation tests.test_variants tests.test_sanity -v
```

Expected: 28 tests pass.

- [ ] **Step 4: Repopulate the snapshot**

```bash
make update-cards
```

Expected: command runs to completion (a few seconds). The latest row in `common_decks` and any new rows in `recent_battles` now have `elixirCost` per card.

- [ ] **Step 5: Smoke-test the API**

```bash
curl -s http://localhost:5001/decks | python -m json.tool | head -30
```

Expected: each deck's `cards[]` entries include `"elixirCost": <int>`.

```bash
curl -s "http://localhost:5001/player/%23PPJU2YGP0" | python -m json.tool | head -50
```

Expected: same — each card in `recommended_decks[i].cards[]` includes `elixirCost`.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/utils/data_utils.py
git commit -m "Include elixirCost in ingested deck snapshots"
```

---

## Task 2: Frontend — `DeckStats` component

**Files:**
- Create: `frontend/src/components/DeckStats.js`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/DeckStats.js`:

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

- [ ] **Step 2: Build the frontend**

```bash
cd frontend && npm run build
```

Expected: build succeeds (warnings OK).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DeckStats.js
git commit -m "Add DeckStats component (avg elixir + 4-card cycle)"
```

---

## Task 3: Frontend — `/decks` two-column layout

**Files:**
- Modify: `frontend/src/components/TopDecks.js`

- [ ] **Step 1: Add the import**

At the top of `frontend/src/components/TopDecks.js`, after the existing `import Deck from "./Deck";` line, add:

```jsx
import DeckStats from "./DeckStats";
```

- [ ] **Step 2: Wrap the deck grid in a two-column row**

In the `render()` method, find the `decks.map(...)` block. Replace the existing per-deck JSX (the block that renders `<Deck cards={deck.cards} ownership={ownership} />` plus the players list and the `<hr>`) so the deck and stats sit in a Bootstrap row.

The full updated block should be:

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

Don't change anything else in the file.

- [ ] **Step 3: Build the frontend**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TopDecks.js
git commit -m "Render /decks with two-column deck + stats layout"
```

---

## Task 4: Frontend — `/player/<tag>` two-column layout

**Files:**
- Modify: `frontend/src/components/Player.js`

- [ ] **Step 1: Add the import**

At the top of `frontend/src/components/Player.js`, after `import Deck from "./Deck";`, add:

```jsx
import DeckStats from "./DeckStats";
```

- [ ] **Step 2: Wrap the deck grid in a two-column row**

In the `render()` method, find the `recommended_decks.map(...)` block. Replace the inner per-deck JSX so the missing-variants caption and deck grid live in a `col-md-9` and the new `<DeckStats>` lives in a `col-md-3`.

The full updated block should be:

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

Don't change anything else in the file.

- [ ] **Step 3: Build the frontend**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Player.js
git commit -m "Render /player decks with two-column deck + stats layout"
```

---

## Done

After Task 4, the feature is complete. Run a final end-to-end pass:

1. Backend tests: `docker-compose exec -T backend python -m unittest tests.test_recommendation tests.test_variants tests.test_sanity -v` — 28 tests pass.
2. Visit `/decks`:
   - Each deck renders with the deck grid on the left and a stats panel on the right showing "Avg elixir: X.X" and "4-card cycle: Y.Y".
   - Players list still appears below the deck grid in the left column.
3. Visit `/player/%23PPJU2YGP0`:
   - Same two-column layout. Missing-variants caption (when present) renders inside the left column above the deck.
4. Resize the viewport to mobile width (< 768px) — the stats column drops below the deck.
5. `/battles` is unchanged.
