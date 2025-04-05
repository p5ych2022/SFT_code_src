"""This module provides a function to monitor system resources and store them in MySQL using ORM."""

import psutil
import datetime
import logging
from models import SessionLocal, SystemMetric

def monitor_resources():
    """
    Periodically captures system resource data (CPU and memory usage)
    and inserts it into the system_metrics table via SQLAlchemy ORM.
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    mem_info = psutil.virtual_memory()
    memory_percent = mem_info.percent

    # Log resource usage to file
    logging.info(f"System CPU Usage: {cpu_percent}%, Memory Usage: {memory_percent}%")

    # Prepare a new SystemMetric object
    metric_record = SystemMetric(
        created_at=datetime.datetime.now(),
        cpu_usage=cpu_percent,
        memory_usage=memory_percent
    )

    # Use the ORM session to insert the record into the database
    session = SessionLocal()
    try:
        session.add(metric_record)
        session.commit()
    finally:
        session.close()
