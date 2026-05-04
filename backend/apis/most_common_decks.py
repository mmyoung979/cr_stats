# Third party imports
from apis.utils.db_utils import make_connection
from flask_restful import Resource


class MostCommonDecks(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                sql = """
                SELECT decks
                FROM common_decks
                ORDER BY timestamp DESC
                LIMIT 1
                """
                cursor.execute(sql)
                results = cursor.fetchall()
        return results[0][0]
