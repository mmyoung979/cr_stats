"""
Variables & configurations that can be accessed throughout the microservice
"""

# Python imports
import os

# Third party imports
from dotenv import load_dotenv
from pytz import timezone

env_file_path: str = str(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(env_file_path)

API_KEY = os.environ.get("API_KEY")
API_URL = "https://api.clashroyale.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
TZ = timezone("UTC")
