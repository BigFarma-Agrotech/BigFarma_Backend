from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable
from database import engine, SessionLocal, Base

def get_existing_columns(table_name):
    inspector = inspect(engine)
    return [col['name'] for col in inspector.get_columns(table_name)]

def get_model_columns(table_name):
    table = Base.metadata.tables[table_name]
    return [column.name for column in table.columns]

def check_database_status():
    """Check current status of DB vs models"""
    db = SessionLocal()
    inspector = inspect(engine)

    print(f"\n🔍 Checking database status...")
    db_tables = inspector.get_table_names()
    model_tables = Base.metadata.tables.keys()

    for table_name in model_tables:
        if table_name not in db_tables:
            print(f"❌ Missing table: {table_name}")
        else:
            db_columns = [col['name'] for col in inspector.get_columns(table_name)]
            model_columns = [col.name for col in Base.metadata.tables[table_name].columns]

            missing_columns = set(model_columns) - set(db_columns)
            if missing_columns:
                print(f"⚠️  Table '{table_name}' missing columns: {list(missing_columns)}")
            else:
                print(f"✅ Table '{table_name}' is complete")

    db.close()

def migrate_database():
    """Run migrations (create tables + add missing columns)"""
    db = SessionLocal()
    inspector = inspect(engine)

    print("\n🔄 Running migrations...")

    # 1. Ensure all tables exist
    Base.metadata.create_all(engine)

    # 2. Sync missing columns
    for table_name, table in Base.metadata.tables.items():
        existing_columns = get_existing_columns(table_name)
        model_columns = get_model_columns(table_name)

        missing_columns = set(model_columns) - set(existing_columns)
        if missing_columns:
            print(f"\n📊 Table '{table_name}' is missing columns: {list(missing_columns)}")
            for col_name in missing_columns:
                col = table.columns[col_name]
                col_type = col.type.compile(engine.dialect)
                nullable = "NULL" if col.nullable else "NOT NULL"

                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable};"
                try:
                    db.execute(text(sql))
                    db.commit()
                    print(f"   ✅ Added column {col_name} ({col_type})")
                except Exception as e:
                    print(f"   ❌ Failed to add {col_name}: {e}")
                    db.rollback()
        else:
            print(f"✅ Table '{table_name}' is up to date")

    # 3. Extra manual migrations
    extra_migrations = [
        {
            "desc": "Add profile_setup to users table",
            "sql": "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_setup BOOLEAN DEFAULT FALSE;"
        },
        {
            "desc": "Add full_name to farmer_profiles table",
            "sql": "ALTER TABLE farmer_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR;"
        },
        {
            "desc": "Extend orderstatus enum",
            "sql": """
            DO $$ 
            BEGIN
                BEGIN
                    ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'awaiting_confirmation';
                EXCEPTION WHEN duplicate_object THEN null; END;

                BEGIN
                    ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'delivery_issue';
                EXCEPTION WHEN duplicate_object THEN null; END;
            END $$;
            """
        }
    ]

    print("\n🔧 Running extra migrations...")
    for m in extra_migrations:
        try:
            db.execute(text(m["sql"]))
            db.commit()
            print(f"   ✅ {m['desc']}")
        except Exception as e:
            db.rollback()
            print(f"   ⚠️ {m['desc']} failed: {e}")

    db.close()
    print("\n✅ Migration finished!")
