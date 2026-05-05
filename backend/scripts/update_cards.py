# Python imports
import json
from datetime import datetime

# Third party imports
from psycopg2.extras import Json, execute_values

# Local imports
from apis.utils.db_utils import make_connection
from scripts.utils.data_utils import (
    get_battle_rows,
    get_battlelog_data,
    get_card_data,
    get_deck_data,
)
from settings import TZ


BATTLE_INSERT_SQL = """
INSERT INTO recent_battles (
    battle_time, team_tag, team_name, team_rank, team_deck, team_crowns,
    opp_tag, opp_name, opp_deck, opp_crowns, fetched_at
) VALUES %s
ON CONFLICT (battle_time, team_tag) DO NOTHING
"""


def update_common_cards_and_decks(player_count: int = 50):
    """
    Fetches battle log data, processes it to get common cards, common decks,
    and recent battles, and updates the database with the latest data.
    """
    battlelog_data, rank_by_tag = get_battlelog_data(player_count)
    card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)
    battle_rows = get_battle_rows(battlelog_data, rank_by_tag)

    with make_connection() as connection:
        with connection.cursor() as cursor:
            sql = f"""
            INSERT INTO common_cards(
                cards,
                timestamp
            )
            VALUES(
                '{card_data}',
                '{datetime.now(TZ)}'
            );
            INSERT INTO common_decks(
                decks,
                timestamp
            )
            VALUES(
                '{deck_data}',
                '{datetime.now(TZ)}'
            );
            """
            cursor.execute(sql)

            if battle_rows:
                values = [
                    (
                        r["battle_time"],
                        r["team_tag"],
                        r["team_name"],
                        r["team_rank"],
                        Json(r["team_deck"]),
                        r["team_crowns"],
                        r["opp_tag"],
                        r["opp_name"],
                        Json(r["opp_deck"]),
                        r["opp_crowns"],
                        r["fetched_at"],
                    )
                    for r in battle_rows
                ]
                execute_values(cursor, BATTLE_INSERT_SQL, values)

            connection.commit()


if __name__ == "__main__":
    player_count: int = 100
    update_common_cards_and_decks(player_count)
    print("Common cards, decks, and recent battles updated successfully.")
