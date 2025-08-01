#!/usr/bin/env python3
"""
Script to copy env.txt to .env file for easy setup.
"""
import shutil
import os

def setup_env():
    """Copy env.txt to .env file."""
    try:
        if os.path.exists('env.txt'):
            shutil.copy('env.txt', '.env')
            print("✅ Successfully copied env.txt to .env")
            print("📝 Please update the .env file with your actual database password")
            print("🔑 Replace [YOUR-PASSWORD] with your actual Supabase database password")
        else:
            print("❌ env.txt file not found")
            print("📝 Please create a .env file manually using env_template.txt as reference")
    except Exception as e:
        print(f"❌ Error copying file: {e}")

if __name__ == "__main__":
    setup_env() 