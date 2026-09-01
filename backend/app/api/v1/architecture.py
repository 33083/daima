"""项目架构概览 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.architecture_service import ArchitectureService

router = APIRouter(prefix="/architecture", tags=["项目架构"])


@router.get("/overview/{repo_id}")
def get_architecture_overview(repo_id: int, db: Session = Depends(get_db)):
    """
    获取项目架构概览
    返回：目录树、模块说明、技术栈、统计信息、入口文件
    """
    service = ArchitectureService(db)
    result = service.generate_overview(repo_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
