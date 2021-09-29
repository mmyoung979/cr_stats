"""
Variables & configurations that can be accessed throughout the microservice
"""
# Python imports
import os

# Third party imports
from psycopg2 import connect
from pytz import timezone

API_KEY = os.environ.get("API_KEY")
API_URL = "https://api.clashroyale.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
TZ = timezone("UTC")
