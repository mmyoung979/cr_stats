# Python imports
import concurrent.futures
import hashlib
import os
from datetime import date, datetime, timezone
from urllib.parse import quote_plus

# Third party imports
import requests

# Local imports
from settings import API_URL, HEADERS
from apis.utils.db_utils import make_connection
from apis.utils.variants import slot_active_variant

# Global variables
COUNT = "count"
NAME = "name"
CARDS = "cards"
RANKED = "pathOfLegend"


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


def get_deck_data(battlelog_data):
    # Find most commonly used cards among top players
    deck_data: dict = {}
    for battlelog in battlelog_data:
        try:
            deck: list[dict] = []
            for battle in battlelog:
                if battle.get("type") == RANKED:
                    deck = battle["team"][0][CARDS]
                    player = battle["team"][0]["tag"]
        except KeyError:
            continue

        # If no pathOfLegend battles found, skip to next battlelog
        if len(deck) == 0:
            continue

        # Parse deck data
        sorted_deck_names: list[str] = sorted(card[NAME] for card in deck)
        joined_deck_names: str = ",".join(sorted_deck_names)
        deck_hash: str = hashlib.sha256(joined_deck_names.encode()).hexdigest()
        if deck_hash not in deck_data:
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
        deck_data[deck_hash][COUNT] += 1
        deck_data[deck_hash]["players"].append(player)

    return [
        {
            COUNT: deck[COUNT],
            CARDS: deck[CARDS],
            "players": deck["players"],
        }
        for deck in deck_data.values()
    ]


def _slot_active_variant(slot_idx, hero_icon, ev_icon):
    """Per-slot rule for which variant is active in this position.

    Slot 0 = evolution slot. Slot 1 = hero slot (evolution allowed as
    fallback for malformed decks). Slot 2 = hero or evolution choice
    (defaults to hero when both are unlocked).
    """
    if slot_idx == 0:
        return "evolution" if ev_icon else None
    if slot_idx in (1, 2):
        if hero_icon:
            return "hero"
        if ev_icon:
            return "evolution"
    return None


def get_card_data(battlelog_data):
    # Find most commonly used cards among top players
    card_data: dict = {}
    for battlelog in battlelog_data:
        try:
            deck: list[dict] = []
            for battle in battlelog:
                if battle.get("type") == RANKED:
                    deck = battle["team"][0][CARDS]
        except KeyError:
            continue

        # If no pathOfLegend battles found, skip to next battlelog
        if len(deck) == 0:
            continue

        # Parse card data
        for idx, card in enumerate(deck):
            name: str = card[NAME]
            icons = card.get("iconUrls", {})
            ev_icon = icons.get("evolutionMedium")
            hero_icon = icons.get("heroMedium")

            entry = card_data.setdefault(name, {
                COUNT: 0,
                "evolutionCount": 0,
                "heroCount": 0,
                "icon": icons.get("medium"),
                "evolvedIcon": None,
                "heroIcon": None,
            })
            # Capture variant icons whenever we see them — don't lock to first-seen.
            if ev_icon and not entry["evolvedIcon"]:
                entry["evolvedIcon"] = ev_icon
            if hero_icon and not entry["heroIcon"]:
                entry["heroIcon"] = hero_icon

            entry[COUNT] += 1
            variant = _slot_active_variant(idx, hero_icon, ev_icon)
            if variant == "hero":
                entry["heroCount"] += 1
            elif variant == "evolution":
                entry["evolutionCount"] += 1

    return [
        {
            NAME: name,
            COUNT: data[COUNT],
            "evolutionCount": data["evolutionCount"],
            "heroCount": data["heroCount"],
            "hasEvolution": data["evolvedIcon"] is not None,
            "hasHero": data["heroIcon"] is not None,
            "icon": data["icon"],
            "evolvedIcon": data["evolvedIcon"],
            "heroIcon": data["heroIcon"],
        }
        for name, data in card_data.items()
    ]


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


def _parse_battle_time(raw: str) -> datetime:
    # Clash Royale format: "20260504T123045.000Z"
    return datetime.strptime(raw, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def _resolve_rank(side, rank_by_tag):
    """Prefer the per-battle globalRank, fall back to the seasonal PoL ranking."""
    return side.get("globalRank") or rank_by_tag.get(side.get("tag"))


def get_battle_rows(battlelog_data, rank_by_tag=None):
    """Flatten battlelogs into one row per pathOfLegend battle.

    Returned dicts match the recent_battles table columns.
    """
    rank_by_tag = rank_by_tag or {}
    fetched_at = datetime.now(timezone.utc)
    rows = []
    for battlelog in battlelog_data:
        if not isinstance(battlelog, list):
            continue
        for battle in battlelog:
            if battle.get("type") != RANKED:
                continue
            team = battle.get("team") or []
            opp = battle.get("opponent") or []
            if not team or not opp:
                continue
            try:
                rows.append({
                    "battle_time": _parse_battle_time(battle["battleTime"]),
                    "team_tag": team[0]["tag"],
                    "team_rank": _resolve_rank(team[0], rank_by_tag),
                    "team_name": team[0].get("name"),
                    "team_deck": _battle_deck(team[0]),
                    "team_crowns": team[0].get("crowns"),
                    "opp_tag": opp[0].get("tag"),
                    "opp_name": opp[0].get("name"),
                    "opp_rank": _resolve_rank(opp[0], rank_by_tag),
                    "opp_deck": _battle_deck(opp[0]),
                    "opp_crowns": opp[0].get("crowns"),
                    "fetched_at": fetched_at,
                })
            except (KeyError, ValueError):
                continue
    return rows


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
