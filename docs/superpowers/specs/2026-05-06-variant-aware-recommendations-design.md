# Variant-Aware Recommendations Design

**Date:** 2026-05-06

## Goal

Two surfaces currently treat "owns the base card" as sufficient for ownership: the `/player/<tag>` recommendations and the `/decks` overlay. Both should respect per-slot variant unlocks (evolution and hero). Decks the player can fully play (all base cards owned AND all required variants unlocked) come first; decks the player can only partially play (missing variants but base cards owned) get demoted and labeled, not excluded. The `/decks` overlay shows a distinct "no evo" / "no hero" badge for variant-locked slots.

## Background — the unlock signal

The Clash Royale player API exposes per-card `evolutionLevel` as a bitfield, not a level:

| value | meaning |
|---|---|
| `None` or `0` | no variants unlocked |
| `1` | evo only unlocked (`& 1`) |
| `2` | hero only unlocked (`& 2`) |
| `3` | both unlocked |

`maxEvolutionLevel` follows the same pattern (which variants exist for that card in the game).

Verified against `#PPJU2YGP0`'s data: hero-only cards with `evolutionLevel=2` (Giant, Magic Archer, Mega Minion, Barbarian Barrel, Balloon) line up with RoyaleAPI's "Hero Card Collection" page; evo-only cards with `evolutionLevel=1` (Furnace, Mega Knight, etc.) line up with the "Evo Card Collection" page; dual-variant cards (Wizard `=3`, Knight `=1`, Musketeer `=None`) match the user's stated unlocks.

## Non-Goals (v1)

- Refactoring `data_utils._slot_active_variant` to share the new variants module (acceptable duplication; ingestion-side cleanup is out of scope).
- Surfacing per-variant levels (we treat unlock as binary; not displaying "your evo is at level 2 of 3").
- Server-side caching of CR API responses.
- Updating the `/cards` page (separate concern).
- Excluding partially-playable decks from recommendations (per user choice they're demoted, not excluded).

## Architecture Overview

- **Backend** — `pick_recommended_decks` gains an `evolution_level_by_name` parameter and uses the per-slot variant rule + bitmask check to compute `fully_playable: bool` and `missing_variants: list[{name, slot, variant}]` for each deck. Sort key becomes `(fully_playable desc, count desc)`. The `/player/<tag>` response now includes `evolutionLevel` per card.
- **Shared rule** — A new pure module `apis/utils/variants.py` (Python) holds `slot_active_variant` and `is_variant_unlocked`. A mirrored `frontend/src/utils/variants.js` exists for the overlay (the rule lives in two places — Python and JS — but each side has one canonical definition).
- **`/decks` overlay** — `Deck.js` gains a third badge state. `TopDecks.js` extends the ownership map to include `evolutionLevel`.
- **`/player` page** — `Player.js` renders a "Missing: evo Royal Giant, hero Bowler" caption for any deck where `missing_variants` is non-empty.

No schema changes, no new endpoints.

## Backend

### New module: `backend/apis/utils/variants.py`

```python
EVO_BIT = 1
HERO_BIT = 2


def slot_active_variant(slot_idx, has_evolution, has_hero):
    """Which variant the deck slot is using. Returns 'evolution', 'hero', or None.

    Slot 0 = evolution slot (only if hasEvolution).
    Slot 1 / 2 = hero if hasHero, else evolution if hasEvolution.
    Slots 3-7 = no variant.
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
    """Bitmask check. evolution_level None or 0 = nothing unlocked.

    `variant` is 'evolution', 'hero', or None. None always returns True.
    """
    if variant is None:
        return True
    bit = HERO_BIT if variant == "hero" else EVO_BIT
    return bool((evolution_level or 0) & bit)
```

### Updated: `backend/apis/utils/recommendation.py`

```python
from apis.utils.variants import is_variant_unlocked, slot_active_variant


def pick_recommended_decks(
    all_decks, owned_card_names, level_by_name, evolution_level_by_name, limit=3
):
    """Top `limit` decks the player owns all base cards for, ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by count descending.

    Each result includes `avg_level`, `fully_playable`, and `missing_variants`.
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

### Updated: `backend/apis/player.py`

```python
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

Other resource code (the `try/except` around the CR call, the 404/502 returns) stays unchanged.

## Frontend

### New module: `frontend/src/utils/variants.js`

```js
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

### Updated: `frontend/src/components/Deck.js`

`ownership` is now `{ [cardName]: { level, maxLevel, evolutionLevel } }`. The badge function gains a third state — yellow "no evo" / "no hero" — for cards that are owned but the slot's variant isn't unlocked. `opacity-25` keeps its current meaning: only fully unowned cards are dimmed.

```jsx
import { activeSlotVariant, isVariantUnlocked } from "../utils/variants";

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
```

The call site inside `cards.map` becomes `{ownershipBadge(card, idx, ownership)}` (passing `idx` is the only signature change at the call site).

### Updated: `frontend/src/components/TopDecks.js`

`buildOwnershipMap` gains `evolutionLevel`:

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

No other change.

### Updated: `frontend/src/components/Player.js`

Inside the existing `recommended_decks.map(...)` block, add a "Missing: ..." caption between the existing "used by N · avg level X.Y" header and the `<Deck cards={deck.cards} />`:

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

## Edge Cases

| Case | Behavior |
|---|---|
| `evolutionLevel` field missing on a card | `c.get("evolutionLevel") or 0` → no variants unlocked. Variant slots get demoted/badged. |
| All 3 recs end up partially playable | All 3 render with "Missing: ..." captions. No special "nothing fully playable" message. |
| Top deck has slots 0/1/2 on cards without variant art | `slot_active_variant` returns `None` → no variant check → `missing_variants: []` → fully playable. |
| Player owns no full meta deck | `recommended_decks: []`, existing "No full meta deck matches your collection yet." stays. |
| Dual-variant card in slot 1, hero bit unlocked but evo bit not | Slot is hero → check hero bit only → unlocked → fully playable. |
| Dual-variant card in slot 1, only evo bit unlocked | Slot is hero → check hero bit only → not unlocked → demoted with "Missing: hero Wizard" caption. |
| `/decks` overlay toggle off | `ownership = null`, no badges, no variant logic runs. |
| Backend response always includes `missing_variants` (even when empty) | `Player.js` only renders caption when `length > 0`. |
| Sort tie: two fully-playable decks with the same count | Falls through to input order (stable sort). |

## Testing

**`backend/tests/test_variants.py`** (new) — unit tests for the pure rule:

- `slot_active_variant`:
  - slot 0 with `has_evolution=True` → `"evolution"`.
  - slot 0 with `has_evolution=False` → `None`.
  - slot 1 with `has_hero=True` → `"hero"`.
  - slot 1 with `has_hero=False, has_evolution=True` → `"evolution"`.
  - slot 1 with neither → `None`.
  - slot 2 same as slot 1.
  - slots 3–7 always `None`.
- `is_variant_unlocked`:
  - `variant=None` → always `True`.
  - `evolution_level=None` and any variant → `False`.
  - `evolution_level=0` and any variant → `False`.
  - `evolution_level=1` with `"evolution"` → `True`.
  - `evolution_level=1` with `"hero"` → `False`.
  - `evolution_level=2` with `"evolution"` → `False`.
  - `evolution_level=2` with `"hero"` → `True`.
  - `evolution_level=3` with `"evolution"` → `True`.
  - `evolution_level=3` with `"hero"` → `True`.

**`backend/tests/test_recommendation.py`** (updated) — existing tests get the new `evolution_level_by_name` argument; add new cases:

- Fully owned + all variants unlocked → `fully_playable=True`, `missing_variants=[]`.
- Fully owned + slot-0 evo card without evo bit → `fully_playable=False`, `missing_variants` contains `{name, slot=0, variant="evolution"}`.
- Fully owned + slot-1 hero card without hero bit → `missing_variants` contains `{name, slot=1, variant="hero"}`.
- Sort: a partially-playable deck with `count=99` ranks BELOW a fully-playable deck with `count=5`.
- Cards in slots 3–7 don't trigger variant checks even when `hasEvolution=True`.
- Bitmask `evolutionLevel=3` satisfies both evo and hero slots.

No frontend tests (consistent with current repo).

**Manual verification:**
- Visit `/player/%23PPJU2YGP0` — top recommendations no longer include evo-Royal-Giant decks if Royal-Giant evo isn't unlocked; partial decks (if any) show "Missing: evo Royal Giant" and rank below fully-playable ones.
- Visit `/decks` with overlay on — cards in slot 0 you own but lack the evo for show a yellow "no evo" badge instead of a level number. Same for hero slots.
- Toggle overlay off → all badges revert to nothing.
