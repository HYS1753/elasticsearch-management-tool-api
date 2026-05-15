import asyncio
import bcrypt
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from src.python.elasticsearch.config.settings.env_settings import settings

KST = timezone(timedelta(hours=9))

async def create_admin():
    uri = settings.MONGO_URI
    client = AsyncIOMotorClient(uri)
    db = client[settings.MONGO_DB_NAME]
    
    existing = await db.users.find_one({"user_id": "admin"})
    if existing:
        print("Admin already exists!")
        return

    # Use bcrypt directly
    hashed_pw = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")

    admin_user = {
        "user_id": "admin",
        "password": hashed_pw,
        "name": "Admin",
        "role": "ADMIN",
        "delete_yn": "N",
        "created_at": datetime.now(timezone.utc),
        "created_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now(timezone.utc),
        "updated_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    await db.users.insert_one(admin_user)
    print("Admin user created successfully! (id: admin, pw: admin)")

if __name__ == "__main__":
    asyncio.run(create_admin())
