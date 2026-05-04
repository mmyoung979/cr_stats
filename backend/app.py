"""
Get analytics about top players in Clash Royale
"""

# Local imports
from __init__ import create_app
from apis.most_common_cards import MostCommonCards
from apis.most_common_decks import MostCommonDecks

# Third party imports
from flask_restful import Api

# Instantiate app
app = create_app()
api = Api(app)
api.add_resource(MostCommonCards, "/cards")
api.add_resource(MostCommonDecks, "/decks")
