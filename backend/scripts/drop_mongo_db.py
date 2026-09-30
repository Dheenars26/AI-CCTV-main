import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.settings import settings

async def drop_db():
    print(f"Connecting to MongoDB at: {settings.MONGODB_URL}")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    
    # Try to connect and check server status
    try:
        await client.admin.command('ping')
        print("Connected successfully.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print(f"Dropping database: {settings.MONGODB_DB_NAME}")
    await client.drop_database(settings.MONGODB_DB_NAME)
    print("Database dropped successfully.")

if __name__ == "__main__":
    asyncio.run(drop_db())
