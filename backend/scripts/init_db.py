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
            )
            """
            cursor.execute(sql)
            connection.commit()
