from sqlalchemy import Column, Integer, String
from config import Base, engine

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    auth0_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    picture = Column(String(300), nullable=True)

# 🔹 Create all tables in the database
Base.metadata.create_all(engine)
