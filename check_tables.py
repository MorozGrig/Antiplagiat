import asyncio
from sqlalchemy import text
from app.db.database import async_engine


async def check():
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        )
        tables = result.scalars().all()

        print("Количество таблиц:", len(tables))
        for table in tables:
            print(" -", table)

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(check())
