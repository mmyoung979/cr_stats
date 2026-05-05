# Python imports
import concurrent.futures
import hashlib
import os
from datetime import datetime, timezone
from urllib.parse import quote_plus

# Third party imports
import requests

# Local imports
from settings import API_URL, HEADERS

# Global variables
COUNT = "count"
NAME = "name"
CARDS = "cards"
RANKED = "pathOfLegend"


def get_data(url):
    return requests.get(url, headers=HEADERS).json()


def get_seasons():
    url = API_URL + "/locations/global/seasons"
    return get_data(url)


def get_latest_season():
    seasons = get_seasons()
    return seasons["items"][-1]["id"]


def get_top_players(season):
    url = API_URL + f"/locations/global/pathoflegend/{season}/rankings/players"
    data = get_data(url)
    return [player["tag"] for player in data["items"]]


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
    season = get_latest_season()
    players = get_top_players(season)[:player_count]

    # Gather URLs for async API calls
    urls = []
    for player in players:
        battle_log_url = get_player_battlelog_url(player)
        urls.append(battle_log_url)

    # Gather data asynchronously
    return async_requests(urls)


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
                        "hasEvolution": card.get("maxEvolutionLevel"),
                        "icon": card["iconUrls"]["medium"],
                        "evolvedIcon": card["iconUrls"].get("evolutionMedium"),
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
            if name not in card_data:
                card_data[name] = {
                    COUNT: 0,
                    "evolutionCount": 0,
                    "hasEvolution": card.get("maxEvolutionLevel") is not None,
                    "icon": card["iconUrls"]["medium"],
                    "evolvedIcon": card["iconUrls"].get("evolutionMedium", None),
                }

            card_data[name][COUNT] += 1
            if idx < 2 and card.get("maxEvolutionLevel") is not None:
                card_data[name]["evolutionCount"] += 1

    return [
        {
            NAME: name,
            COUNT: data[COUNT],
            "evolutionCount": data["evolutionCount"],
            "hasEvolution": data["hasEvolution"],
            "icon": data["icon"],
            "evolvedIcon": data.get("evolvedIcon"),
        }
        for name, data in card_data.items()
    ]


def _battle_deck(side: dict) -> list[dict]:
    return [
        {
            NAME: card[NAME],
            "hasEvolution": card.get("maxEvolutionLevel") is not None,
            "icon": card["iconUrls"]["medium"],
            "evolvedIcon": card["iconUrls"].get("evolutionMedium"),
        }
        for card in side[CARDS]
    ]


def _parse_battle_time(raw: str) -> datetime:
    # Clash Royale format: "20260504T123045.000Z"
    return datetime.strptime(raw, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def get_battle_rows(battlelog_data):
    """Flatten battlelogs into one row per pathOfLegend battle.

    Returned dicts match the recent_battles table columns.
    """
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
                    "team_name": team[0].get("name"),
                    "team_deck": _battle_deck(team[0]),
                    "team_crowns": team[0].get("crowns"),
                    "opp_tag": opp[0].get("tag"),
                    "opp_name": opp[0].get("name"),
                    "opp_deck": _battle_deck(opp[0]),
                    "opp_crowns": opp[0].get("crowns"),
                    "fetched_at": fetched_at,
                })
            except (KeyError, ValueError):
                continue
    return rows
