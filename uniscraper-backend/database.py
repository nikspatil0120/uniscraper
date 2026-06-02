# database.py
# Creates a single Motor AsyncIOMotorClient on module import (singleton pattern).
# Exports collection references: scrape_results_collection, batch_jobs_collection.
# Exports ping() async function to test the connection on startup.
# Never creates multiple connections — module-level singleton only.

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

logger = logging.getLogger(__name__)

# Module-level singleton client
_client: AsyncIOMotorClient = None
_db = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client

def get_db():
    global _db
    if _db is None:
        _db = get_client()[settings.db_name]
    return _db

# Collection references — used throughout the app
scrape_results_collection = None
batch_jobs_collection = None

def init_collections():
    global scrape_results_collection, batch_jobs_collection
    db = get_db()
    scrape_results_collection = db["scrape_results"]
    batch_jobs_collection = db["batch_jobs"]

# Initialize on import
init_collections()


async def ping() -> bool:
    """Test the MongoDB connection. Returns True on success, False on failure."""
    try:
        await get_client().admin.command("ping")
        logger.info("MongoDB connection successful")
        return True
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return False
