"""
MongoDB Configuration and Connection
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class MongoDB:
    """MongoDB connection singleton"""
    
    client: Optional[AsyncIOMotorClient] = None
    database = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        mongo_url = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        cls.client = AsyncIOMotorClient(mongo_url)
        cls.database = cls.client[os.getenv("MONGODB_DB_NAME", "wandai")]
        print(f"✅ Connected to MongoDB: {os.getenv('MONGODB_DB_NAME', 'wandai')}")
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("❌ Closed MongoDB connection")
    
    @classmethod
    def get_collection(cls, name: str):
        """Get a MongoDB collection"""
        if cls.database is None:
            raise RuntimeError("Database not initialized. Call connect_db() first.")
        return cls.database[name]


def get_database():
    """Get the MongoDB database instance"""
    if MongoDB.database is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return MongoDB.database


# Collection names
COLLECTIONS = {
    "users": "users",
    "ratings": "ratings", 
    "document_scores": "document_scores",
    "query_analytics": "query_analytics",
    "document_analytics": "document_analytics",
    "user_analytics": "user_analytics",
    "sessions": "sessions"  # For JWT session management
}
