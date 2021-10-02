# Python imports
import concurrent.futures
from datetime import datetime
import json
from time import time
from urllib.parse import quote_plus

# Third party imports
import requests
from flask import jsonify
from flask_restful import Resource

# Local imports
from settings import API_URL, HEADERS, TZ
from apis.utils.db_utils import make_connection


class MostCommonCards(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                sql = """
                SELECT cards
                FROM common_cards
                ORDER BY timestamp DESC
                LIMIT 1
                """
                cursor.execute(sql)
                results = cursor.fetchall()
        return results[0][0]
