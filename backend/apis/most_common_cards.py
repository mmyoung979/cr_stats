# Python imports
from datetime import datetime, timedelta, timezone

# Third party imports
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.card_types import card_type
from settings import META_WINDOW_DAYS


CARDS_QUERY = """
WITH deck_slots AS (
    SELECT
        b.team_tag,
        slot.card_id,
        d.evo_card_ids,
        d.hero_card_ids
    FROM battles b
    JOIN decks d ON d.id = b.team_deck_id,
    UNNEST(d.card_ids) AS slot(card_id)
    WHERE b.timestamp > %s
),
usage AS (
    SELECT
        ds.card_id,
        COUNT(DISTINCT ds.team_tag) AS count,
        COUNT(DISTINCT ds.team_tag) FILTER (WHERE ds.card_id = ANY(ds.evo_card_ids))  AS evolution_count,
        COUNT(DISTINCT ds.team_tag) FILTER (WHERE ds.card_id = ANY(ds.hero_card_ids)) AS hero_count
    FROM deck_slots ds
    GROUP BY ds.card_id
)
-- Start FROM the full card catalog and LEFT JOIN usage so cards no top
-- player ran still appear, with zeroed counts.
SELECT
    c.id,
    COALESCE(u.count, 0) AS count,
    COALESCE(u.evolution_count, 0) AS evolution_count,
    COALESCE(u.hero_count, 0) AS hero_count,
    c.name, c.elixir_cost, c.has_evolution, c.has_hero,
    c.icon_url, c.evolution_icon_url, c.hero_icon_url, c.rarity
FROM cards c
LEFT JOIN usage u ON u.card_id = c.id
ORDER BY count DESC, c.name ASC
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
                "rarity": rarity,
                "type": card_type(name),
            }
            for (
                _card_id, count, evolution_count, hero_count,
                name, elixir_cost, has_evolution, has_hero,
                icon_url, evolution_icon_url, hero_icon_url, rarity,
            ) in rows
        ]
