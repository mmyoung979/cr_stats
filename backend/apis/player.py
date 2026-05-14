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
    COUNT(DISTINCT b.team_tag) AS count
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
