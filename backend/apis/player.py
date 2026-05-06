# Python imports
from urllib.parse import quote_plus

# Third party imports
import requests
from flask_restful import Resource

# Local imports
from apis.utils.db_utils import make_connection
from apis.utils.recommendation import pick_recommended_decks
from settings import API_URL, HEADERS


class Player(Resource):
    def get(self, tag):
        # `tag` arrives URL-decoded by Flask (e.g. "#PPJU2YGP0"). The CR API
        # itself wants the leading # encoded as %23, so re-encode here.
        try:
            cr = requests.get(
                f"{API_URL}/players/{quote_plus(tag)}",
                headers=HEADERS,
                timeout=10,
            )
            if cr.status_code == 404:
                return {"error": "player not found"}, 404
            if cr.status_code != 200:
                return {"error": "upstream error"}, 502
            player = cr.json()
        except requests.exceptions.RequestException:
            return {"error": "upstream error"}, 502
        except ValueError:
            return {"error": "upstream error"}, 502

        cards = player.get("cards", []) or []
        owned_card_names = {c["name"] for c in cards}
        level_by_name = {c["name"]: c["level"] for c in cards}

        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT decks FROM common_decks ORDER BY timestamp DESC LIMIT 1"
                )
                row = cursor.fetchone()
        decks = row[0] if row else []

        recommended = pick_recommended_decks(
            decks, owned_card_names, level_by_name, limit=3
        )

        pol = player.get("currentPathOfLegendSeasonResult") or {}
        return {
            "identity": {
                "name": player.get("name"),
                "tag": player.get("tag"),
                "trophies": player.get("trophies"),
                "pol_rank": pol.get("rank"),
            },
            "cards": [
                {"name": c["name"], "level": c["level"], "maxLevel": c["maxLevel"]}
                for c in cards
            ],
            "recommended_decks": recommended,
        }
