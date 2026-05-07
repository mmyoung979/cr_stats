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
