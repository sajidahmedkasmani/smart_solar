import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Instance folder path setup
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

# File path formatted cleanly for SQLite (converting Windows backslashes)
DB_PATH = os.path.join(INSTANCE_DIR, 'solarease.db').replace('\\', '/')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-fallback-key'

    APP_NAME = os.getenv('APP_NAME', 'SolarEase')
    APP_TITLE = os.getenv('APP_TITLE', 'Solar Ease System')
    APP_TAGLINE = os.getenv('APP_TAGLINE', 'Solar Solutions')
    COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'info@solarease.pk')
    COMPANY_PHONE = os.getenv('COMPANY_PHONE', '')

    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Google Auth Keys
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

    if not SECRET_KEY:
        print("\n" + "=" * 60)
        print(" [CONFIG WARNING / ERROR]")
        print(" You don't have secret access keys configured in your .env file!")
        print("=" * 60 + "\n")

    # Correct Absolute SQLite URI (Handles Windows & Linux paths seamlessly)
    SQLALCHEMY_DATABASE_URI = (
        DATABASE_URL if DATABASE_URL and DATABASE_URL.strip() 
        else f"sqlite:///{DB_PATH}"
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False