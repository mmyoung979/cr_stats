# Python imports
import concurrent.futures
import json
from time import time
from urllib.parse import quote_plus

# Third party imports
import requests
from flask import jsonify
from flask_restful import Resource

# Local imports
from settings import API_URL, HEADERS
from apis.utils.db_utils import make_connection


class MostCommonCards(Resource):
    def get_data(self, url):
        return requests.get(url, headers=HEADERS).json()

    def get_season(self):
        url = API_URL + "/locations/global/seasons"
        return self.get_data(url)

    def get_latest_season(self):
        return self.get_season()["items"][-1]["id"]

    def get_top_players(self, season):
        url = API_URL + f"/locations/global/seasons/{season}/rankings/players"
        data = self.get_data(url)
        return [player["tag"] for player in data["items"]]

    def get_player_deck_url(self, player):
        player = quote_plus(player)
        url = API_URL + f"/players/{player}"
        return url

    def async_requests(self, urls):
        result = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(self.get_data, url) for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                data = future.result()
                result.append(data)
        return result

    def count_results(self, player_count):
        season = self.get_latest_season()
        players = self.get_top_players(season)[:player_count]

        # Gather URLs for async API calls
        urls = []
        for player in players:
            url = self.get_player_deck_url(player)
            urls.append(url)

        # Gather data via async requests
        data = self.async_requests(urls)

        # Find most commonly used cards among top players
        result = {}
        for player in data:
            deck = player["currentDeck"]
            for card in deck:
                name = card["name"]
                if name not in result:
                    result[name] = {"count": 1, "icon": card["iconUrls"]["medium"]}
                else:
                    result[name]["count"] += 1
        try:
            total = 0
            for card in result:
                total += result[card]["count"]
            assert total == player_count * 8
        except AssertionError:
            raise AssertionError("Async requests did not perform correctly.")

        # Sort results for output
        return [
            {
                "name": card,
                "count": values["count"],
                "icon": values["icon"],
            }
            for card, values in result.items()
        ]

    def get(self):
        data = self.count_results(50)
        with make_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS random (name VARCHAR (100) UNIQUE NOT NULL);"
                )
                conn.commit()
        return jsonify(data)
