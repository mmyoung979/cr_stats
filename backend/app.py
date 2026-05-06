"""
Get analytics about top players in Clash Royale
"""

# Local imports
from __init__ import create_app
from apis.most_common_cards import MostCommonCards
from apis.most_common_decks import MostCommonDecks
from apis.player import Player
from apis.recent_battles import RecentBattles

# Third party imports
from flask_restful import Api

# Instantiate app
app = create_app()
api = Api(app)
api.add_resource(MostCommonCards, "/cards")
api.add_resource(MostCommonDecks, "/decks")
api.add_resource(RecentBattles, "/battles")
api.add_resource(Player, "/player/<path:tag>")
