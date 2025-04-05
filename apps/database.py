from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from apps.settings import settings



engine = create_async_engine(settings.DATABASE_URL_asyncpg)

db_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session():
    async with db_session() as session:
        yield session

