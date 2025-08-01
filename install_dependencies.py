#!/usr/bin/env python3
import subprocess
import sys

def install_dependencies():
    """Install required dependencies."""
    dependencies = [
        "fastapi==0.116.1",
        "uvicorn[standard]==0.35.0",
        "pydantic==2.11.7",
        "pydantic-settings==2.1.0",
        "email-validator==2.1.0",
        "python-jose[cryptography]==3.3.0",
        "passlib[bcrypt]==1.7.4",
        "python-multipart==0.0.6",
        "supabase==2.17.0",
        "postgrest==1.1.1",
        "psycopg2-binary==2.9.10",
        "httpx==0.28.1",
        "python-dotenv==1.1.1"
    ]
    
    print("Installing BigFarma Backend dependencies...")
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✓ {dep} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install {dep}: {e}")
            return False
    
    print("\nAll dependencies installed successfully!")
    print("You can now run: uvicorn app.main:app --reload")
    return True

if __name__ == "__main__":
    install_dependencies() 