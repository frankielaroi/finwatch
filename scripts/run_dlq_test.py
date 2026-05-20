import asyncio
import logging
import uuid

from app.db.session import AsyncSessionLocal
from app.models.worker import ProfileDLQ
from app.tasks.dlq_retry_worker import start_worker, stop_worker


async def insert_dummy_dlq():
    async with AsyncSessionLocal() as db:
        item = ProfileDLQ(
            source="test",
            item_id=str(uuid.uuid4()),
            payload={"note": "smoke test"},
            attempts=0,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        logging.info("Inserted DLQ item %s", item.id)
        return item.id


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("finwatch.dlq_retry").setLevel(logging.DEBUG)

    await insert_dummy_dlq()

    # start the DLQ worker with a short interval so it runs a few times
    start_worker(interval_seconds=2, batch_size=10, max_attempts=3)
    logging.info("DLQ worker started for test (will run for 8 seconds)")

    # allow the worker to run a few iterations
    await asyncio.sleep(8)

    # stop the worker
    await stop_worker()
    logging.info("DLQ worker stopped; test complete")


if __name__ == "__main__":
    asyncio.run(main())
