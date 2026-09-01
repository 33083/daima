"""请求/响应模型"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


# ===== 仓库相关 =====

class RepoCreateRequest(BaseModel):
    """导入仓库请求"""
    url: Optional[str] = Field(None, description="Git 仓库地址")
    name: str = Field(..., description="仓库名称")
    local_path: Optional[str] = Field(None, description="本地路径（本地导入时使用）")
    source_type: str = Field("git", description="来源类型：git / local")


class RepoResponse(BaseModel):
    id: int
    name: str
    url: Optional[str] = None
    source_type: str
    language: Optional[str] = None
    status: str
    file_count: int
    chunk_count: int
    error_msg: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FileInfoResponse(BaseModel):
    """文件信息"""
    id: int
    file_path: str
    file_name: str
    language: str
    file_size: int
    line_count: int
    function_count: int
    class_count: int

    class Config:
        from_attributes = True


class RepoFileListResponse(BaseModel):
    files: List[FileInfoResponse]
    total: int


# ===== 问答相关 =====

class ChatRequest(BaseModel):
    """问答请求"""
    repo_id: int = Field(..., description="仓库 ID")
    question: str = Field(..., description="问题")
    conversation_id: Optional[str] = Field(None, description="会话 ID（内存版，兼容旧版）")
    conv_id: Optional[int] = Field(None, description="数据库会话 ID（持久化版，推荐）")
    use_agent: bool = Field(True, description="是否启用 Agent 模式（工具调用）")
    max_tool_calls: Optional[int] = Field(8, description="最大工具调用次数")


class RetrievedCode(BaseModel):
    """检索到的代码片段"""
    file_path: str
    file_name: str
    language: str
    start_line: int
    end_line: int
    content: str
    score: float


class ChatStartEvent(BaseModel):
    """对话开始事件"""
    event: str = "start"
    conversation_id: str
    retrieved_count: int


class ChatDeltaEvent(BaseModel):
    """流式增量事件"""
    event: str = "delta"
    content: str


class ChatEndEvent(BaseModel):
    """对话结束事件"""
    event: str = "end"
    references: List[RetrievedCode]
