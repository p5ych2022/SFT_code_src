import redis
import mysql.connector

# Redis client for caching task info and status
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# MySQL connection setup
mysql_conn = mysql.connector.connect(
    host='localhost',
    user='test',
    password='test',
    database='task_scheduler'
)
mysql_cursor = mysql_conn.cursor()