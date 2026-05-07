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
