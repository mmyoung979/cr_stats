# Third party imports
from psycopg2 import connect

# Local imports
from settings import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD


def make_connection():
    return connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
