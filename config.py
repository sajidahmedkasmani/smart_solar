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

    APP_NAME = os.getenv('APP_NAME', 'SmartSolar')
    APP_TITLE = os.getenv('APP_TITLE', 'Smart Solar System')
    APP_TAGLINE = os.getenv('APP_TAGLINE', 'Solar Solutions')
    COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'info@smartsolar.pk')
    COMPANY_PHONE = os.getenv('COMPANY_PHONE', '')

    DATABASE_URL = os.getenv('DATABASE_URL')

    # 
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    
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