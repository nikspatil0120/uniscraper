import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def clear():
    client = AsyncIOMotorClient('mongodb+srv://patilniks69_db_user:Ryussei0120@cluster0.0gpoypz.mongodb.net/')
    db = client['uniscraper']
    result = await db.scrape_results.delete_many({
        'url_requested': {'$regex': 'ed.ac.uk.*id=107|astate.edu|mcgill.ca|sydney.edu.au'}
    })
    print(f'Deleted {result.deleted_count} cached results')
    client.close()

asyncio.run(clear())
