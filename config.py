import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables
load_dotenv()

# Get credentials from .env
DB_HOST = os.getenv("host")
DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_NAME = os.getenv("database")
DB_PORT = os.getenv("port", "3306")  # Default MySQL port

# ✅ Force TCP Connection (Fixes Unix Socket Error)
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?use_pure=True"

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, isolation_level="READ COMMITTED")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define the Base model
Base = declarative_base()

print(f"✅ Connected to MySQL at {DB_HOST}:{DB_PORT}")



# 🔹 Auth0 Configuration
AUTH0_DOMAIN = "dev-xrfy36ba5upgog72.us.auth0.com"  # Replace with your actual Auth0 domain
AUTH0_CLIENT_ID = "FgUCBvkEtKhZp7S5xQR1BN4WZbAKm510"
AUTH0_CLIENT_SECRET = "qfz3YruO9Y269PXjALNOBQMa8r25hK53i2jIneZOyAXC3f75tefL4eRNnjxLVXjC"
AUTH0_CALLBACK_URL = "http://127.0.0.1:5000/callback"
AUTH0_LOGOUT_REDIRECT = "http://127.0.0.1:5000/"
