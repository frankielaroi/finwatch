import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.model_registry_service import promote_model


async def _promote(database_url: str, model_name: str, version: str):
    engine = create_async_engine(database_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionLocal() as db:
        m = await promote_model(db, model_name, version)
        await db.commit()
        if m:
            print(f"Promoted {model_name}@{version}")
        else:
            print(f"Model {model_name}@{version} not found")
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: promote_model.py <ASYNC_DATABASE_URL> <model_name> <version>")
        sys.exit(2)
    url = sys.argv[1]
    model_name = sys.argv[2]
    version = sys.argv[3]
    asyncio.run(_promote(url, model_name, version))
