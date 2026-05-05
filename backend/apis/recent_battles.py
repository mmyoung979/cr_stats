# Third party imports
from apis.utils.db_utils import make_connection
from flask_restful import Resource


class RecentBattles(Resource):
    def get(self):
        with make_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT battle_time, team_name, team_tag, team_deck, team_crowns,
                           opp_name, opp_tag, opp_deck, opp_crowns
                    FROM recent_battles
                    ORDER BY battle_time DESC
                    LIMIT 10
                    """
                )
                rows = cursor.fetchall()
        return [
            {
                "battle_time": battle_time.isoformat(),
                "team_name": team_name,
                "team_tag": team_tag,
                "team_deck": team_deck,
                "team_crowns": team_crowns,
                "opp_name": opp_name,
                "opp_tag": opp_tag,
                "opp_deck": opp_deck,
                "opp_crowns": opp_crowns,
            }
            for (
                battle_time,
                team_name,
                team_tag,
                team_deck,
                team_crowns,
                opp_name,
                opp_tag,
                opp_deck,
                opp_crowns,
            ) in rows
        ]
