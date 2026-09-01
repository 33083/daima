"""ORM 模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class CodeRepo(Base):
    """代码仓库"""
    __tablename__ = "code_repos"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)                    # 仓库名称
    url = Column(String(500), nullable=True)                   # Git 地址（如果是 clone 来的）
    source_type = Column(String(20), default="git")            # git / local
    local_path = Column(String(500))                           # 本地路径
    language = Column(String(50), nullable=True)               # 主要语言
    status = Column(String(20), default="pending")             # pending / indexing / ready / error
    file_count = Column(Integer, default=0)                    # 索引的文件数
    chunk_count = Column(Integer, default=0)                   # 切片数量
    error_msg = Column(Text, nullable=True)                    # 错误信息
    description = Column(Text, nullable=True)                   # 项目简介（自动生成）
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class CodeFile(Base):
    """代码文件信息"""
    __tablename__ = "code_files"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, index=True)
    file_path = Column(String(500))                            # 相对路径
    file_name = Column(String(255))
    language = Column(String(50))                              # 编程语言
    file_size = Column(Integer, default=0)                     # 文件大小（字节）
    line_count = Column(Integer, default=0)                    # 行数
    function_count = Column(Integer, default=0)                # 函数数量
    class_count = Column(Integer, default=0)                   # 类数量
    created_at = Column(DateTime, server_default=func.now())
