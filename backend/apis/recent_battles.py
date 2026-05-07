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
