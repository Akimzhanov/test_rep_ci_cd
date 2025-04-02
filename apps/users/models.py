import email
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
from datetime import datetime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class ChatType(enum.Enum):
    PRIVATE = "private"
    GROUP = "group"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token = Column(Text, nullable=False, unique=True)
    user_agent = Column(String(255))
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("Users", back_populates="sessions")


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))

    sessions = relationship("Session", back_populates="user", cascade="all, delete")
    chats = relationship("Chats", secondary="chat_user", back_populates="participants")
    messages = relationship("Messages", back_populates="sender")


class Chats(Base):
    __tablename__ = 'chats'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    chats_type = Column(SAEnum(ChatType, name="chattype"), nullable=False, index=True)

    messages = relationship("Messages", back_populates="chat", cascade="all, delete-orphan")
    participants = relationship("Users", secondary="chat_user", back_populates="chats")

class ChatUser(Base):
    __tablename__ = "chat_user"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))


class Messages(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    chat = relationship("Chats", back_populates="messages")
    sender = relationship("Users", back_populates="messages")


class Groups(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    
