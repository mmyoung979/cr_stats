# Relational Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the JSON-snapshot tables (`common_cards`, `common_decks`, `recent_battles`) with 4 relational tables (`cards`, `decks`, `players`, `battles`). Aggregations move from cron-time JSON dumps to read-time SQL queries over a 7-day rolling window. Adds numbered SQL migration infrastructure.

**Architecture:** Numbered migration files in `backend/scripts/migrations/`, run via a small Python runner. Cron does append-and-upsert into the new tables (no aggregation step). Read endpoints query the new tables and assemble the same JSON shapes the frontend already expects, plus a new `activeForm` field per card derived from membership in `evo_card_ids` / `hero_card_ids`.

**Tech Stack:** Python 3, Flask-RESTful, psycopg2 (Postgres 17), Docker Compose.

**Spec:** `docs/superpowers/specs/2026-05-06-relational-data-model-design.md`

**Important codebase conventions:**
- Backend imports rooted at `backend/`. Tests run inside the container via `docker-compose exec -T backend python -m unittest tests.<name>`.
- DB connections via `apis.utils.db_utils.make_connection()` as a context manager.
- Cron entry point: `backend/scripts/update_cards.py`.
- The Docker stack is already up. After backend changes, gunicorn `--reload` picks them up automatically.
- Commit directly to master (user has consented throughout the session).
- Working directory: `/Users/matthewyoung/Documents/GitHub/cr_stats`.

**Important: this refactor's intermediate states.** The plan executes with the system in a partially-broken state for several tasks. After Task 4 (cron rewrite), `/decks` and `/cards` return *stale data* (last successful old-cron snapshot from before the migration) until each endpoint is migrated in Tasks 5–8. This is acceptable for a personal app on master. Don't try to keep things working perfectly through every intermediate commit — keep moving.

---

## File Structure

**New files:**
- `backend/scripts/migrations/001_initial.sql` — schema + `schema_migrations` tracking table.
- `backend/scripts/migrate.py` — migration runner (apply / drop_legacy subcommands).
- `backend/apis/utils/decks.py` — `hydrate_deck` render helper.
- `backend/tests/test_deck_inference.py` — tests for `infer_deck`.
- `backend/tests/test_hydrate_deck.py` — tests for `hydrate_deck`.

**Modified files:**
- `backend/scripts/utils/data_utils.py` — add `refresh_cards_catalog`, `infer_deck`, `upsert_deck`, `upsert_player`, `insert_battle`. Delete `_battle_deck`, `get_card_data`, `get_deck_data`, `get_battle_rows` after Task 9.
- `backend/scripts/update_cards.py` — full rewrite around the new helpers.
- `backend/apis/most_common_cards.py` — query new schema.
- `backend/apis/most_common_decks.py` — query new schema.
- `backend/apis/recent_battles.py` — query new schema.
- `backend/apis/player.py` — query new schema for recommendations.
- `backend/apis/utils/recommendation.py` — adapt signature for new candidate shape.
- `backend/tests/test_recommendation.py` — adapt fixtures to new candidate shape.
- `backend/settings.py` — add `META_WINDOW_DAYS = 7`.
- `Makefile` — add `migrate` target, drop `init-db` target.

**Deleted files (Task 9):**
- `backend/scripts/init_db.py` — schema lives in migrations now.

---

## Task 1: Migration infrastructure

**Files:**
- Create: `backend/scripts/migrations/001_initial.sql`
- Create: `backend/scripts/migrate.py`
- Modify: `Makefile`

- [ ] **Step 1: Create the initial migration**

Create `backend/scripts/migrations/001_initial.sql`:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cards (
    id                  BIGINT PRIMARY KEY,
    name                TEXT NOT NULL,
    rarity              TEXT NOT NULL,
    elixir_cost         INT,
    max_level           INT,
    has_evolution       BOOLEAN NOT NULL,
    has_hero            BOOLEAN NOT NULL,
    icon_url            TEXT,
    evolution_icon_url  TEXT,
    hero_icon_url       TEXT
);

CREATE TABLE decks (
    id              BIGSERIAL PRIMARY KEY,
    hash            CHAR(64) NOT NULL UNIQUE,
    card_ids        BIGINT[] NOT NULL,
    evo_card_ids    BIGINT[] NOT NULL,
    hero_card_ids   BIGINT[] NOT NULL
);

CREATE INDEX decks_card_ids_gin ON decks USING GIN (card_ids);

CREATE TABLE players (
    tag     TEXT PRIMARY KEY,
    name    TEXT
);

CREATE TABLE battles (
    timestamp       TIMESTAMPTZ NOT NULL,
    team_tag        TEXT NOT NULL REFERENCES players(tag),
    opp_tag         TEXT REFERENCES players(tag),
    team_deck_id    BIGINT NOT NULL REFERENCES decks(id),
    opp_deck_id     BIGINT NOT NULL REFERENCES decks(id),
    team_rank       INT,
    opp_rank        INT,
    team_crowns     INT,
    opp_crowns      INT,
    PRIMARY KEY (timestamp, team_tag)
);

CREATE INDEX battles_timestamp_idx ON battles (timestamp DESC);
CREATE INDEX battles_team_deck_id_idx ON battles (team_deck_id);
```

- [ ] **Step 2: Create the migration runner**

Create `backend/scripts/migrate.py`:

```python
"""Migration runner.

Usage:
    python scripts/migrate.py            # apply any unapplied migrations
    python scripts/migrate.py drop_legacy  # drop pre-refactor tables
"""
# Python imports
import os
import sys

# Local imports
from apis.utils.db_utils import make_connection

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def applied_migrations(cursor):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'schema_migrations'
        )
    """)
    if not cursor.fetchone()[0]:
        return set()
    cursor.execute("SELECT filename FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations():
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    with make_connection() as conn:
        with conn.cursor() as cur:
            applied = applied_migrations(cur)
            for filename in files:
                if filename in applied:
                    print(f"skip  {filename} (already applied)")
                    continue
                path = os.path.join(MIGRATIONS_DIR, filename)
                with open(path) as f:
                    sql = f.read()
                print(f"apply {filename}")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,),
                )
            conn.commit()


def drop_legacy():
    confirm = input(
        "This will DROP common_cards, common_decks, recent_battles. "
        "Type 'drop' to confirm: "
    )
    if confirm != "drop":
        print("aborted")
        return
    with make_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS common_cards")
            cur.execute("DROP TABLE IF EXISTS common_decks")
            cur.execute("DROP TABLE IF EXISTS recent_battles")
            conn.commit()
    print("legacy tables dropped")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "drop_legacy":
        drop_legacy()
    else:
        apply_migrations()
```

- [ ] **Step 3: Update the Makefile**

Replace the `init-db` target with `migrate`. The `init` target should call `migrate` instead of `init-db`. Final `Makefile`:

```makefile
DC=docker-compose

init: ## start from scratch
	make up
	make migrate
	make update-cards
	@echo "CR Stats successfully initialized"

up: ## start up the app
	@$(DC) --env-file .env up -d
	@echo "CR Stats is running"

migrate: ## Apply database migrations
	@$(DC) exec -T backend python ./scripts/migrate.py
	@echo "Migrations applied"

update-cards: ## Hit the CR API and update the database
	@$(DC) exec -T backend python ./scripts/update_cards.py
	@echo "Most recent cards have been updated"
```

- [ ] **Step 4: Apply the migration**

Run: `make migrate`
Expected: `apply 001_initial.sql` (or `skip` on subsequent runs).

- [ ] **Step 5: Verify schema exists**

```bash
docker-compose exec -T postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "\\dt"
```

Expected output includes `cards`, `decks`, `players`, `battles`, `schema_migrations` (alongside the still-present old tables).

- [ ] **Step 6: Confirm idempotency**

Run `make migrate` again.
Expected: `skip 001_initial.sql (already applied)`.

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/migrations/001_initial.sql backend/scripts/migrate.py Makefile
git commit -m "Add migration infrastructure and initial relational schema"
```

---

## Task 2: Ingestion helpers (`infer_deck`, `refresh_cards_catalog`)

**Files:**
- Modify: `backend/scripts/utils/data_utils.py`
- Create: `backend/tests/test_deck_inference.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_deck_inference.py`:

```python
import hashlib
from unittest import TestCase

from scripts.utils.data_utils import infer_deck


def _card(card_id, name, has_evo=False, has_hero=False):
    icons = {"medium": f"{name}.png"}
    if has_evo:
        icons["evolutionMedium"] = f"{name}-evo.png"
    if has_hero:
        icons["heroMedium"] = f"{name}-hero.png"
    return {"id": card_id, "name": name, "iconUrls": icons}


def _expected_hash(card_ids, evo_ids, hero_ids):
    payload = (
        "|".join(str(i) for i in sorted(card_ids))
        + "::"
        + "|".join(str(i) for i in sorted(evo_ids))
        + "::"
        + "|".join(str(i) for i in sorted(hero_ids))
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class TestInferDeck(TestCase):
    def test_no_variants_when_no_variant_cards_in_first_three_slots(self):
        cards = [_card(i, chr(ord("A") + i)) for i in range(8)]
        result = infer_deck(cards)
        self.assertEqual(result["card_ids"], sorted(c["id"] for c in cards))
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [])
        self.assertEqual(
            result["hash"], _expected_hash(result["card_ids"], [], [])
        )

    def test_evo_only_in_slot_0(self):
        cards = [_card(0, "Furnace", has_evo=True)] + [
            _card(i, chr(ord("A") + i)) for i in range(1, 8)
        ]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [0])
        self.assertEqual(result["hero_card_ids"], [])

    def test_hero_only_in_slot_1(self):
        cards = [
            _card(0, "Furnace"),
            _card(1, "Bowler", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [1])

    def test_evo_fallback_in_slot_1(self):
        # slot 1 has hasEvolution but NOT hasHero -> falls back to evo
        cards = [
            _card(0, "Furnace"),
            _card(1, "Tesla", has_evo=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [1])
        self.assertEqual(result["hero_card_ids"], [])

    def test_three_form_slots_filled(self):
        cards = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
            _card(2, "Balloon", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(3, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [0])
        self.assertEqual(result["hero_card_ids"], [1, 2])

    def test_dual_variant_in_hero_slot_picks_hero(self):
        # Wizard has both evo and hero; in slot 1 it's hero
        cards = [
            _card(0, "Furnace"),
            _card(1, "Wizard", has_evo=True, has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [1])

    def test_hash_is_order_insensitive_for_regular_slots(self):
        # Same 8 cards, same form choices, different slot 3-7 order -> same hash
        cards_a = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        cards_b = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
        ] + list(reversed([_card(i, chr(ord("A") + i)) for i in range(2, 8)]))
        self.assertEqual(infer_deck(cards_a)["hash"], infer_deck(cards_b)["hash"])

    def test_hash_changes_when_evo_choice_changes(self):
        cards_a = [
            _card(0, "Furnace", has_evo=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(1, 8)]
        # Same 8 cards but Furnace is now in slot 3 (regular form, not evo)
        cards_b = [
            _card(1, "B"), _card(2, "C"), _card(3, "D"),
            _card(0, "Furnace", has_evo=True),  # in slot 3 now -> regular
        ] + [_card(i, chr(ord("A") + i)) for i in range(4, 8)]
        self.assertNotEqual(infer_deck(cards_a)["hash"], infer_deck(cards_b)["hash"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference -v`
Expected: FAIL with `ImportError: cannot import name 'infer_deck' from 'scripts.utils.data_utils'`.

- [ ] **Step 3: Implement `infer_deck` and `refresh_cards_catalog`**

Edit `backend/scripts/utils/data_utils.py`. Add at the top alongside existing imports:

```python
# Add to existing imports
from apis.utils.db_utils import make_connection
from apis.utils.variants import slot_active_variant
```

Then append these new functions to the file:

```python
def _hash_deck(card_ids, evo_card_ids, hero_card_ids):
    payload = (
        "|".join(str(i) for i in sorted(card_ids))
        + "::"
        + "|".join(str(i) for i in sorted(evo_card_ids))
        + "::"
        + "|".join(str(i) for i in sorted(hero_card_ids))
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def infer_deck(battle_cards):
    """Convert a CR battle's `team[0].cards` (or `opponent[0].cards`) array
    into deck identity fields: sorted card_ids set, the evo card subset,
    the hero card subset, and the canonical hash."""
    evo_card_ids = []
    hero_card_ids = []
    for slot_idx, card in enumerate(battle_cards):
        icons = card.get("iconUrls") or {}
        variant = slot_active_variant(
            slot_idx,
            icons.get("evolutionMedium") is not None,
            icons.get("heroMedium") is not None,
        )
        if variant == "evolution":
            evo_card_ids.append(card["id"])
        elif variant == "hero":
            hero_card_ids.append(card["id"])
    card_ids = sorted(c["id"] for c in battle_cards)
    evo_card_ids.sort()
    hero_card_ids.sort()
    return {
        "card_ids": card_ids,
        "evo_card_ids": evo_card_ids,
        "hero_card_ids": hero_card_ids,
        "hash": _hash_deck(card_ids, evo_card_ids, hero_card_ids),
    }


CARDS_UPSERT_SQL = """
INSERT INTO cards (
    id, name, rarity, elixir_cost, max_level,
    has_evolution, has_hero,
    icon_url, evolution_icon_url, hero_icon_url
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    rarity = EXCLUDED.rarity,
    elixir_cost = EXCLUDED.elixir_cost,
    max_level = EXCLUDED.max_level,
    has_evolution = EXCLUDED.has_evolution,
    has_hero = EXCLUDED.has_hero,
    icon_url = EXCLUDED.icon_url,
    evolution_icon_url = EXCLUDED.evolution_icon_url,
    hero_icon_url = EXCLUDED.hero_icon_url
"""


def refresh_cards_catalog():
    """Fetch the global card catalog from CR /cards and upsert every row."""
    response = get_data(API_URL + "/cards")
    items = response.get("items", [])
    with make_connection() as connection:
        with connection.cursor() as cursor:
            for card in items:
                icons = card.get("iconUrls") or {}
                cursor.execute(CARDS_UPSERT_SQL, (
                    card["id"],
                    card["name"],
                    card.get("rarity"),
                    card.get("elixirCost"),
                    card.get("maxLevel"),
                    icons.get("evolutionMedium") is not None,
                    icons.get("heroMedium") is not None,
                    icons.get("medium"),
                    icons.get("evolutionMedium"),
                    icons.get("heroMedium"),
                ))
            connection.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference tests.test_variants tests.test_recommendation tests.test_sanity -v`
Expected: PASS, 36 tests (8 new + 13 variants + 14 recommendation + 1 sanity).

- [ ] **Step 5: Smoke-test `refresh_cards_catalog`**

```bash
docker-compose exec -T backend python -c "from scripts.utils.data_utils import refresh_cards_catalog; refresh_cards_catalog(); print('ok')"
docker-compose exec -T postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "SELECT COUNT(*) FROM cards"
```

Expected: ~150 row count.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/utils/data_utils.py backend/tests/test_deck_inference.py
git commit -m "Add infer_deck and refresh_cards_catalog ingestion helpers"
```

---

## Task 3: Read helper (`hydrate_deck`)

**Files:**
- Create: `backend/apis/utils/decks.py`
- Create: `backend/tests/test_hydrate_deck.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_hydrate_deck.py`:

```python
from unittest import TestCase

from apis.utils.decks import hydrate_deck


def _card_row(card_id, name, elixir_cost=3, has_evolution=False, has_hero=False):
    return {
        "id": card_id,
        "name": name,
        "rarity": "common",
        "elixir_cost": elixir_cost,
        "max_level": 16,
        "has_evolution": has_evolution,
        "has_hero": has_hero,
        "icon_url": f"{name}.png",
        "evolution_icon_url": f"{name}-evo.png" if has_evolution else None,
        "hero_icon_url": f"{name}-hero.png" if has_hero else None,
    }


class TestHydrateDeck(TestCase):
    def test_orders_evos_first_then_heroes_then_regulars_by_elixir(self):
        cards_by_id = {
            1: _card_row(1, "EvoCard", elixir_cost=4, has_evolution=True),
            2: _card_row(2, "HeroCard", elixir_cost=5, has_hero=True),
            3: _card_row(3, "Cheap", elixir_cost=1),
            4: _card_row(4, "Mid", elixir_cost=3),
            5: _card_row(5, "Big", elixir_cost=7),
            6: _card_row(6, "Small", elixir_cost=2),
            7: _card_row(7, "Med2", elixir_cost=4),
            8: _card_row(8, "Filler", elixir_cost=3),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        names = [c["name"] for c in result]
        self.assertEqual(names[0], "EvoCard")
        self.assertEqual(names[1], "HeroCard")
        # Remaining 6 are sorted by elixir cost ascending
        remaining = [c["elixir_cost"] for c in result[2:]]
        self.assertEqual(remaining, sorted(remaining))

    def test_active_form_set_per_card(self):
        cards_by_id = {
            1: _card_row(1, "EvoCard", has_evolution=True),
            2: _card_row(2, "HeroCard", has_hero=True),
            3: _card_row(3, "Plain"),
            4: _card_row(4, "Plain2"),
            5: _card_row(5, "Plain3"),
            6: _card_row(6, "Plain4"),
            7: _card_row(7, "Plain5"),
            8: _card_row(8, "Plain6"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = {c["name"]: c["activeForm"] for c in result}
        self.assertEqual(forms["EvoCard"], "evolution")
        self.assertEqual(forms["HeroCard"], "hero")
        self.assertIsNone(forms["Plain"])

    def test_emits_expected_card_shape(self):
        cards_by_id = {
            1: _card_row(1, "Furnace", has_evolution=True),
            2: _card_row(2, "B"),
            3: _card_row(3, "C"),
            4: _card_row(4, "D"),
            5: _card_row(5, "E"),
            6: _card_row(6, "F"),
            7: _card_row(7, "G"),
            8: _card_row(8, "H"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        first = result[0]
        self.assertEqual(set(first.keys()), {
            "name", "icon", "evolvedIcon", "heroIcon",
            "hasEvolution", "hasHero", "elixir_cost", "activeForm",
        })
        self.assertEqual(first["icon"], "Furnace.png")
        self.assertEqual(first["evolvedIcon"], "Furnace-evo.png")
        self.assertEqual(first["activeForm"], "evolution")

    def test_skips_unknown_card_ids(self):
        # If a card_id is missing from cards_by_id, skip it (defensive).
        cards_by_id = {
            1: _card_row(1, "A"),
            2: _card_row(2, "B"),
        }
        deck_row = {"card_ids": [1, 2, 999], "evo_card_ids": [], "hero_card_ids": []}
        result = hydrate_deck(deck_row, cards_by_id)
        self.assertEqual(len(result), 2)
        self.assertEqual({c["name"] for c in result}, {"A", "B"})

    def test_empty_deck_returns_empty(self):
        self.assertEqual(
            hydrate_deck({"card_ids": [], "evo_card_ids": [], "hero_card_ids": []}, {}),
            [],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose exec -T backend python -m unittest tests.test_hydrate_deck -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apis.utils.decks'`.

- [ ] **Step 3: Implement `hydrate_deck`**

Create `backend/apis/utils/decks.py`:

```python
def _card_json(card_row, active_form):
    return {
        "name": card_row["name"],
        "icon": card_row["icon_url"],
        "evolvedIcon": card_row["evolution_icon_url"],
        "heroIcon": card_row["hero_icon_url"],
        "hasEvolution": card_row["has_evolution"],
        "hasHero": card_row["has_hero"],
        "elixir_cost": card_row["elixir_cost"],
        "activeForm": active_form,
    }


def hydrate_deck(deck_row, cards_by_id):
    """Build the frontend per-card JSON list for one deck.

    Order: evos first, then heroes, then regulars — each group sorted by
    elixir_cost ascending. activeForm is derived from membership in the
    deck's evo_card_ids / hero_card_ids. Unknown card_ids are skipped.
    """
    evo_set = set(deck_row["evo_card_ids"])
    hero_set = set(deck_row["hero_card_ids"])

    evos, heroes, regulars = [], [], []
    for card_id in deck_row["card_ids"]:
        card_row = cards_by_id.get(card_id)
        if card_row is None:
            continue
        if card_id in evo_set:
            evos.append(_card_json(card_row, "evolution"))
        elif card_id in hero_set:
            heroes.append(_card_json(card_row, "hero"))
        else:
            regulars.append(_card_json(card_row, None))

    def by_elixir(card):
        return card["elixir_cost"] if card["elixir_cost"] is not None else 0

    evos.sort(key=by_elixir)
    heroes.sort(key=by_elixir)
    regulars.sort(key=by_elixir)
    return evos + heroes + regulars
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker-compose exec -T backend python -m unittest tests.test_hydrate_deck -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Confirm full suite still passes**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference tests.test_hydrate_deck tests.test_variants tests.test_recommendation tests.test_sanity -v`
Expected: PASS, 41 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/apis/utils/decks.py backend/tests/test_hydrate_deck.py
git commit -m "Add hydrate_deck render helper"
```

---

## Task 4: Cron rewrite

**Files:**
- Modify: `backend/scripts/utils/data_utils.py`
- Modify: `backend/scripts/update_cards.py`

- [ ] **Step 1: Add upsert helpers to `data_utils.py`**

Append to `backend/scripts/utils/data_utils.py`:

```python
DECK_UPSERT_SQL = """
INSERT INTO decks (hash, card_ids, evo_card_ids, hero_card_ids)
VALUES (%s, %s, %s, %s)
ON CONFLICT (hash) DO UPDATE SET hash = EXCLUDED.hash
RETURNING id
"""


def upsert_deck(cursor, deck):
    """Insert (or get id of existing) deck row. `deck` is the dict from
    `infer_deck`. Returns the deck's id."""
    cursor.execute(DECK_UPSERT_SQL, (
        deck["hash"],
        deck["card_ids"],
        deck["evo_card_ids"],
        deck["hero_card_ids"],
    ))
    return cursor.fetchone()[0]


PLAYER_UPSERT_SQL = """
INSERT INTO players (tag, name)
VALUES (%s, %s)
ON CONFLICT (tag) DO UPDATE SET name = EXCLUDED.name
"""


def upsert_player(cursor, tag, name):
    cursor.execute(PLAYER_UPSERT_SQL, (tag, name))


BATTLE_INSERT_SQL = """
INSERT INTO battles (
    timestamp, team_tag, opp_tag, team_deck_id, opp_deck_id,
    team_rank, opp_rank, team_crowns, opp_crowns
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (timestamp, team_tag) DO NOTHING
"""


def insert_battle(
    cursor, timestamp, team_tag, opp_tag,
    team_deck_id, opp_deck_id,
    team_rank, opp_rank, team_crowns, opp_crowns,
):
    cursor.execute(BATTLE_INSERT_SQL, (
        timestamp, team_tag, opp_tag,
        team_deck_id, opp_deck_id,
        team_rank, opp_rank, team_crowns, opp_crowns,
    ))
```

(The `ON CONFLICT (hash) DO UPDATE SET hash = EXCLUDED.hash` is a no-op write that lets `RETURNING id` return the existing row's id for upserts. Without it, `INSERT … ON CONFLICT DO NOTHING RETURNING id` returns no rows when a conflict happens.)

- [ ] **Step 2: Rewrite `update_cards.py`**

Replace `backend/scripts/update_cards.py` entirely with:

```python
# Local imports
from apis.utils.db_utils import make_connection
from scripts.utils.data_utils import (
    _parse_battle_time,
    _resolve_rank,
    get_battlelog_data,
    infer_deck,
    insert_battle,
    refresh_cards_catalog,
    upsert_deck,
    upsert_player,
)

RANKED = "pathOfLegend"


def ingest_battles(player_count: int = 100):
    refresh_cards_catalog()
    battlelog_data, rank_by_tag = get_battlelog_data(player_count)

    with make_connection() as connection:
        with connection.cursor() as cursor:
            for battlelog in battlelog_data:
                if not isinstance(battlelog, list):
                    continue
                for battle in battlelog:
                    if battle.get("type") != RANKED:
                        continue
                    team = (battle.get("team") or [None])[0]
                    opp = (battle.get("opponent") or [None])[0]
                    if not team or not opp:
                        continue
                    try:
                        team_deck = infer_deck(team["cards"])
                        opp_deck = infer_deck(opp["cards"])
                        team_deck_id = upsert_deck(cursor, team_deck)
                        opp_deck_id = upsert_deck(cursor, opp_deck)
                        upsert_player(cursor, team["tag"], team.get("name"))
                        if opp.get("tag"):
                            upsert_player(cursor, opp["tag"], opp.get("name"))
                        insert_battle(
                            cursor,
                            timestamp=_parse_battle_time(battle["battleTime"]),
                            team_tag=team["tag"],
                            opp_tag=opp.get("tag"),
                            team_deck_id=team_deck_id,
                            opp_deck_id=opp_deck_id,
                            team_rank=_resolve_rank(team, rank_by_tag),
                            opp_rank=_resolve_rank(opp, rank_by_tag),
                            team_crowns=team.get("crowns"),
                            opp_crowns=opp.get("crowns"),
                        )
                    except (KeyError, ValueError):
                        continue
            connection.commit()


if __name__ == "__main__":
    ingest_battles(player_count=100)
    print("Cards catalog refreshed and battles ingested.")
```

- [ ] **Step 3: Run cron**

```bash
make update-cards
```

Expected: prints "Cards catalog refreshed and battles ingested." within ~30 seconds (depends on CR API).

- [ ] **Step 4: Verify the new tables have data**

```bash
docker-compose exec -T postgres psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "SELECT COUNT(*) FROM cards" -c "SELECT COUNT(*) FROM decks" -c "SELECT COUNT(*) FROM players" -c "SELECT COUNT(*) FROM battles"
```

Expected: cards ≈150, decks > 0, players > 0, battles > 0. If battles=0, the cron likely failed silently — check `docker-compose logs backend --tail=30`.

- [ ] **Step 5: Run unit tests**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference tests.test_hydrate_deck tests.test_variants tests.test_recommendation tests.test_sanity -v`
Expected: PASS, 41 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/utils/data_utils.py backend/scripts/update_cards.py
git commit -m "Rewrite cron to write into relational schema"
```

---

## Task 5: `/decks` endpoint refactor

**Files:**
- Modify: `backend/apis/most_common_decks.py`
- Modify: `backend/settings.py`

- [ ] **Step 1: Add `META_WINDOW_DAYS` to `settings.py`**

Append to `backend/settings.py`:

```python
META_WINDOW_DAYS = 7
```

- [ ] **Step 2: Replace `most_common_decks.py`**

Replace `backend/apis/most_common_decks.py` entirely with:

```python
# Python imports
from datetime import datetime, timedelta, timezone

# Third party imports
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.decks import hydrate_deck
from settings import META_WINDOW_DAYS


DECKS_QUERY = """
SELECT
    d.id, d.card_ids, d.evo_card_ids, d.hero_card_ids,
    COUNT(*) AS count,
    array_agg(DISTINCT b.team_tag) AS player_tags
FROM battles b
JOIN decks d ON d.id = b.team_deck_id
WHERE b.timestamp > %s
GROUP BY d.id
ORDER BY count DESC
LIMIT 50
"""


class MostCommonDecks(Resource):
    def get(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=META_WINDOW_DAYS)
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(DECKS_QUERY, (cutoff,))
                deck_rows = cursor.fetchall()
                # Collect every card id involved, fetch once
                all_card_ids = set()
                for row in deck_rows:
                    all_card_ids.update(row[1])  # card_ids column
                if all_card_ids:
                    cursor.execute(
                        "SELECT id, name, rarity, elixir_cost, max_level, "
                        "has_evolution, has_hero, icon_url, evolution_icon_url, "
                        "hero_icon_url FROM cards WHERE id = ANY(%s)",
                        (list(all_card_ids),),
                    )
                    cards_by_id = {
                        r[0]: {
                            "id": r[0], "name": r[1], "rarity": r[2],
                            "elixir_cost": r[3], "max_level": r[4],
                            "has_evolution": r[5], "has_hero": r[6],
                            "icon_url": r[7], "evolution_icon_url": r[8],
                            "hero_icon_url": r[9],
                        }
                        for r in cursor.fetchall()
                    }
                else:
                    cards_by_id = {}

        result = []
        for deck_id, card_ids, evo_card_ids, hero_card_ids, count, player_tags in deck_rows:
            deck_dict = {
                "card_ids": card_ids,
                "evo_card_ids": evo_card_ids,
                "hero_card_ids": hero_card_ids,
            }
            result.append({
                "count": count,
                "cards": hydrate_deck(deck_dict, cards_by_id),
                "players": player_tags or [],
            })
        return result
```

- [ ] **Step 3: Smoke-test the endpoint**

```bash
curl -s http://localhost:5001/decks | python -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'decks'); print('first deck count:', d[0]['count'] if d else 'n/a'); print('first card:', d[0]['cards'][0] if d else 'n/a')"
```

Expected: prints a non-zero number of decks (assuming Task 4's cron run produced data within the last 7 days). First card has all expected keys including `activeForm`.

If empty: confirm `SELECT COUNT(*) FROM battles WHERE timestamp > NOW() - INTERVAL '7 days'` is non-zero.

- [ ] **Step 4: Commit**

```bash
git add backend/apis/most_common_decks.py backend/settings.py
git commit -m "Switch /decks to relational schema with read-time aggregation"
```

---

## Task 6: `/cards` endpoint refactor

**Files:**
- Modify: `backend/apis/most_common_cards.py`

- [ ] **Step 1: Replace `most_common_cards.py`**

Replace `backend/apis/most_common_cards.py` entirely with:

```python
# Python imports
from datetime import datetime, timedelta, timezone

# Third party imports
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from settings import META_WINDOW_DAYS


CARDS_QUERY = """
WITH deck_slots AS (
    SELECT
        b.team_deck_id AS deck_id,
        slot.card_id,
        d.evo_card_ids,
        d.hero_card_ids
    FROM battles b
    JOIN decks d ON d.id = b.team_deck_id,
    UNNEST(d.card_ids) AS slot(card_id)
    WHERE b.timestamp > %s
)
SELECT
    ds.card_id,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE ds.card_id = ANY(ds.evo_card_ids))  AS evolution_count,
    COUNT(*) FILTER (WHERE ds.card_id = ANY(ds.hero_card_ids)) AS hero_count,
    c.name, c.elixir_cost, c.has_evolution, c.has_hero,
    c.icon_url, c.evolution_icon_url, c.hero_icon_url
FROM deck_slots ds
JOIN cards c ON c.id = ds.card_id
GROUP BY ds.card_id, c.name, c.elixir_cost, c.has_evolution, c.has_hero,
         c.icon_url, c.evolution_icon_url, c.hero_icon_url
ORDER BY count DESC
"""


class MostCommonCards(Resource):
    def get(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=META_WINDOW_DAYS)
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CARDS_QUERY, (cutoff,))
                rows = cursor.fetchall()
        return [
            {
                "name": name,
                "count": count,
                "evolutionCount": evolution_count,
                "heroCount": hero_count,
                "hasEvolution": has_evolution,
                "hasHero": has_hero,
                "icon": icon_url,
                "evolvedIcon": evolution_icon_url,
                "heroIcon": hero_icon_url,
                "elixirCost": elixir_cost,
            }
            for (
                _card_id, count, evolution_count, hero_count,
                name, elixir_cost, has_evolution, has_hero,
                icon_url, evolution_icon_url, hero_icon_url,
            ) in rows
        ]
```

- [ ] **Step 2: Smoke-test**

```bash
curl -s http://localhost:5001/cards | python -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'cards'); print(d[0] if d else 'empty')"
```

Expected: non-empty list, first card has count and either evolutionCount/heroCount > 0 or = 0.

- [ ] **Step 3: Commit**

```bash
git add backend/apis/most_common_cards.py
git commit -m "Switch /cards to relational schema with read-time aggregation"
```

---

## Task 7: `/battles` endpoint refactor

**Files:**
- Modify: `backend/apis/recent_battles.py`

- [ ] **Step 1: Replace `recent_battles.py`**

Replace `backend/apis/recent_battles.py` entirely with:

```python
# Third party imports
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.decks import hydrate_deck


BATTLES_QUERY = """
SELECT
    b.timestamp, b.team_tag, p1.name AS team_name, b.team_rank, b.team_crowns,
    b.team_deck_id,
    b.opp_tag, p2.name AS opp_name, b.opp_rank, b.opp_crowns,
    b.opp_deck_id
FROM battles b
LEFT JOIN players p1 ON p1.tag = b.team_tag
LEFT JOIN players p2 ON p2.tag = b.opp_tag
ORDER BY b.timestamp DESC
LIMIT 10
"""


DECKS_FETCH_SQL = """
SELECT id, card_ids, evo_card_ids, hero_card_ids
FROM decks
WHERE id = ANY(%s)
"""


CARDS_FETCH_SQL = """
SELECT id, name, rarity, elixir_cost, max_level,
       has_evolution, has_hero, icon_url, evolution_icon_url, hero_icon_url
FROM cards
WHERE id = ANY(%s)
"""


class RecentBattles(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(BATTLES_QUERY)
                battle_rows = cursor.fetchall()

                deck_ids = set()
                for row in battle_rows:
                    deck_ids.add(row[5])   # team_deck_id
                    deck_ids.add(row[10])  # opp_deck_id

                cursor.execute(DECKS_FETCH_SQL, (list(deck_ids),))
                decks_by_id = {
                    deck_id: {
                        "card_ids": card_ids,
                        "evo_card_ids": evo_card_ids,
                        "hero_card_ids": hero_card_ids,
                    }
                    for deck_id, card_ids, evo_card_ids, hero_card_ids in cursor.fetchall()
                }

                all_card_ids = set()
                for deck in decks_by_id.values():
                    all_card_ids.update(deck["card_ids"])
                cursor.execute(CARDS_FETCH_SQL, (list(all_card_ids),))
                cards_by_id = {
                    r[0]: {
                        "id": r[0], "name": r[1], "rarity": r[2],
                        "elixir_cost": r[3], "max_level": r[4],
                        "has_evolution": r[5], "has_hero": r[6],
                        "icon_url": r[7], "evolution_icon_url": r[8],
                        "hero_icon_url": r[9],
                    }
                    for r in cursor.fetchall()
                }

        result = []
        for (
            timestamp, team_tag, team_name, team_rank, team_crowns,
            team_deck_id,
            opp_tag, opp_name, opp_rank, opp_crowns,
            opp_deck_id,
        ) in battle_rows:
            result.append({
                "battle_time": timestamp.isoformat(),
                "team_name": team_name,
                "team_tag": team_tag,
                "team_rank": team_rank,
                "team_deck": hydrate_deck(decks_by_id[team_deck_id], cards_by_id),
                "team_crowns": team_crowns,
                "opp_name": opp_name,
                "opp_tag": opp_tag,
                "opp_rank": opp_rank,
                "opp_deck": hydrate_deck(decks_by_id[opp_deck_id], cards_by_id),
                "opp_crowns": opp_crowns,
            })
        return result
```

- [ ] **Step 2: Smoke-test**

```bash
curl -s http://localhost:5001/battles | python -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'battles'); print('first:', d[0]['team_name'], 'vs', d[0]['opp_name'] if d else 'n/a')"
```

Expected: non-empty list of 10 battles.

- [ ] **Step 3: Commit**

```bash
git add backend/apis/recent_battles.py
git commit -m "Switch /battles to relational schema"
```

---

## Task 8: Recommendation refactor + `/player` endpoint

**Files:**
- Modify: `backend/apis/utils/recommendation.py`
- Modify: `backend/tests/test_recommendation.py`
- Modify: `backend/apis/player.py`

- [ ] **Step 1: Update `pick_recommended_decks` signature**

Replace `backend/apis/utils/recommendation.py` entirely with:

```python
from apis.utils.variants import is_variant_unlocked


def pick_recommended_decks(
    candidate_decks, owned_card_names, level_by_name,
    evolution_level_by_name, limit=3,
):
    """Score and rank candidate decks by playability for the owning player.

    `candidate_decks` is a list of dicts:
      {id, hash, count, card_ids: [...], evo_card_ids: [...],
       hero_card_ids: [...], cards: [{name, ...}]}
    where `cards` is the hydrated card list (already in render order).

    Returns the top `limit` decks ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by count descending.

    Each result is the input dict augmented with:
      - avg_level, fully_playable, missing_variants
    """
    annotated = []
    for deck in candidate_decks:
        names = [c["name"] for c in deck["cards"]]
        if not names:
            continue
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        evo_set = set(deck["evo_card_ids"])
        hero_set = set(deck["hero_card_ids"])
        # Map name -> id once for the missing-variants check
        # (we passed name-keyed unlock data; cards include id under "id"
        # if available — but we keep this purely name-based for backward
        # compat with the existing player payload shape).
        missing = []
        for card in deck["cards"]:
            card_id = card.get("id")
            variant = None
            if card_id is not None:
                if card_id in evo_set:
                    variant = "evolution"
                elif card_id in hero_set:
                    variant = "hero"
            if variant and not is_variant_unlocked(
                evolution_level_by_name.get(card["name"]), variant
            ):
                missing.append({
                    "name": card["name"],
                    "variant": variant,
                })
        annotated.append({
            **deck,
            "avg_level": round(avg_level, 1),
            "fully_playable": not missing,
            "missing_variants": missing,
        })
    annotated.sort(key=lambda d: (not d["fully_playable"], -d["count"]))
    return annotated[:limit]
```

(`slot` is dropped from `missing_variants` entries — was only used for diagnostics in tests; the frontend caption only renders `variant` and `name`.)

- [ ] **Step 2: Update `test_recommendation.py`**

Replace `backend/tests/test_recommendation.py` entirely with:

```python
from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_ids, count, players=None, evo_ids=None, hero_ids=None,
          card_names=None):
    n = len(card_ids)
    names = card_names or [chr(ord("A") + i) for i in range(n)]
    return {
        "id": hash(tuple(card_ids)),
        "hash": "h" + str(card_ids),
        "count": count,
        "card_ids": card_ids,
        "evo_card_ids": evo_ids or [],
        "hero_card_ids": hero_ids or [],
        "cards": [
            {"name": names[i], "id": card_ids[i]}
            for i in range(n)
        ],
        "players": players or [],
    }


def _no_variants(card_names):
    return {n: 0 for n in card_names}


class TestPickRecommendedDecks(TestCase):
    def test_full_ownership_ranked_by_count_descending(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        decks = [
            _deck(ids, 3, card_names=names),
            _deck(ids, 10, card_names=names),
            _deck(ids, 7, card_names=names),
        ]
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(decks, owned, levels, _no_variants(names), limit=3)
        self.assertEqual([d["count"] for d in result], [10, 7, 3])

    def test_excludes_decks_missing_any_card(self):
        ids = list(range(8))
        names_ok = [chr(ord("A") + i) for i in range(8)]
        deck_owned = _deck(ids, 5, card_names=names_ok)
        names_missing = names_ok[:7] + ["Z"]
        deck_missing = _deck(ids, 99, card_names=names_missing)
        owned = set(names_ok)
        levels = {n: 14 for n in names_ok}
        result = pick_recommended_decks(
            [deck_missing, deck_owned], owned, levels, _no_variants(names_ok), limit=3
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        decks = [_deck(ids, i, card_names=names) for i in range(1, 11)]
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(decks, owned, levels, _no_variants(names), limit=3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(pick_recommended_decks([], {"A"}, {"A": 14}, {"A": 0}), [])

    def test_no_owned_cards_returns_empty(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 5, card_names=names)
        self.assertEqual(pick_recommended_decks([deck], set(), {}, {}), [])

    def test_avg_level_computed_and_rounded(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 1, card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        levels[names[7]] = 1
        result = pick_recommended_decks([deck], owned, levels, _no_variants(names), limit=1)
        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        first = _deck(ids, 5, players=["#FIRST"], card_names=names)
        second = _deck(ids, 5, players=["#SECOND"], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(
            [first, second], owned, levels, _no_variants(names), limit=2
        )
        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])

    def test_deck_with_empty_cards_is_skipped(self):
        empty = {"id": 1, "hash": "h", "count": 99, "card_ids": [],
                 "evo_card_ids": [], "hero_card_ids": [], "cards": [],
                 "players": []}
        self.assertEqual(pick_recommended_decks([empty], {"A"}, {"A": 14}, {"A": 0}), [])

    def test_fully_playable_when_all_variants_unlocked(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], hero_ids=[ids[1]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        evos[names[0]] = 1  # evo bit
        evos[names[1]] = 2  # hero bit
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_missing_evo_variant_reported(self):
        ids = list(range(8))
        names = ["RG"] + [chr(ord("B") + i) for i in range(7)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "RG", "variant": "evolution"}],
        )

    def test_missing_hero_variant_reported(self):
        ids = list(range(8))
        names = ["A", "Bowler"] + [chr(ord("C") + i) for i in range(6)]
        deck = _deck(ids, 5, hero_ids=[ids[1]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "Bowler", "variant": "hero"}],
        )

    def test_partially_playable_demoted_below_fully_playable(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        partial = _deck(ids, 99, evo_ids=[ids[0]], players=["#PARTIAL"], card_names=names)
        full = _deck(ids, 5, players=["#FULL"], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([partial, full], owned, levels, evos, limit=2)
        self.assertEqual(result[0]["players"], ["#FULL"])
        self.assertEqual(result[1]["players"], ["#PARTIAL"])

    def test_evolution_level_3_satisfies_both_slots(self):
        ids = list(range(8))
        names = ["Wizard"] + [chr(ord("B") + i) for i in range(7)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        evos["Wizard"] = 3
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertTrue(result[0]["fully_playable"])
```

- [ ] **Step 3: Run recommendation tests**

Run: `docker-compose exec -T backend python -m unittest tests.test_recommendation -v`
Expected: PASS, 13 tests (one fewer than before — `test_slots_3_through_7_dont_trigger_variant_check` is gone since slot logic moved to ingestion).

- [ ] **Step 4: Replace `player.py`**

Replace `backend/apis/player.py` entirely with:

```python
# Python imports
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

# Third party imports
import requests
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.decks import hydrate_deck
from apis.utils.recommendation import pick_recommended_decks
from settings import API_URL, HEADERS, META_WINDOW_DAYS

# Universal in-game level cap. The CR API's per-card `level` is rarity-scaled
# (common max 16, rare 14, legendary 8, etc.); the displayed in-game level is
# `level + (MAX_DISPLAYED_LEVEL - maxLevel)`. Bump this when Supercell raises
# the cap.
MAX_DISPLAYED_LEVEL = 16


CANDIDATES_QUERY = """
SELECT
    d.id, d.hash, d.card_ids, d.evo_card_ids, d.hero_card_ids,
    COUNT(*) AS count
FROM battles b
JOIN decks d ON d.id = b.team_deck_id
WHERE b.timestamp > %s
  AND d.card_ids <@ %s::bigint[]
GROUP BY d.id
ORDER BY count DESC
LIMIT 50
"""


CARDS_FETCH_SQL = """
SELECT id, name, rarity, elixir_cost, max_level,
       has_evolution, has_hero, icon_url, evolution_icon_url, hero_icon_url
FROM cards
WHERE id = ANY(%s)
"""


class Player(Resource):
    def get(self, tag):
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
        owned_card_ids = [c["id"] for c in cards if "id" in c]
        level_by_name = {
            c["name"]: c["level"] + (MAX_DISPLAYED_LEVEL - c["maxLevel"])
            for c in cards
        }
        evolution_level_by_name = {
            c["name"]: (c.get("evolutionLevel") or 0) for c in cards
        }

        # Fetch candidate decks the player owns all 8 cards of, then hydrate.
        cutoff = datetime.now(timezone.utc) - timedelta(days=META_WINDOW_DAYS)
        candidates = []
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CANDIDATES_QUERY, (cutoff, owned_card_ids))
                deck_rows = cursor.fetchall()
                all_card_ids = set()
                for row in deck_rows:
                    all_card_ids.update(row[2])
                if all_card_ids:
                    cursor.execute(CARDS_FETCH_SQL, (list(all_card_ids),))
                    cards_by_id = {
                        r[0]: {
                            "id": r[0], "name": r[1], "rarity": r[2],
                            "elixir_cost": r[3], "max_level": r[4],
                            "has_evolution": r[5], "has_hero": r[6],
                            "icon_url": r[7], "evolution_icon_url": r[8],
                            "hero_icon_url": r[9],
                        }
                        for r in cursor.fetchall()
                    }
                else:
                    cards_by_id = {}

        for deck_id, deck_hash, card_ids, evo_card_ids, hero_card_ids, count in deck_rows:
            deck_dict = {
                "card_ids": card_ids,
                "evo_card_ids": evo_card_ids,
                "hero_card_ids": hero_card_ids,
            }
            hydrated_cards = hydrate_deck(deck_dict, cards_by_id)
            # hydrate_deck strips id; re-attach for the variant check in
            # pick_recommended_decks (which compares against evo/hero_card_ids
            # by id, not name).
            id_by_name = {cards_by_id[cid]["name"]: cid for cid in card_ids if cid in cards_by_id}
            for c in hydrated_cards:
                c["id"] = id_by_name.get(c["name"])
            candidates.append({
                "id": deck_id,
                "hash": deck_hash,
                "count": count,
                "card_ids": card_ids,
                "evo_card_ids": evo_card_ids,
                "hero_card_ids": hero_card_ids,
                "cards": hydrated_cards,
            })

        recommended = pick_recommended_decks(
            candidates, owned_card_names, level_by_name,
            evolution_level_by_name, limit=3,
        )

        # Strip card_ids/evo_card_ids/hero_card_ids before returning (frontend
        # only reads `cards` and the augmented fields).
        for r in recommended:
            r.pop("card_ids", None)
            r.pop("evo_card_ids", None)
            r.pop("hero_card_ids", None)
            r.pop("hash", None)
            for c in r["cards"]:
                c.pop("id", None)

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
                    "level": c["level"] + (MAX_DISPLAYED_LEVEL - c["maxLevel"]),
                    "evolutionLevel": c.get("evolutionLevel") or 0,
                }
                for c in cards
            ],
            "recommended_decks": recommended,
        }
```

- [ ] **Step 5: Smoke-test**

```bash
curl -s "http://localhost:5001/player/%23PPJU2YGP0" | python -c "import sys,json; d=json.load(sys.stdin); print('identity:', d['identity']['name']); print('recs:', len(d['recommended_decks'])); print('first deck cards:', len(d['recommended_decks'][0]['cards']) if d['recommended_decks'] else 0)"
```

Expected: identity name printed, recommendations populated (assuming player owns the cards in any of the top decks). Each deck has 8 cards.

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/player/%23ZZZZZZZZ"
```

Expected: `404`.

- [ ] **Step 6: Run full test suite**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference tests.test_hydrate_deck tests.test_variants tests.test_recommendation tests.test_sanity -v`
Expected: PASS, 40 tests (8 deck inference + 5 hydrate + 13 variants + 13 recommendation + 1 sanity).

- [ ] **Step 7: Commit**

```bash
git add backend/apis/utils/recommendation.py backend/tests/test_recommendation.py backend/apis/player.py
git commit -m "Switch /player and recommendations to relational schema"
```

---

## Task 9: Cleanup

**Files:**
- Delete: `backend/scripts/init_db.py`
- Modify: `backend/scripts/utils/data_utils.py` (delete dead helpers)

- [ ] **Step 1: Drop legacy tables**

```bash
docker-compose exec backend python ./scripts/migrate.py drop_legacy
```

When prompted, type `drop` and press Enter. Expected: `legacy tables dropped`.

- [ ] **Step 2: Delete `init_db.py`**

```bash
rm backend/scripts/init_db.py
```

- [ ] **Step 3: Remove dead helpers from `data_utils.py`**

In `backend/scripts/utils/data_utils.py`, delete these functions (no callers remain):

- `get_card_data`
- `get_deck_data`
- `_battle_deck`
- `get_battle_rows`
- `_slot_active_variant` (replaced by `apis.utils.variants.slot_active_variant`)

Keep: `get_data`, `get_latest_season`, `get_top_players`, `get_player_battlelog_url`, `async_requests`, `get_battlelog_data`, `_parse_battle_time`, `_resolve_rank`, `infer_deck`, `refresh_cards_catalog`, `upsert_deck`, `upsert_player`, `insert_battle`, plus the SQL constants.

- [ ] **Step 4: Verify nothing references the deleted functions**

```bash
docker-compose exec -T backend grep -rn "get_card_data\|get_deck_data\|_battle_deck\|get_battle_rows\|_slot_active_variant" /usr/src/cr_stats/ 2>/dev/null || echo "no references found"
```

Expected: `no references found`.

- [ ] **Step 5: Run full test suite**

Run: `docker-compose exec -T backend python -m unittest tests.test_deck_inference tests.test_hydrate_deck tests.test_variants tests.test_recommendation tests.test_sanity -v`
Expected: PASS, 40 tests.

- [ ] **Step 6: End-to-end smoke**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/cards
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/decks
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/battles
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/player/%23PPJU2YGP0"
```

Expected: `200` for all four.

- [ ] **Step 7: Commit**

```bash
git add -A backend/scripts/init_db.py backend/scripts/utils/data_utils.py
git commit -m "Drop legacy tables and dead aggregation helpers"
```

---

## Done

After Task 9, the relational data model is fully live. Browser-side smoke test:

1. Visit `/cards` — top cards with counts and evolution/hero counts.
2. Visit `/decks` — top decks rendered via the new schema. Variant overlay still works when a player tag is set.
3. Visit `/battles` — recent 10 battles, both decks render with variant icons.
4. Set a player tag in the navbar and visit `/player/%23PPJU2YGP0` — identity + recommended decks. Missing-variants caption renders. Stats panel (avg elixir + 4-card cycle) renders.

If `/decks` and `/cards` look sparse, it's because the rolling 7-day window is empty initially — let a few cron runs populate.
