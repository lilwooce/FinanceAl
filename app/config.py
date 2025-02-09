import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ✅ Load environment variables safely
load_dotenv()

# ✅ Fetch database credentials from .env
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")  # Default MySQL port

# ✅ Validate that all required variables are set
if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise ValueError("❌ Missing database environment variables. Check your .env file.")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")  # ✅ Fallback if not set
    # ✅ Securely format MySQL connection URL
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # ✅ Avoid unnecessary warnings

    # Create engine
    engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True, isolation_level="READ COMMITTED")
    print(engine)

    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # ✅ Define the Base model
    Base = declarative_base()

    # 🔹 Auth0 Configuration (🚨 Secret keys should be in `.env`)
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "your-auth0-domain")
    AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "your-client-id")
    AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "your-client-secret")
    AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "http://127.0.0.1:5000/callback")
    AUTH0_LOGOUT_REDIRECT = os.getenv("AUTH0_LOGOUT_REDIRECT", "http://127.0.0.1:5000/")

    # 🔹 OpenAI API Key (🚨 Should NOT be hardcoded)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ✅ Print database connection confirmation
    print(f"✅ Connected to MySQL at {DB_HOST}:{DB_PORT}")
