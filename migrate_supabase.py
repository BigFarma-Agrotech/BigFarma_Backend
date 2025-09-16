from database import engine
import sqlalchemy as sa

def add_profile_setup_column():
    # Check if column already exists
    inspector = sa.inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'profile_setup' not in columns:
        with engine.begin() as connection:
            connection.execute(
                sa.text("ALTER TABLE users ADD COLUMN profile_setup BOOLEAN DEFAULT FALSE NOT NULL")
            )
        print("✅ Added profile_setup column to users table")
    else:
        print("✅ profile_setup column already exists")

if __name__ == "__main__":
    add_profile_setup_column()