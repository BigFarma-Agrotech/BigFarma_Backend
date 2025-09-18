import sys
from database import Base, engine, SessionLocal
from features.auth import models
from features.users import models
from migrate_helper import check_database_status, migrate_database  # your helper file

if __name__ == "__main__":
    print("🔍 Checking database schema against models...")
    check_database_status()

    response = input("\nDo you want to run migrations? (y/N): ")
    if response.lower() in ["y", "yes"]:
        migrate_database()
    else:
        print("❌ Migration cancelled.")
        sys.exit(0)
