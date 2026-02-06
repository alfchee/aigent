from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.db import Base
import datetime

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat())
    updated_at = Column(String, default=lambda: datetime.datetime.now().isoformat())
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String) # user, model
    content = Column(JSON) # Store parts as JSON
    timestamp = Column(String, default=lambda: datetime.datetime.now().isoformat())

    session = relationship("ChatSession", back_populates="messages")
