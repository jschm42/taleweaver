import asyncio
from sqlalchemy import create_engine, inspect
from backend.core.config import settings

def inspect_db():
    engine = create_engine(settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://"))
    inspector = inspect(engine)
    
    tables = inspector.get_table_names()
    print(f"Tables: {tables}")
    
    if "game_sessions" in tables:
        columns = [c["name"] for c in inspector.get_columns("game_sessions")]
        print(f"Columns in game_sessions: {columns}")
    
    if "users" in tables:
        columns = [c["name"] for c in inspector.get_columns("users")]
        print(f"Columns in users: {columns}")

if __name__ == "__main__":
    inspect_db()
