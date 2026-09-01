"""会话管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["会话管理"])


# ===== Pydantic Models =====

class ConversationResponse(BaseModel):
    id: int
    repo_id: int
    title: str
    mode: str
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    meta: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    items: List[ConversationResponse]
    total: int


class MessageListResponse(BaseModel):
    items: List[MessageResponse]
    total: int


class CreateConversationRequest(BaseModel):
    repo_id: int = Field(..., description="仓库 ID")
    title: Optional[str] = Field(None, description="会话标题")
    mode: Optional[str] = Field("agent", description="模式: agent / quick")


class UpdateTitleRequest(BaseModel):
    title: str


# ===== Routes =====

@router.get("", response_model=ConversationListResponse)
def list_conversations(
    repo_id: int = Query(..., description="仓库 ID"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """获取仓库的会话列表"""
    service = ConversationService(db)
    items, total = service.list_conversations(repo_id, page, page_size)
    return {"items": items, "total": total}


@router.post("", response_model=ConversationResponse)
def create_conversation(req: CreateConversationRequest, db: Session = Depends(get_db)):
    """创建新会话"""
    service = ConversationService(db)
    conv = service.create_conversation(req.repo_id, req.title, req.mode)
    return conv


@router.get("/{conv_id}", response_model=ConversationResponse)
def get_conversation(conv_id: int, db: Session = Depends(get_db)):
    """获取会话详情"""
    service = ConversationService(db)
    conv = service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.patch("/{conv_id}/title", response_model=ConversationResponse)
def update_title(conv_id: int, req: UpdateTitleRequest, db: Session = Depends(get_db)):
    """更新会话标题"""
    service = ConversationService(db)
    conv = service.update_title(conv_id, req.title)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.delete("/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    """删除会话"""
    service = ConversationService(db)
    if not service.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "删除成功"}


@router.get("/{conv_id}/messages", response_model=MessageListResponse)
def list_messages(
    conv_id: int,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """获取会话消息列表"""
    service = ConversationService(db)
    # 检查会话是否存在
    conv = service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    items, total = service.list_messages(conv_id, page, page_size)
    # 解析 meta JSON
    result = []
    for msg in items:
        item_dict = {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "meta": None,
            "created_at": msg.created_at,
        }
        if msg.meta:
            try:
                import json
                item_dict["meta"] = json.loads(msg.meta)
            except Exception:
                pass
        result.append(item_dict)

    return {"items": result, "total": total}
