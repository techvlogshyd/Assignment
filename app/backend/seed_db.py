"""Apply seed data on first startup (skips if users table is non-empty)."""

import asyncio
import os

import asyncpg


async def seed() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)

    count = await conn.fetchval("select count(*) from users")
    if count and count > 0:
        print("seed: users table already populated, skipping")
        await conn.close()
        return

    seed_sql = open("/seed/seed.sql").read()
    await conn.execute(seed_sql)
    print("seed: inserted users and orders")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
