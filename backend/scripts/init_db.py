# Local imports
from apis.utils.db_utils import make_connection

if __name__ == "__main__":
    with make_connection() as connection:
        with connection.cursor() as cursor:
            sql = """
            CREATE TABLE IF NOT EXISTS common_cards (
                id SERIAL PRIMARY KEY,
                cards JSON,
                timestamp timestamp with time zone
            );
            CREATE TABLE IF NOT EXISTS common_decks (
                id SERIAL PRIMARY KEY,
                decks JSON,
                timestamp timestamp with time zone
            );
            CREATE TABLE IF NOT EXISTS recent_battles (
                battle_time  TIMESTAMP WITH TIME ZONE NOT NULL,
                team_tag     TEXT NOT NULL,
                team_name    TEXT,
                team_deck    JSON NOT NULL,
                team_crowns  INT,
                opp_tag      TEXT,
                opp_name     TEXT,
                opp_deck     JSON NOT NULL,
                opp_crowns   INT,
                fetched_at   TIMESTAMP WITH TIME ZONE NOT NULL,
                PRIMARY KEY (battle_time, team_tag)
            );
            CREATE INDEX IF NOT EXISTS recent_battles_battle_time_idx
                ON recent_battles (battle_time DESC);
            """
            cursor.execute(sql)
            connection.commit()
