# Python imports
import concurrent.futures
import json
from datetime import datetime
from time import time
from urllib.parse import quote_plus

# Third party imports
import requests

# Local imports
from settings import API_URL, HEADERS, TZ
from apis.utils.db_utils import make_connection


def get_data(url):
    return requests.get(url, headers=HEADERS).json()


def get_season():
    url = API_URL + "/locations/global/seasons"
    return get_data(url)


def get_latest_season():
    return get_season()["items"][-1]["id"]


def get_top_players(season):
    url = API_URL + f"/locations/global/seasons/{season}/rankings/players"
    data = get_data(url)
    return [player["tag"] for player in data["items"]]


def get_player_deck_url(player):
    player = quote_plus(player)
    url = API_URL + f"/players/{player}"
    return url


def async_requests(urls):
    result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(get_data, url) for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            data = future.result()
            result.append(data)
    return result


def count_results(player_count):
    season = get_latest_season()
    players = get_top_players(season)[:player_count]

    # Gather URLs for async API calls
    urls = []
    for player in players:
        url = get_player_deck_url(player)
        urls.append(url)

    # Gather data via async requests
    data = async_requests(urls)

    # Find most commonly used cards among top players
    result = {}
    for player in data:
        try:
            deck = player["currentDeck"]
        except KeyError:
            continue

        for card in deck:
            name = card["name"]
            if name not in result:
                result[name] = {"count": 1, "icon": card["iconUrls"]["medium"]}
            else:
                result[name]["count"] += 1

    # Sort results for output
    return [
        {
            "name": card,
            "count": values["count"],
            "icon": values["icon"],
        }
        for card, values in result.items()
    ]


if __name__ == "__main__":
    data = json.dumps(count_results(50), indent=2)
    with make_connection() as connection:
        with connection.cursor() as cursor:
            sql = f"""
            INSERT INTO common_cards(
                cards,
                timestamp
            )
            VALUES(
                '{data}',
                '{datetime.now(TZ)}'
            )
            """
            cursor.execute(sql)
            connection.commit()
