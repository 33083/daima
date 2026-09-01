"""
异步任务管理
- 后台线程执行索引任务
- 内存记录任务进度
- 提供查询接口
"""
import threading
import time
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class TaskProgress:
    """任务进度"""
    task_id: str
    task_type: str           # repo_index / repo_clone
    repo_id: int
    status: str = "pending"  # pending / running / done / error
    progress: float = 0.0    # 0-100
    message: str = ""
    current_file: str = ""
    processed_files: int = 0
    total_files: int = 0
    error_msg: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


class TaskManager:
    """任务管理器（单例）"""

    def __init__(self):
        self._tasks: Dict[str, TaskProgress] = {}
        self._lock = threading.Lock()

    def create_task(self, task_id: str, task_type: str, repo_id: int) -> TaskProgress:
        """创建任务"""
        task = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            repo_id=repo_id,
        )
        with self._lock:
            self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        with self._lock:
            return self._tasks.get(task_id)

    def update_progress(self, task_id: str, **kwargs):
        """更新任务进度"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)

    def run_async(self, task_id: str, target_func, *args, **kwargs):
        """
        后台运行任务
        target_func 的第一个参数会被注入 task_id，用于更新进度
        """
        def wrapper():
            try:
                self.update_progress(task_id, status="running")
                target_func(task_id, *args, **kwargs)
                self.update_progress(task_id, status="done", progress=100, finished_at=time.time())
            except Exception as e:
                self.update_progress(
                    task_id,
                    status="error",
                    error_msg=str(e)[:500],
                    finished_at=time.time(),
                )

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()

    def cleanup_old_tasks(self, max_age: int = 3600):
        """清理超过指定时间的已完成任务（秒）"""
        now = time.time()
        with self._lock:
            to_delete = [
                tid for tid, task in self._tasks.items()
                if task.finished_at and now - task.finished_at > max_age
            ]
            for tid in to_delete:
                del self._tasks[tid]


# 全局单例
task_manager = TaskManager()
