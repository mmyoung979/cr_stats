"""
Get analytics about top players in Clash Royale
"""
# Third party imports
from flask_restful import Api

# Local imports
from __init__ import create_app
from apis.most_common_cards import MostCommonCards

# Instantiate app
app = create_app()
api = Api(app)
api.add_resource(MostCommonCards, "/")
