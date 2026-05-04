# Python imports
import json
from datetime import datetime

# Local imports
from apis.utils.db_utils import make_connection
from scripts.utils.data_utils import get_battlelog_data, get_card_data, get_deck_data
from settings import TZ


def update_common_cards_and_decks(player_count: int = 50):
    """
    Fetches battle log data, processes it to get common cards and decks,
    and updates the database with the latest data.
    """
    battlelog_data = get_battlelog_data(player_count)
    card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)

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
            connection.commit()


if __name__ == "__main__":
    player_count: int = 100
    update_common_cards_and_decks(player_count)
    print("Common cards and decks updated successfully.")
