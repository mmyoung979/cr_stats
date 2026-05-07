# Python imports
import concurrent.futures
import hashlib
from datetime import date, datetime, timezone
from urllib.parse import quote_plus

# Third party imports
import requests

# Local imports
from settings import API_URL, HEADERS
from apis.utils.db_utils import make_connection
from apis.utils.variants import slot_active_variant


def get_data(url):
    return requests.get(url, headers=HEADERS).json()


def get_latest_season():
    """The CR API only publishes finalized PoL rankings for completed months
    (current month returns 404, and the /seasons listing endpoint returns
    items with null ids). Returns the YYYY-MM ID of the previous calendar
    month, which is the most recent queryable season."""
    today = date.today()
    if today.month == 1:
        return f"{today.year - 1}-12"
    return f"{today.year}-{today.month - 1:02d}"


def get_top_players(season):
    url = API_URL + f"/locations/global/pathoflegend/{season}/rankings/players?limit=1000"
    data = get_data(url)
    return [(player["tag"], player["rank"]) for player in data["items"]]


def get_player_battlelog_url(player):
    player = quote_plus(player)
    url = API_URL + f"/players/{player}/battlelog"
    return url


def async_requests(urls):
    result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(get_data, url) for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            data = future.result()
            result.append(data)
    return result


def get_battlelog_data(player_count):
    """Returns (battlelogs, rank_by_tag).

    rank_by_tag covers the full path-of-legend ranking returned by the API
    (up to ~1000 players) so it can be used as a fallback rank lookup for
    both team and opponent tags. Battlelogs are only fetched for the top
    `player_count`.
    """
    season = get_latest_season()
    all_players = get_top_players(season)
    rank_by_tag = {tag: rank for tag, rank in all_players}

    top_n = all_players[:player_count]
    urls = [get_player_battlelog_url(tag) for tag, _ in top_n]
    battlelogs = async_requests(urls)
    return battlelogs, rank_by_tag


def _parse_battle_time(raw: str) -> datetime:
    # Clash Royale format: "20260504T123045.000Z"
    return datetime.strptime(raw, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def _resolve_rank(side, rank_by_tag):
    """Prefer the per-battle globalRank, fall back to the seasonal PoL ranking."""
    return side.get("globalRank") or rank_by_tag.get(side.get("tag"))


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
