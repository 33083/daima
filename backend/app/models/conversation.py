"""会话 & 消息模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class Conversation(Base):
    """对话会话"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, index=True)
    title = Column(String(255), default="新对话")                      # 会话标题（自动取第一句）
    mode = Column(String(20), default="agent")                        # agent / quick
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_deleted = Column(Boolean, default=False)


class Message(Base):
    """对话消息"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, index=True)
    role = Column(String(20))            # user / assistant
    content = Column(Text)               # 消息内容（Markdown 纯文本）
    # 额外信息 JSON
    meta = Column(Text, nullable=True)   # JSON: { agent_actions, references, tokens 等 }
    created_at = Column(DateTime, server_default=func.now())
