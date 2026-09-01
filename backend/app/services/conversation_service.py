"""会话管理服务"""
import json
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation import Conversation, Message


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    def list_conversations(self, repo_id: int, page: int = 1, page_size: int = 20) -> Tuple[List[Conversation], int]:
        """获取仓库的会话列表（按最后消息时间倒序）"""
        query = self.db.query(Conversation).filter(
            Conversation.repo_id == repo_id,
            Conversation.is_deleted == False,
        )
        total = query.count()
        conversations = query.order_by(
            desc(Conversation.last_message_at)
        ).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return conversations, total

    def get_conversation(self, conv_id: int) -> Optional[Conversation]:
        """获取会话详情"""
        conv = self.db.query(Conversation).filter(
            Conversation.id == conv_id,
            Conversation.is_deleted == False,
        ).first()
        return conv

    def create_conversation(self, repo_id: int, title: str = None, mode: str = "agent") -> Conversation:
        """创建新会话"""
        conv = Conversation(
            repo_id=repo_id,
            title=title or "新对话",
            mode=mode,
        )
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def update_title(self, conv_id: int, title: str) -> Optional[Conversation]:
        """更新会话标题"""
        conv = self.get_conversation(conv_id)
        if not conv:
            return None
        conv.title = title
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def delete_conversation(self, conv_id: int) -> bool:
        """软删除会话"""
        conv = self.get_conversation(conv_id)
        if not conv:
            return False
        conv.is_deleted = True
        self.db.commit()
        return True

    def list_messages(self, conv_id: int, page: int = 1, page_size: int = 50) -> Tuple[List[Message], int]:
        """获取会话消息列表（按时间正序，最新的在后面）"""
        query = self.db.query(Message).filter(Message.conversation_id == conv_id)
        total = query.count()
        messages = query.order_by(Message.id.asc()).offset(
            max(0, total - page * page_size)
        ).limit(page_size).all()
        return messages, total

    def add_message(self, conv_id: int, role: str, content: str, meta: dict = None) -> Message:
        """添加消息"""
        msg = Message(
            conversation_id=conv_id,
            role=role,
            content=content,
            meta=json.dumps(meta, ensure_ascii=False) if meta else None,
        )
        self.db.add(msg)

        # 更新会话统计
        conv = self.get_conversation(conv_id)
        if conv:
            conv.message_count += 1
            conv.last_message_at = func_now()
            # 第一句用户消息作为标题
            if role == "user" and conv.message_count <= 2:
                conv.title = content[:30] + ("..." if len(content) > 30 else "")

        self.db.commit()
        self.db.refresh(msg)
        return msg


def func_now():
    """获取当前时间（SQLAlchemy 方式）"""
    from sqlalchemy.sql import func
    return func.now()
