# db/base.py
from numpy import insert
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from loguru import logger
from typing import Any, Type, Union, Dict, List
import contextlib
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, JSON

# Define logger path
logger.add("./logs/base_db.log", rotation="1 week")
# Load environment variables
load_dotenv()

# Base class for all models
Base = declarative_base()


# Common data classes to be reused
class CameraTraffic(Base):
    __tablename__ = "camera_traffic"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True))
    camera_name = Column(String(50))
    count = Column(Integer)
    location = Column(String(50))
    direction = Column(String(10))
    day_of_week = Column(String(10))
    is_holiday = Column(Boolean)


class MobileRequestLog(Base):
    __tablename__ = "mobile_request_logs"

    id = Column(String, primary_key=True, index=True)  # Same as request_id
    client_timestamp = Column(DateTime, nullable=True)  # From mobile client
    server_timestamp = Column(DateTime, default=datetime.now())  # When we received it
    prompt = Column(Text, nullable=False)  # User's prompt
    response = Column(Text, nullable=True)  # AI response (nullable for errors)
    status = Column(
        String(50), nullable=False
    )  # 'received', 'processing', 'completed', 'error'
    model = Column(String(100), nullable=True)  # Model used
    response_time = Column(Float, nullable=True)  # In seconds
    prompt_hash = Column(String(64), index=True)  # For deduplication
    error_message = Column(Text, nullable=True)  # If status='error'

    def __repr__(self):
        return f"<OllamaRequestLog(id={self.id}, status={self.status}, model={self.model})>"


def get_connection_string() -> str:
    """Construct the database connection string from environment variables"""
    try:
        with open("/app/secrets/postgres_secrets.txt", "r") as f:
            password = f.read().strip()

        return (
            f"postgresql://{os.getenv('DB_USER')}:{password}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/"
            f"{os.getenv('DB_NAME')}"
        )
    except Exception as e:
        logger.error(f"Failed to get database connection string: {e}")
        raise


# Create database engine with connection pooling
engine = create_engine(
    get_connection_string(),
    pool_pre_ping=True,  # Check connections before using them
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_size=10,  # Number of connections to keep open
    max_overflow=20,  # Allow 20 additional connections during spikes
    echo=True,  # Set to True for SQL query logging
    connect_args={
        "connect_timeout": 5,  # 5 second connection timeout
        "keepalives": 1,  # Enable TCP keepalive
        "keepalives_idle": 30,  # Seconds before first keepalive
        "keepalives_interval": 10,  # Interval between keepalives
        "keepalives_count": 5,  # Number of keepalives before dropping
    },
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,  # Automatically flush changes
    autocommit=False,  # No automatic commits
    expire_on_commit=True,  # Expire instances after commit
)

# Scoped session for thread safety
Session = scoped_session(SessionLocal)


# for the first version of stats_db
def execute_query(query: str, params: dict) -> list:
    """Execute a query and return results as list of dictionaries"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return []


async def single_insert_query(db_table_name: Base, query_values: dict):
    """Execute an insert query based on the databse name"""
    try:
        with engine.connect() as conn:
            insert_query = insert(db_table_name).values(**query_values)
            conn.execute(insert_query)
            conn.commit()
    except ValueError as e:
        logger.error(f"Failed to insert data due to {e}")
        raise


async def bulk_insert_query(
    db_table_name: Base,
    query_values: Union[Dict[str, Any], List[Dict[str, Any]]],
    batch_size: int,
):
    try:
        with engine.connect() as conn:
            # Handle single row (convert to list)
            if isinstance(query_values, dict):
                query_values = [query_values]

            # Split into batches (to avoid huge transactions)
            for i in range(0, len(query_values), batch_size):
                batch = query_values[i : i + batch_size]
                stmt = insert(db_table_name).values(batch)
                conn.execute(stmt)

            conn.commit()
    except Exception as e:
        logger.error(f"Failed to insert data into {db_table_name.__tablename__}: {e}")
        raise


def init_db() -> None:
    """Initialize the database by creating all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@contextlib.contextmanager
def session_scope() -> Any:
    """Provide a transactional scope around a series of operations"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rollback due to error: {e}")
        raise
    finally:
        session.close()


def shutdown_session() -> None:
    """Properly close all database connections"""
    Session.remove()
    engine.dispose()
    logger.info("Database connections closed")


# Add utility functions that might be used across models
def current_time() -> datetime:
    """Get current time"""
    return datetime.now()


def get_db():
    db = Session()
    try:
        yield db
    except ValueError:
        db.rollback()
        raise
    finally:
        db.close()
