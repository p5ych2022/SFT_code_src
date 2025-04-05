"""This module defines the ORM models for the task scheduler using SQLAlchemy."""
import os
from sqlalchemy import ( create_engine, Column, Integer, DateTime, Float, String, Text, JSON)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from dotenv import load_dotenv

# Set the base directory for loading environment variables.
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from the .env file.
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Construct the database URL for SQLAlchemy using environment variables.
DATABASE_URL = (
    f"mysql+mysqlconnector://{os.environ.get('mysql_user')}:"
    f"{os.environ.get('mysql_password')}@{os.environ.get('mysql_host')}/"
    f"{os.environ.get('mysql_database')}"
)

# Create an SQLAlchemy engine.
engine = create_engine(DATABASE_URL, echo=True)

# Create a configured "Session" class.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our ORM models.
Base = declarative_base()

class SystemMetric(Base):
    """
    ORM model for the system_metrics table.

    Attributes:
        id (int): Primary key, auto-incremented.
        created_at (datetime): Timestamp when the metric was recorded.
        cpu_usage (float): CPU usage percentage.
        memory_usage (float): Memory usage percentage.
    """
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)

class TaskModel(Base):
    """
    ORM model for the tasks table.

    Attributes:
        id (int): Primary key, auto-incremented.
        task_id (str): Unique identifier for the task.
        task_name (str): Name of the task.
        description (str): Description of the task.
        task_type (str): The type of the task (shell, python, api, etc.).
        execution_params (str): JSON/text-based parameters for execution.
        scheduling_rule (str): JSON/text-based scheduling rule.
        priority (int): Priority level of the task.
        dependencies (str): JSON/text-based dependencies.
    """
    __tablename__ = "tasks"

    task_id = Column(String(50), primary_key=True)
    task_name = Column(String(255), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), nullable=False)
    execution_params = Column(JSON, nullable=False)
    scheduling_rule = Column(JSON, nullable=False)
    priority = Column(Integer)
    dependencies = Column(JSON)

# Create the tables in the database (if they do not exist).
Base.metadata.create_all(bind=engine)
