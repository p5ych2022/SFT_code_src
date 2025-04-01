# resource_monitor.py (new file)

"""
This module provides a function to monitor system resources
and store them in MySQL for later analysis.

Requirements:
    - psutil for capturing system CPU and memory usage
    - Access to the MySQL connection/cursor from app.py or a shared config

Important:
    The example below references the same MySQL connection that is
    in app.py. For a production app, consider injecting or passing
    the connection object in a safer way.
"""

import psutil
import datetime
import logging
# If you need to reuse the same MySQL connection,
# you can import it from app.py (circular import warning)
# or instantiate a new connection here using the same config.

from db_config import mysql_conn, mysql_cursor


def monitor_resources():
    """
    Periodically captures and stores system resource data (CPU and memory usage).
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    mem_info = psutil.virtual_memory()
    memory_percent = mem_info.percent

    # Log it to file
    logging.info(f"System CPU Usage: {cpu_percent}%, Memory Usage: {memory_percent}%")

    # Insert into database for historical usage
    sql = """
        INSERT INTO system_metrics (created_at, cpu_usage, memory_usage)
        VALUES (%s, %s, %s)
    """
    val = (datetime.datetime.now(), cpu_percent, memory_percent)
    mysql_cursor.execute(sql, val)
    mysql_conn.commit()
