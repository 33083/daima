"""仓库管理 API"""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import (
    RepoCreateRequest, RepoResponse,
    FileInfoResponse, RepoFileListResponse,
)
from app.services.repo_service import RepoService
from app.services.task_manager import task_manager

router = APIRouter(prefix="/repos", tags=["仓库管理"])


@router.get("/browse/dirs")
def browse_dirs(path: str = ""):
    """浏览本地目录，返回子目录列表（用于前端文件夹选择器）"""
    import time as _time

    FOLDER_NAME_MAP = {
        "Desktop": "桌面", "Documents": "文档", "Downloads": "下载",
        "Pictures": "图片", "Music": "音乐", "Videos": "视频",
        "Users": "用户", "Program Files": "程序文件",
        "Program Files (x86)": "程序文件 (x86)", "Public": "公共",
        "AppData": "应用数据", "Local": "本地", "Roaming": "漫游",
    }

    if not path:
        drives = []
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                mtime = os.path.getmtime(drive) if os.path.exists(drive) else 0
                drives.append({
                    "name": f"本地磁盘 ({letter}:)",
                    "path": drive, "is_dir": True,
                    "modified": _time.strftime("%Y/%m/%d %H:%M", _time.localtime(mtime)) if mtime else "",
                    "type": "文件夹", "size": "",
                })

        # 常用目录快捷入口
        home = os.path.expanduser("~")
        quick = []
        quick_map = {"Desktop": "桌面", "Downloads": "下载", "Documents": "文档", "Pictures": "图片"}
        for en, zh in quick_map.items():
            p = os.path.join(home, en)
            if os.path.exists(p):
                quick.append({"name": zh, "path": p})

        return {"current": "", "dirs": drives, "quick": quick, "parent": None}

    path = os.path.normpath(path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="路径不存在")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="不是目录")

    dirs = []
    try:
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if not os.path.isdir(full_path):
                continue
            if entry.startswith('.') or entry in ('node_modules', '__pycache__', '.git', 'venv', '.venv'):
                continue
            st = os.stat(full_path)
            display_name = FOLDER_NAME_MAP.get(entry, entry)
            dirs.append({
                "name": display_name,
                "path": full_path,
                "is_dir": True,
                "modified": _time.strftime("%Y/%m/%d %H:%M", _time.localtime(st.st_mtime)),
                "type": "文件夹",
                "size": "",
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问")

    dirs.sort(key=lambda x: x["name"].lower())

    parent = os.path.dirname(path)
    if parent == path or not parent:
        parent = None

    # 常用目录快捷入口
    home = os.path.expanduser("~")
    quick = []
    quick_map = {"Desktop": "桌面", "Downloads": "下载", "Documents": "文档", "Pictures": "图片"}
    for en, zh in quick_map.items():
        p = os.path.join(home, en)
        if os.path.exists(p):
            quick.append({"name": zh, "path": p})

    return {"current": path, "dirs": dirs, "quick": quick, "parent": parent}


@router.get("", response_model=List[RepoResponse])
def list_repos(db: Session = Depends(get_db)):
    """获取仓库列表"""
    service = RepoService(db)
    return service.list_repos()


@router.get("/{repo_id}", response_model=RepoResponse)
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    """获取仓库详情"""
    service = RepoService(db)
    repo = service.get_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repo


@router.post("", response_model=RepoResponse)
def create_repo(req: RepoCreateRequest, db: Session = Depends(get_db)):
    """
    导入代码仓库（异步）
    - git 方式：后台克隆+索引
    - local 方式：后台索引本地目录
    返回仓库信息后，可以通过 /tasks/{task_id} 查询进度
    """
    service = RepoService(db)

    if req.source_type == "git" and req.url:
        repo, task_id = service.import_from_git_async(req.url, req.name)
        return repo
    elif req.source_type == "local" and req.local_path:
        repo, task_id = service.import_from_local_async(req.name, req.local_path)
        return repo
    else:
        raise HTTPException(status_code=400, detail="请提供有效的 Git 地址或本地路径")


@router.delete("/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db)):
    """删除仓库"""
    service = RepoService(db)
    if not service.delete_repo(repo_id):
        raise HTTPException(status_code=404, detail="仓库不存在")
    return {"message": "删除成功"}


@router.post("/{repo_id}/reindex", response_model=RepoResponse)
def reindex_repo(repo_id: int, db: Session = Depends(get_db)):
    """重新索引（异步）"""
    service = RepoService(db)
    result = service.reindex_async(repo_id)
    if not result:
        raise HTTPException(status_code=404, detail="仓库不存在")
    repo, task_id = result
    return repo


@router.get("/{repo_id}/tasks/{task_id}")
def get_task_progress(repo_id: int, task_id: str):
    """查询索引任务进度"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.repo_id != repo_id:
        raise HTTPException(status_code=400, detail="任务不属于该仓库")
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "current_file": task.current_file,
        "processed_files": task.processed_files,
        "total_files": task.total_files,
        "error_msg": task.error_msg,
    }


@router.get("/{repo_id}/files", response_model=RepoFileListResponse)
def list_files(repo_id: int, page: int = 1, page_size: int = 50,
               db: Session = Depends(get_db)):
    """获取仓库文件列表"""
    service = RepoService(db)
    files, total = service.list_files(repo_id, page, page_size)
    return {"files": files, "total": total}


@router.get("/{repo_id}/files/content")
def get_file_content(repo_id: int, path: str, db: Session = Depends(get_db)):
    """获取文件内容"""
    service = RepoService(db)
    content = service.get_file_content(repo_id, path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"content": content, "path": path}
