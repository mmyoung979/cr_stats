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
