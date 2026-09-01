"""仓库服务：导入、索引、管理"""
import os
import shutil
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from git import Repo as GitRepo, InvalidGitRepositoryError

from app.config import settings
from app.models.repo import CodeRepo, CodeFile
from app.services.code_parser import (
    collect_code_files, chunk_code_file, get_file_info,
    detect_repo_language, detect_language,
)
from app.core import vectorstore
from app.services.bm25_service import bm25_retriever
from app.services.task_manager import task_manager


class RepoService:
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(settings.repo_storage_dir, exist_ok=True)

    def list_repos(self) -> List[CodeRepo]:
        return self.db.query(CodeRepo).order_by(CodeRepo.created_at.desc()).all()

    def get_repo(self, repo_id: int) -> Optional[CodeRepo]:
        return self.db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()

    def import_from_git(self, url: str, name: str) -> CodeRepo:
        """从 Git 仓库导入"""
        # 创建记录
        repo = CodeRepo(
            name=name,
            url=url,
            source_type="git",
            status="pending",
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)

        # 本地存储路径
        local_path = os.path.join(settings.repo_storage_dir, f"repo_{repo.id}")

        try:
            repo.status = "indexing"
            repo.local_path = local_path
            self.db.commit()

            # 克隆仓库
            os.makedirs(local_path, exist_ok=True)
            GitRepo.clone_from(url, local_path, depth=1)

            # 索引代码
            self._index_repo(repo)

            repo.status = "ready"
        except Exception as e:
            repo.status = "error"
            repo.error_msg = str(e)[:500]
        finally:
            self.db.commit()

        return repo

    # ==================== 异步索引 ====================

    def import_from_git_async(self, url: str, name: str) -> tuple:
        """
        异步从 Git 导入仓库
        返回 (repo, task_id)
        """
        repo = CodeRepo(
            name=name,
            url=url,
            source_type="git",
            status="pending",
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)

        local_path = os.path.join(settings.repo_storage_dir, f"repo_{repo.id}")
        repo.local_path = local_path
        repo.status = "indexing"
        self.db.commit()

        task_id = f"repo_{repo.id}_import"
        task_manager.create_task(task_id, "repo_import", repo.id)

        # 后台执行
        task_manager.run_async(
            task_id,
            self._import_git_worker,
            repo.id,
            url,
            local_path,
        )

        return repo, task_id

    def import_from_local_async(self, name: str, local_path: str) -> tuple:
        """
        异步导入本地目录
        返回 (repo, task_id)
        """
        if not os.path.exists(local_path):
            raise ValueError(f"路径不存在: {local_path}")

        repo = CodeRepo(
            name=name,
            source_type="local",
            local_path=local_path,
            status="indexing",
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)

        task_id = f"repo_{repo.id}_import"
        task_manager.create_task(task_id, "repo_import", repo.id)

        task_manager.run_async(
            task_id,
            self._index_repo_worker,
            repo.id,
        )

        return repo, task_id

    def reindex_async(self, repo_id: int) -> Optional[tuple]:
        """
        异步重新索引
        返回 (repo, task_id)
        """
        repo = self.get_repo(repo_id)
        if not repo:
            return None

        repo.status = "indexing"
        repo.error_msg = None
        self.db.commit()

        # 删除旧文件记录
        self.db.query(CodeFile).filter(CodeFile.repo_id == repo_id).delete()
        self.db.commit()

        task_id = f"repo_{repo.id}_reindex"
        task_manager.create_task(task_id, "repo_reindex", repo.id)

        task_manager.run_async(
            task_id,
            self._index_repo_worker,
            repo.id,
        )

        return repo, task_id

    def _import_git_worker(self, task_id: str, repo_id: int, url: str, local_path: str):
        """Git 克隆 + 索引（后台线程执行，用新的 db session）"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            task_manager.update_progress(task_id, message="正在克隆仓库...", progress=5)

            os.makedirs(local_path, exist_ok=True)

            # 国内 GitHub clone 超时，用代理加速
            clone_url = url
            if url.startswith("https://github.com") and settings.github_proxy:
                clone_url = settings.github_proxy + url
                task_manager.update_progress(task_id, message="使用代理加速克隆...", progress=5)

            GitRepo.clone_from(clone_url, local_path, depth=1)

            task_manager.update_progress(task_id, message="克隆完成，开始索引...", progress=10)

            # 索引代码（带进度）
            self._index_repo_with_progress(task_id, db, repo_id)

            # 更新仓库状态
            repo = db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()
            if repo:
                repo.status = "ready"
                self._generate_description(db, repo)
                db.commit()
        except Exception as e:
            repo = db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()
            if repo:
                repo.status = "error"
                repo.error_msg = str(e)[:500]
                db.commit()
            raise
        finally:
            db.close()

    def _index_repo_worker(self, task_id: str, repo_id: int):
        """索引代码（后台线程执行）"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            task_manager.update_progress(task_id, message="开始索引...", progress=5)
            self._index_repo_with_progress(task_id, db, repo_id)

            repo = db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()
            if repo:
                repo.status = "ready"
                self._generate_description(db, repo)
                db.commit()
        except Exception as e:
            repo = db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()
            if repo:
                repo.status = "error"
                repo.error_msg = str(e)[:500]
                db.commit()
            raise
        finally:
            db.close()

    def _index_repo_with_progress(self, task_id: str, db, repo_id: int):
        """带进度的索引（用独立 db session）"""
        repo = db.query(CodeRepo).filter(CodeRepo.id == repo_id).first()
        if not repo:
            raise ValueError("仓库不存在")

        # 收集代码文件
        code_files = collect_code_files(repo.local_path)
        repo.file_count = len(code_files)
        repo.language = detect_repo_language(code_files)
        db.commit()

        task_manager.update_progress(
            task_id,
            message=f"发现 {len(code_files)} 个代码文件，正在解析...",
            total_files=len(code_files),
            progress=10,
        )

        # 删除旧索引
        vectorstore.delete_collection(repo.id)
        bm25_retriever.delete_index(repo.id)

        total_chunks = 0
        all_chunks = []

        for idx, file_path in enumerate(code_files):
            rel_path = os.path.relpath(file_path, repo.local_path)
            task_manager.update_progress(
                task_id,
                current_file=rel_path,
                processed_files=idx + 1,
                progress=10 + int(85 * (idx + 1) / max(len(code_files), 1)),
            )

            # 保存文件信息
            info = get_file_info(file_path, repo.local_path)
            db_file = CodeFile(
                repo_id=repo.id,
                file_path=info.file_path,
                file_name=info.file_name,
                language=info.language,
                file_size=info.file_size,
                line_count=info.line_count,
                function_count=info.function_count,
                class_count=info.class_count,
            )
            db.add(db_file)

            # 代码切片并入库
            chunks = chunk_code_file(
                file_path,
                repo.local_path,
                max_chunk_size=settings.rag_chunk_size,
                overlap=settings.rag_chunk_overlap,
            )
            if chunks:
                added = vectorstore.add_code_chunks(repo.id, chunks)
                total_chunks += added
                for c in chunks:
                    all_chunks.append({
                        "content": c.content,
                        "file_path": c.file_path,
                        "file_name": c.file_name,
                        "language": c.language,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "chunk_type": c.chunk_type,
                        "symbol_name": c.symbol_name,
                    })

            # 每 50 个文件提交一次 db
            if (idx + 1) % 50 == 0:
                db.commit()

        db.commit()

        # 建立 BM25 索引
        task_manager.update_progress(task_id, message="建立 BM25 索引...", progress=95)
        if all_chunks:
            bm25_retriever.index(repo.id, all_chunks)

        repo.chunk_count = total_chunks
        db.commit()

        task_manager.update_progress(
            task_id,
            message=f"索引完成：{len(code_files)} 个文件，{total_chunks} 个切片",
            progress=100,
        )

    def import_from_local(self, name: str, local_path: str) -> CodeRepo:
        """从本地目录导入"""
        if not os.path.exists(local_path):
            raise ValueError(f"路径不存在: {local_path}")

        repo = CodeRepo(
            name=name,
            source_type="local",
            local_path=local_path,
            status="indexing",
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)

        try:
            self._index_repo(repo)
            repo.status = "ready"
            self._generate_description(self.db, repo)
        except Exception as e:
            repo.status = "error"
            repo.error_msg = str(e)[:500]
        finally:
            self.db.commit()

        return repo

    def _index_repo(self, repo: CodeRepo):
        """索引仓库代码"""
        # 收集代码文件
        code_files = collect_code_files(repo.local_path)
        repo.file_count = len(code_files)
        repo.language = detect_repo_language(code_files)

        # 删除旧索引
        vectorstore.delete_collection(repo.id)
        bm25_retriever.delete_index(repo.id)

        total_chunks = 0
        all_chunks = []

        for file_path in code_files:
            # 保存文件信息
            info = get_file_info(file_path, repo.local_path)
            db_file = CodeFile(
                repo_id=repo.id,
                file_path=info.file_path,
                file_name=info.file_name,
                language=info.language,
                file_size=info.file_size,
                line_count=info.line_count,
                function_count=info.function_count,
                class_count=info.class_count,
            )
            self.db.add(db_file)

            # 代码切片并入库
            chunks = chunk_code_file(
                file_path,
                repo.local_path,
                max_chunk_size=settings.rag_chunk_size,
                overlap=settings.rag_chunk_overlap,
            )
            if chunks:
                added = vectorstore.add_code_chunks(repo.id, chunks)
                total_chunks += added
                # 转为 dict 格式供 BM25 使用
                for c in chunks:
                    all_chunks.append({
                        "content": c.content,
                        "file_path": c.file_path,
                        "file_name": c.file_name,
                        "language": c.language,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "chunk_type": c.chunk_type,
                        "symbol_name": c.symbol_name,
                    })

        # 建立 BM25 索引
        if all_chunks:
            bm25_retriever.index(repo.id, all_chunks)

        repo.chunk_count = total_chunks
        self.db.commit()

    def list_files(self, repo_id: int, page: int = 1, page_size: int = 50) -> Tuple[List[CodeFile], int]:
        """获取仓库文件列表"""
        query = self.db.query(CodeFile).filter(CodeFile.repo_id == repo_id)
        total = query.count()
        files = query.order_by(CodeFile.file_path).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return files, total

    def get_file_content(self, repo_id: int, file_path: str) -> Optional[str]:
        """获取文件内容"""
        repo = self.get_repo(repo_id)
        if not repo:
            return None
        full_path = os.path.join(repo.local_path, file_path)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return None

    def delete_repo(self, repo_id: int) -> bool:
        """删除仓库（包括本地文件和向量）"""
        repo = self.get_repo(repo_id)
        if not repo:
            return False

        # 删除向量
        vectorstore.delete_collection(repo_id)

        # 删除数据库记录
        self.db.query(CodeFile).filter(CodeFile.repo_id == repo_id).delete()
        self.db.delete(repo)
        self.db.commit()

        # 删除本地文件（git clone 的才删，本地导入的不删原文件）
        if repo.source_type == "git" and repo.local_path and os.path.exists(repo.local_path):
            try:
                shutil.rmtree(repo.local_path)
            except Exception:
                pass

        return True

    def reindex(self, repo_id: int) -> Optional[CodeRepo]:
        """重新索引"""
        repo = self.get_repo(repo_id)
        if not repo:
            return None

        try:
            repo.status = "indexing"
            repo.error_msg = None
            self.db.commit()

            # 删除旧文件记录
            self.db.query(CodeFile).filter(CodeFile.repo_id == repo_id).delete()
            self.db.commit()

            self._index_repo(repo)
            repo.status = "ready"
            self._generate_description(self.db, repo)
        except Exception as e:
            repo.status = "error"
            repo.error_msg = str(e)[:500]
        finally:
            self.db.commit()

        return repo

    def _generate_description(self, db, repo: CodeRepo):
        """索引完成后自动生成项目简介"""
        try:
            from app.services.architecture_service import ArchitectureService
            arch = ArchitectureService(db)
            overview = arch.generate_overview(repo.id)
            if "error" in overview:
                return

            ts = overview.get("tech_stack", {})
            languages = ts.get("languages", [])
            frameworks = ts.get("frameworks", [])
            databases = ts.get("databases", [])

            stats = overview.get("stats", {})
            modules = overview.get("modules", [])
            entry_points = overview.get("entry_points", [])

            parts = []
            if languages:
                parts.append(f"{'/'.join(languages)} 项目")
            if frameworks:
                parts.append(f"使用 {'、'.join(frameworks)} 框架")
            if databases:
                parts.append(f"数据库: {'、'.join(databases)}")

            total_files = stats.get("total_files", 0)
            total_lines = stats.get("total_lines", 0)
            total_funcs = stats.get("total_functions", 0)
            total_classes = stats.get("total_classes", 0)
            parts.append(f"共 {total_files} 个文件、{total_lines:,} 行代码、{total_funcs} 个函数、{total_classes} 个类")

            if modules:
                top_modules = [m["name"] for m in modules[:5]]
                parts.append(f"主要模块: {', '.join(top_modules)}")

            if entry_points:
                entry_str = "; ".join([f"{e['path']} ({e['description']})" for e in entry_points[:3]])
                parts.append(f"入口: {entry_str}")

            repo.description = " | ".join(parts)
        except Exception:
            pass
