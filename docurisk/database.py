from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from docurisk.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=True
)


SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

async def init_database():
    from docurisk import models

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)