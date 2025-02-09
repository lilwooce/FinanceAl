from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .config import Config

Base = Config.Base
engine = Config.engine

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    auth0_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    picture = Column(String(300), nullable=True)
    monthly_income = Column(Float, default=0.0)

    chat_history = relationship("ChatHistory", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    recurring_expenses = relationship("RecurringExpense", back_populates="user")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")  
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(100), nullable=False)  # Example: "Rent", "Subscription"
    amount = Column(Float, nullable=False)
    frequency = Column(Enum("daily", "weekly", "monthly", "yearly", name="recurring_type"), nullable=False)
    next_due_date = Column(DateTime, nullable=False, default=datetime.now())  # When the next expense should be recorded

    user = relationship("User", back_populates="recurring_expenses")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum("income", "expense", name="transaction_type"), nullable=False)  # Income or Expense
    category = Column(String(100), nullable=False)  # Example: "Food", "Rent", "Salary"
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)  # ✅ Stores what user originally entered
    date = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(100), nullable=False)  # Example: "Food", "Entertainment"
    limit_amount = Column(Float, nullable=False)

    user = relationship("User", back_populates="budgets")
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender = Column(String(10), nullable=False)  # "user" or "bot"
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_history")
class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Assuming users table exists
    name = Column(String(255), nullable=False)  # Goal name
    target = Column(Float, nullable=False)  # Target amount
    progress = Column(Float, default=0)  # Amount saved so far
    completed = Column(Boolean, default=False)

    # Relationship to User (Optional, useful if you need user data)
    user = relationship("User", back_populates="goals")  

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="posts")  # Add this line
    comments = relationship('Comment', back_populates='post', cascade="all, delete-orphan")
    
class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    content = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="comments")
    post = relationship('Post', back_populates='comments')

# 🔹 Create all tables in the database
Base.metadata.create_all(engine)
