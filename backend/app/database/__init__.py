from app.database.database import engine, Base, AsyncSessionLocal as SessionLocal, get_db
from app.database.mongo_database import mongo_client, mongo_db, articles_collection, create_mongo_indexes