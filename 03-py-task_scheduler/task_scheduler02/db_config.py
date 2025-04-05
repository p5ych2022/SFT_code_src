import redis
import mysql.connector
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


# Load environment variables from the .env file located at the same level as manage.py
load_dotenv(os.path.join(BASE_DIR, '.env'))
print(os.path.join(BASE_DIR, '.env'))
# Redis client for caching task info and status
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# MySQL connection setup
mysql_conn = mysql.connector.connect(
    host=os.environ.get('mysql_host'),
    user=os.environ.get('mysql_user'),
    password=os.environ.get('mysql_password'),
    database=os.environ.get('mysql_database')
)

# MySQL cursor to execute queries
mysql_cursor = mysql_conn.cursor()