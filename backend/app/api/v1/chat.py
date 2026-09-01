"""对话问答 API"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["对话问答"])


@router.post("/stream")
async def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """
    流式问答接口（SSE）
    事件类型：
    - start: 对话开始
    - tool_call: Agent 调用工具中
    - tool_result: 工具返回结果
    - delta: 增量文本
    - end: 对话结束，携带 agent 动作记录
    - error: 错误信息
    """
    service = ChatService(db)

    # 始终使用数据库持久化版本
    gen = service.chat_stream_with_conv(
        repo_id=req.repo_id,
        question=req.question,
        conv_id=req.conv_id,
        use_agent=req.use_agent,
        max_tool_calls=req.max_tool_calls or 8,
    )

    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
