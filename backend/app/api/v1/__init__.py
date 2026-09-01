"""API v1 路由"""
from fastapi import APIRouter

from app.api.v1.repos import router as repos_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conv_router
from app.api.v1.architecture import router as arch_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(repos_router)
api_router.include_router(chat_router)
api_router.include_router(conv_router)
api_router.include_router(arch_router)
