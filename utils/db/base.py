# db/base.py
# db/base.py
import contextlib
import os
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    insert,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select

# Define logger path
logger.add("./logs/base_db.log", rotation="1 week")
# Load environment variables
load_dotenv()

# Base class for all models
Base = declarative_base()


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

    id = Column(String, primary_key=True, index=True)
    client_timestamp = Column(DateTime, nullable=True)
    server_timestamp = Column(DateTime, default=datetime.now())
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    response_time = Column(Float, nullable=True)
    prompt_hash = Column(String(64), index=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MobileRequestLog(id={self.id}, status={self.status}, model={self.model})>"


def get_async_connection_string() -> str:
    """Construct the ASYNCHRONOUS database connection string."""
    try:
        secret_path = "/run/secrets/postgres_secrets"
        if not os.path.exists(secret_path):
            secret_path = "./secrets/postgres_secrets.txt"

        with open(secret_path, "r") as f:
            password = f.read().strip()

        return (
            f"postgresql+asyncpg://{os.getenv('DB_USER')}:{password}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/"
            f"{os.getenv('DB_NAME')}"
        )
    except Exception as e:
        logger.error(f"Failed to get database connection string: {e}")
        raise


# Create async database engine with connection pooling
async_engine = create_async_engine(
    get_async_connection_string(),
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    echo=True,
)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def execute_query(query: str, params: Optional[dict] = None) -> List[dict]:
    """Execute a query and return results as list of dictionaries"""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def single_insert_query(db_table: Base, query_values: dict) -> None:
    """Execute an insert query for a single row"""
    async with AsyncSessionLocal() as session:
        try:
            stmt = insert(db_table).values(**query_values)
            await session.execute(stmt)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            await session.rollback()
            raise


async def bulk_insert_query(
    db_table: Base,
    query_values: Union[Dict[str, Any], List[Dict[str, Any]]],
    batch_size: int = 100,
) -> None:
    """Execute bulk insert with batch processing"""
    async with AsyncSessionLocal() as session:
        try:
            if isinstance(query_values, dict):
                query_values = [query_values]

            for i in range(0, len(query_values), batch_size):
                batch = query_values[i : i + batch_size]
                stmt = insert(db_table).values(batch)
                await session.execute(stmt)

            await session.commit()
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize the database by creating all tables"""
    async with async_engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise


@contextlib.asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope around a series of operations"""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Session rollback due to error: {e}")
        raise
    finally:
        await session.close()


async def shutdown_session() -> None:
    """Properly close all database connections"""
    await async_engine.dispose()
    logger.info("Database connections closed")


@contextlib.asynccontextmanager
async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency for FastAPI to get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def current_time() -> datetime:
    """Get current time (synchronous utility function)"""
    return datetime.now()
