from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    dob = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Subscription & Usage Fields
    subscription_tier = Column(String, default="FREE")
    tokens_used = Column(Integer, default=0)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    stripe_subscription_item_id = Column(String, nullable=True)

    sessions = relationship("Session", back_populates="user")
    queries = relationship("QueryHistory", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, unique=True, index=True)
    login_time = Column(DateTime, default=datetime.datetime.utcnow)
    logout_time = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    domain = Column(String)
    query = Column(Text)
    status = Column(String)  # "Started", "In Progress", "Completed", "Error"
    result_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="queries")
    artifacts = relationship("QueryArtifact", back_populates="query")

class QueryArtifact(Base):
    __tablename__ = "query_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("query_history.id"))
    agent_id = Column(String)
    agent_name = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    query = relationship("QueryHistory", back_populates="artifacts")

class OpenAlexCache(Base):
    __tablename__ = "openalex_cache"

    query_hash = Column(String, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    results = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class LiteratureChunk(Base):
    __tablename__ = "literature_chunks"

    id = Column(String, primary_key=True, index=True)
    paper_id = Column(String, index=True)
    title = Column(String)
    text = Column(Text)
    embedding = Column(Vector(384))
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

