# Variant-Aware Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/player/<tag>` recommendations and the `/decks` overlay respect per-slot variant unlocks (evolution and hero) by reading the `evolutionLevel` bitfield (`1`=evo, `2`=hero, `3`=both) from each card. Decks the player can't fully play (missing variants in slots 0/1/2) get demoted and labeled.

**Architecture:** A new pure module `apis/utils/variants.py` (mirrored as `frontend/src/utils/variants.js`) holds the per-slot variant rule and bitmask check. `pick_recommended_decks` gains a `evolution_level_by_name` parameter and returns each deck with new `fully_playable` and `missing_variants` fields, sorted by `(fully_playable desc, count desc)`. `/player/<tag>` exposes `evolutionLevel` per card. `Deck.js` gains a yellow "no evo" / "no hero" badge state for the overlay. `Player.js` renders a caption listing missing variants per deck.

**Tech Stack:** Python 3, Flask-RESTful, psycopg2 (Postgres 17), React 18 class components, react-router v7, Bootstrap 5.1.1, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-05-06-variant-aware-recommendations-design.md`

**Important codebase conventions:**
- Backend imports are rooted at `backend/` (e.g. `from apis.utils.recommendation import pick_recommended_decks`).
- Backend tests use `unittest`, run via `docker-compose exec -T backend python -m unittest <path>`. Use `tests.test_<name>` (not `backend.tests.test_<name>`) — the WORKDIR is `/usr/src/`, so `tests/` is on the path directly.
- The `common_decks` table column is `decks` (not `data`).
- Frontend has no test infrastructure.
- Build the frontend with `cd frontend && npm run build` after JS changes (the dockerized nginx serves `frontend/build` via bind mount).
- Working directory: `/Users/matthewyoung/Documents/GitHub/cr_stats`. Committing to master (the user has consented to this throughout the session).
- Gunicorn `--reload` picks up backend changes automatically.

---

## File Structure

**New files:**
- `backend/apis/utils/variants.py` — `slot_active_variant`, `is_variant_unlocked`, plus `EVO_BIT`/`HERO_BIT` constants.
- `backend/tests/test_variants.py` — unit tests for the rule.
- `frontend/src/utils/variants.js` — JS mirror: `activeSlotVariant`, `isVariantUnlocked`.

**Modified files:**
- `backend/apis/utils/recommendation.py` — add `evolution_level_by_name` parameter, compute `fully_playable` + `missing_variants` per deck, change sort key.
- `backend/tests/test_recommendation.py` — update all existing call sites for the new signature; add new tests for variant behavior.
- `backend/apis/player.py` — build `evolution_level_by_name`, pass to function, expose `evolutionLevel` per card.
- `frontend/src/components/Deck.js` — `ownership` map now expects `evolutionLevel`; badge gains yellow "no evo"/"no hero" state.
- `frontend/src/components/TopDecks.js` — `buildOwnershipMap` includes `evolutionLevel`.
- `frontend/src/components/Player.js` — render "Missing: ..." caption for non-fully-playable decks.

---

## Task 1: `variants.py` module + tests (TDD)

**Files:**
- Create: `backend/apis/utils/variants.py`
- Create: `backend/tests/test_variants.py`

- [ ] **Step 1: Write the first failing test**

Create `backend/tests/test_variants.py`:

```python
from unittest import TestCase

from apis.utils.variants import is_variant_unlocked, slot_active_variant


class TestSlotActiveVariant(TestCase):
    def test_slot_0_with_evolution_returns_evolution(self):
        self.assertEqual(slot_active_variant(0, True, False), "evolution")

    def test_slot_0_without_evolution_returns_none(self):
        self.assertIsNone(slot_active_variant(0, False, False))
        self.assertIsNone(slot_active_variant(0, False, True))

    def test_slot_1_with_hero_returns_hero(self):
        self.assertEqual(slot_active_variant(1, False, True), "hero")
        self.assertEqual(slot_active_variant(1, True, True), "hero")

    def test_slot_1_with_evo_only_returns_evolution(self):
        self.assertEqual(slot_active_variant(1, True, False), "evolution")

    def test_slot_1_with_neither_returns_none(self):
        self.assertIsNone(slot_active_variant(1, False, False))

    def test_slot_2_matches_slot_1_logic(self):
        self.assertEqual(slot_active_variant(2, False, True), "hero")
        self.assertEqual(slot_active_variant(2, True, False), "evolution")
        self.assertIsNone(slot_active_variant(2, False, False))

    def test_slots_3_to_7_always_none(self):
        for idx in range(3, 8):
            self.assertIsNone(slot_active_variant(idx, True, True))


class TestIsVariantUnlocked(TestCase):
    def test_no_variant_required_always_true(self):
        self.assertTrue(is_variant_unlocked(0, None))
        self.assertTrue(is_variant_unlocked(None, None))
        self.assertTrue(is_variant_unlocked(3, None))

    def test_none_evolution_level_means_nothing_unlocked(self):
        self.assertFalse(is_variant_unlocked(None, "evolution"))
        self.assertFalse(is_variant_unlocked(None, "hero"))

    def test_zero_evolution_level_means_nothing_unlocked(self):
        self.assertFalse(is_variant_unlocked(0, "evolution"))
        self.assertFalse(is_variant_unlocked(0, "hero"))

    def test_evolution_level_1_is_evo_only(self):
        self.assertTrue(is_variant_unlocked(1, "evolution"))
        self.assertFalse(is_variant_unlocked(1, "hero"))

    def test_evolution_level_2_is_hero_only(self):
        self.assertFalse(is_variant_unlocked(2, "evolution"))
        self.assertTrue(is_variant_unlocked(2, "hero"))

    def test_evolution_level_3_is_both(self):
        self.assertTrue(is_variant_unlocked(3, "evolution"))
        self.assertTrue(is_variant_unlocked(3, "hero"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose exec -T backend python -m unittest tests.test_variants -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apis.utils.variants'`.

- [ ] **Step 3: Create the implementation**

Create `backend/apis/utils/variants.py`:

```python
EVO_BIT = 1
HERO_BIT = 2


def slot_active_variant(slot_idx, has_evolution, has_hero):
    """Which variant the deck slot is using. Returns 'evolution', 'hero', or None.

    Slot 0 is the evolution slot. Slot 1 is the hero slot (with evolution as a
    fallback). Slot 2 is hero or evolution (hero default when both unlocked).
    Slots 3-7 carry no variant.
    """
    if slot_idx == 0:
        return "evolution" if has_evolution else None
    if slot_idx in (1, 2):
        if has_hero:
            return "hero"
        if has_evolution:
            return "evolution"
    return None


def is_variant_unlocked(evolution_level, variant):
    """Bitmask check on `evolution_level`. None or 0 means nothing unlocked.

    `variant` is 'evolution', 'hero', or None. None always returns True.
    """
    if variant is None:
        return True
    bit = HERO_BIT if variant == "hero" else EVO_BIT
    return bool((evolution_level or 0) & bit)
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `docker-compose exec -T backend python -m unittest tests.test_variants -v`
Expected: PASS, 13 tests ran.

- [ ] **Step 5: Commit**

```bash
git add backend/apis/utils/variants.py backend/tests/test_variants.py
git commit -m "Add slot_active_variant and is_variant_unlocked helpers"
```

---

## Task 2: Update `pick_recommended_decks` for variants

**Files:**
- Modify: `backend/apis/utils/recommendation.py`
- Modify: `backend/tests/test_recommendation.py`

- [ ] **Step 1: Update existing tests for new signature**

Replace `backend/tests/test_recommendation.py` entirely with:

```python
from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_names, count, players=None, variants=None):
    """Build a deck dict like the snapshot stored in common_decks.

    `variants` is an optional list of (has_evolution, has_hero) tuples per slot.
    Defaults to (False, False) for every slot, i.e. no variants required.
    """
    if variants is None:
        variants = [(False, False)] * len(card_names)
    return {
        "count": count,
        "cards": [
            {
                "name": n,
                "icon": f"{n}.png",
                "hasEvolution": ev,
                "hasHero": hero,
            }
            for n, (ev, hero) in zip(card_names, variants)
        ],
        "players": players or [],
    }


def _no_variants(card_names):
    return {n: 0 for n in card_names}


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

        result = pick_recommended_decks(decks, owned, levels, _no_variants(cards), limit=3)

        self.assertEqual([d["count"] for d in result], [10, 7, 3])

    def test_excludes_decks_missing_any_card(self):
        deck_owned = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        deck_missing = _deck(["A", "B", "C", "D", "E", "F", "G", "Z"], count=99)
        owned = {"A", "B", "C", "D", "E", "F", "G", "H"}
        levels = {n: 14 for n in owned}

        result = pick_recommended_decks(
            [deck_missing, deck_owned], owned, levels, _no_variants(owned), limit=3
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [_deck(cards, count=i) for i in range(1, 11)]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, _no_variants(cards), limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(
            pick_recommended_decks([], {"A"}, {"A": 14}, {"A": 0}), []
        )

    def test_no_owned_cards_returns_empty(self):
        deck = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        self.assertEqual(pick_recommended_decks([deck], set(), {}, {}), [])

    def test_avg_level_computed_and_rounded(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(cards, count=1)
        owned = set(cards)
        # Levels: 14,14,14,14,14,14,14,1 -> mean 12.375 -> rounds to 12.4
        levels = {n: 14 for n in cards}
        levels["H"] = 1

        result = pick_recommended_decks([deck], owned, levels, _no_variants(cards), limit=1)

        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        first = _deck(cards, count=5, players=["#FIRST"])
        second = _deck(cards, count=5, players=["#SECOND"])
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(
            [first, second], owned, levels, _no_variants(cards), limit=2
        )

        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])

    def test_deck_with_empty_cards_is_skipped(self):
        empty = {"count": 99, "cards": [], "players": []}
        self.assertEqual(
            pick_recommended_decks([empty], {"A"}, {"A": 14}, {"A": 0}), []
        )

    def test_fully_playable_when_all_variants_unlocked(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Slot 0 needs evo, slot 1 needs hero.
        deck = _deck(
            cards,
            count=5,
            variants=[(True, False), (False, True), (False, False), (False, False),
                      (False, False), (False, False), (False, False), (False, False)],
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}
        evos["A"] = 1  # evo bit
        evos["B"] = 2  # hero bit

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_missing_evo_variant_reported(self):
        cards = ["RG", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(
            cards,
            count=5,
            variants=[(True, False)] + [(False, False)] * 7,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # RG evo NOT unlocked

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "RG", "slot": 0, "variant": "evolution"}],
        )

    def test_missing_hero_variant_reported(self):
        cards = ["A", "Bowler", "C", "D", "E", "F", "G", "H"]
        deck = _deck(
            cards,
            count=5,
            variants=[(False, False), (False, True)] + [(False, False)] * 6,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # Bowler hero NOT unlocked

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "Bowler", "slot": 1, "variant": "hero"}],
        )

    def test_partially_playable_demoted_below_fully_playable(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Partial deck: count=99 but slot 0 needs evo we lack.
        partial = _deck(
            cards,
            count=99,
            variants=[(True, False)] + [(False, False)] * 7,
            players=["#PARTIAL"],
        )
        # Full deck: count=5, no variants required.
        full = _deck(cards, count=5, players=["#FULL"])
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # No variants unlocked

        result = pick_recommended_decks([partial, full], owned, levels, evos, limit=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["players"], ["#FULL"])
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[1]["players"], ["#PARTIAL"])
        self.assertFalse(result[1]["fully_playable"])

    def test_slots_3_through_7_dont_trigger_variant_check(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # All slots have hasEvolution=True, but only slot 0 should trigger a check.
        deck = _deck(cards, count=5, variants=[(True, False)] * 8)
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}
        evos["A"] = 1  # Slot 0 evo unlocked

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_evolution_level_3_satisfies_both_slots(self):
        cards = ["Wizard", "B", "C", "D", "E", "F", "G", "H"]
        # Same card in slot 0 (needs evo) and (hypothetically) implied hero
        # via a second deck — verify the bitmask check.
        evo_deck = _deck(
            cards, count=5, variants=[(True, True)] + [(False, False)] * 7
        )
        hero_deck = _deck(
            ["B", "Wizard", "C", "D", "E", "F", "G", "H"],
            count=4,
            variants=[(False, False), (True, True)] + [(False, False)] * 6,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}
        evos["Wizard"] = 3  # Both variants unlocked

        result = pick_recommended_decks(
            [evo_deck, hero_deck], owned, levels, evos, limit=2
        )

        self.assertTrue(result[0]["fully_playable"])
        self.assertTrue(result[1]["fully_playable"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose exec -T backend python -m unittest tests.test_recommendation -v`
Expected: FAIL — the existing function has the old signature, so all 14 tests will fail with `TypeError` about positional args, except `test_empty_deck_list_returns_empty` and similar that may produce other errors. Some tests will additionally check for `fully_playable` / `missing_variants` keys that don't yet exist.

- [ ] **Step 3: Update the implementation**

Replace `backend/apis/utils/recommendation.py` entirely with:

```python
from apis.utils.variants import is_variant_unlocked, slot_active_variant


def pick_recommended_decks(
    all_decks, owned_card_names, level_by_name, evolution_level_by_name, limit=3
):
    """Top `limit` decks the player owns all base cards for, ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by count descending.

    Each result is the input deck dict augmented with:
      - `avg_level`: mean of `level_by_name[name]` across the deck's cards (1 dp)
      - `fully_playable`: True iff `missing_variants` is empty
      - `missing_variants`: list of {name, slot, variant} for slots whose active
        variant the player has not unlocked.
    Sort is stable on the secondary key — ties preserve input order.
    """
    annotated = []
    for deck in all_decks:
        names = [c["name"] for c in deck["cards"]]
        if not names:
            continue
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        missing = []
        for slot_idx, card in enumerate(deck["cards"]):
            variant = slot_active_variant(
                slot_idx, card.get("hasEvolution"), card.get("hasHero")
            )
            if variant and not is_variant_unlocked(
                evolution_level_by_name.get(card["name"]), variant
            ):
                missing.append(
                    {"name": card["name"], "slot": slot_idx, "variant": variant}
                )
        annotated.append({
            **deck,
            "avg_level": round(avg_level, 1),
            "fully_playable": not missing,
            "missing_variants": missing,
        })
    annotated.sort(key=lambda d: (not d["fully_playable"], -d["count"]))
    return annotated[:limit]
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `docker-compose exec -T backend python -m unittest tests.test_recommendation tests.test_variants -v`
Expected: PASS, 27 tests (14 recommendation + 13 variants).

- [ ] **Step 5: Commit**

```bash
git add backend/apis/utils/recommendation.py backend/tests/test_recommendation.py
git commit -m "Make pick_recommended_decks variant-aware"
```

---

## Task 3: Update `/player/<tag>` to thread `evolutionLevel`

**Files:**
- Modify: `backend/apis/player.py`

- [ ] **Step 1: Update the resource**

Replace `backend/apis/player.py` entirely with:

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
        try:
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
        except requests.exceptions.RequestException:
            return {"error": "upstream error"}, 502
        except ValueError:
            return {"error": "upstream error"}, 502

        cards = player.get("cards", []) or []
        owned_card_names = {c["name"] for c in cards}
        level_by_name = {c["name"]: c["level"] for c in cards}
        evolution_level_by_name = {
            c["name"]: (c.get("evolutionLevel") or 0) for c in cards
        }

        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT decks FROM common_decks ORDER BY timestamp DESC LIMIT 1"
                )
                row = cursor.fetchone()
        decks = row[0] if row else []

        recommended = pick_recommended_decks(
            decks,
            owned_card_names,
            level_by_name,
            evolution_level_by_name,
            limit=3,
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
                {
                    "name": c["name"],
                    "level": c["level"],
                    "maxLevel": c["maxLevel"],
                    "evolutionLevel": c.get("evolutionLevel") or 0,
                }
                for c in cards
            ],
            "recommended_decks": recommended,
        }
```

- [ ] **Step 2: Smoke-test the endpoint**

Gunicorn `--reload` should already be live.

```bash
curl -s "http://localhost:5001/player/%23PPJU2YGP0" | python -m json.tool | head -60
```

Expected:
- `identity.name` is a non-empty string.
- `cards` entries each include `evolutionLevel` (an integer 0-3).
- `recommended_decks` entries each include `fully_playable` (bool) and `missing_variants` (list, may be empty).

If you get HTML / 500, run `docker-compose logs backend --tail=30`.

- [ ] **Step 3: Smoke-test bad tag**

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/player/%23ZZZZZZZZ"
```

Expected: `404`.

- [ ] **Step 4: Run unit tests**

```bash
docker-compose exec -T backend python -m unittest tests.test_recommendation tests.test_variants tests.test_sanity -v
```

Expected: 28 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/apis/player.py
git commit -m "Expose evolutionLevel and thread it into recommendations"
```

---

## Task 4: Frontend `variants.js` mirror

**Files:**
- Create: `frontend/src/utils/variants.js`

- [ ] **Step 1: Create the module**

Create `frontend/src/utils/variants.js`:

```js
// Per-slot variant rule mirrored from backend/apis/utils/variants.py.
// Slot 0 = evo slot. Slot 1 = hero (evo fallback). Slot 2 = hero (evo fallback).
// Slots 3-7 carry no variant.

const EVO_BIT = 1;
const HERO_BIT = 2;

export function activeSlotVariant(slotIndex, hasEvolution, hasHero) {
    if (slotIndex === 0) return hasEvolution ? "evolution" : null;
    if (slotIndex === 1 || slotIndex === 2) {
        if (hasHero) return "hero";
        if (hasEvolution) return "evolution";
    }
    return null;
}

export function isVariantUnlocked(evolutionLevel, variant) {
    if (!variant) return true;
    const bit = variant === "hero" ? HERO_BIT : EVO_BIT;
    return ((evolutionLevel || 0) & bit) !== 0;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/utils/variants.js
git commit -m "Add frontend variants util mirroring backend rule"
```

---

## Task 5: Update `Deck.js` for variant-aware overlay

**Files:**
- Modify: `frontend/src/components/Deck.js`

- [ ] **Step 1: Replace `Deck.js` entirely**

Replace `frontend/src/components/Deck.js` with:

```jsx
import React from "react";
import { activeSlotVariant, isVariantUnlocked } from "../utils/variants";

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

function ownershipBadge(card, slotIndex, ownership) {
    if (!ownership) return null;
    const info = ownership[card.name];
    if (!info) {
        return (
            <span className="badge bg-danger position-absolute top-0 end-0 m-1">
                Missing
            </span>
        );
    }
    const variant = activeSlotVariant(slotIndex, card.hasEvolution, card.hasHero);
    if (variant && !isVariantUnlocked(info.evolutionLevel, variant)) {
        return (
            <span className="badge bg-warning text-dark position-absolute top-0 end-0 m-1">
                no {variant === "hero" ? "hero" : "evo"}
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
                        {ownershipBadge(card, idx, ownership)}
                    </div>
                );
            })}
        </div>
    );
}
```

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds (warnings OK).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Deck.js
git commit -m "Deck overlay shows yellow badge for variant-locked slots"
```

---

## Task 6: Update `TopDecks.js` to thread `evolutionLevel`

**Files:**
- Modify: `frontend/src/components/TopDecks.js`

- [ ] **Step 1: Update `buildOwnershipMap`**

In `frontend/src/components/TopDecks.js`, replace the `buildOwnershipMap` method body so the entries include `evolutionLevel` from the player payload. The whole method becomes:

```js
buildOwnershipMap() {
    const { playerData } = this.state;
    if (!playerData) return null;
    const map = {};
    for (const c of playerData.cards) {
        map[c.name] = {
            level: c.level,
            maxLevel: c.maxLevel,
            evolutionLevel: c.evolutionLevel,
        };
    }
    return map;
}
```

No other changes to `TopDecks.js`.

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TopDecks.js
git commit -m "Thread evolutionLevel through ownership map"
```

---

## Task 7: Update `Player.js` to render missing-variants caption

**Files:**
- Modify: `frontend/src/components/Player.js`

- [ ] **Step 1: Add the caption inside the recommended-decks map**

In `frontend/src/components/Player.js`, locate the `recommended_decks.map((deck, idx) => (...)` block in the `render` method. Inside the `<div className="mb-5">` wrapper, between the existing header `<div className="mb-2">...</div>` and the `<Deck cards={deck.cards} />` call, add:

```jsx
{deck.missing_variants.length > 0 && (
    <div className="small text-warning mb-2">
        Missing:{" "}
        {deck.missing_variants
            .map((m) => `${m.variant === "hero" ? "hero" : "evo"} ${m.name}`)
            .join(", ")}
    </div>
)}
```

The full `recommended_decks.map(...)` block should now be:

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
        {deck.missing_variants.length > 0 && (
            <div className="small text-warning mb-2">
                Missing:{" "}
                {deck.missing_variants
                    .map((m) => `${m.variant === "hero" ? "hero" : "evo"} ${m.name}`)
                    .join(", ")}
            </div>
        )}
        <Deck cards={deck.cards} />
        <hr className="mt-4" />
    </div>
))
```

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Player.js
git commit -m "Show missing variants caption per recommended deck"
```

---

## Done

After Task 7, the feature is complete. Run a final end-to-end pass:

1. Backend tests: `docker-compose exec -T backend python -m unittest tests.test_recommendation tests.test_variants tests.test_sanity -v` — 28 tests, all pass.
2. Set tag `#PPJU2YGP0` in navbar (already there from prior session).
3. Visit `/player/%23PPJU2YGP0`:
   - Recommendations should now respect variant unlocks.
   - Decks where the player is missing a slot variant show "Missing: evo Royal Giant" (or similar) and rank below fully-playable decks.
   - Decks fully playable show no caption.
4. Visit `/decks` with overlay on:
   - Cards in slot 0 the player owns but lacks the evo for show a yellow "no evo" badge instead of a level number.
   - Same for hero slots in slots 1 / 2.
   - Other cards unchanged.
5. Toggle overlay off → all badges/yellow-states disappear.
