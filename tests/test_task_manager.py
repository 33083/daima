"""
任务管理器测试
"""
import time
import pytest
from app.services.task_manager import TaskManager, TaskProgress


class TestTaskManager:
    """任务管理器测试"""

    @pytest.fixture
    def manager(self):
        return TaskManager()

    def test_create_task(self, manager):
        """创建任务"""
        task = manager.create_task("test-1", "repo_import", 1)
        assert task.task_id == "test-1"
        assert task.task_type == "repo_import"
        assert task.repo_id == 1
        assert task.status == "pending"
        assert task.progress == 0.0

    def test_get_task(self, manager):
        """获取任务"""
        manager.create_task("test-1", "repo_import", 1)
        task = manager.get_task("test-1")
        assert task is not None
        assert task.task_id == "test-1"

    def test_get_nonexistent_task(self, manager):
        """获取不存在的任务"""
        task = manager.get_task("nonexistent")
        assert task is None

    def test_update_progress(self, manager):
        """更新进度"""
        manager.create_task("test-1", "repo_import", 1)
        manager.update_progress("test-1", status="running", progress=50, message="处理中")

        task = manager.get_task("test-1")
        assert task.status == "running"
        assert task.progress == 50
        assert task.message == "处理中"

    def test_run_async(self, manager):
        """后台运行任务"""
        def slow_task(task_id, x, y):
            manager.update_progress(task_id, status="running", progress=50)
            time.sleep(0.1)
            return x + y

        manager.create_task("async-1", "test", 1)
        manager.run_async("async-1", slow_task, 3, 4)

        # 立刻检查应该是 running
        time.sleep(0.02)
        task = manager.get_task("async-1")
        assert task.status in ("running", "done")

        # 等待完成
        time.sleep(0.2)
        task = manager.get_task("async-1")
        assert task.status == "done"
        assert task.progress == 100

    def test_run_async_error(self, manager):
        """后台任务出错"""
        def failing_task(task_id):
            raise ValueError("测试错误")

        manager.create_task("err-1", "test", 1)
        manager.run_async("err-1", failing_task)

        time.sleep(0.1)
        task = manager.get_task("err-1")
        assert task.status == "error"
        assert "测试错误" in task.error_msg

    def test_cleanup_old_tasks(self, manager):
        """清理旧任务"""
        manager.create_task("old-1", "test", 1)
        manager.update_progress("old-1", status="done", finished_at=time.time() - 7200)  # 2 小时前

        manager.create_task("new-1", "test", 1)
        manager.update_progress("new-1", status="done", finished_at=time.time() - 60)  # 1 分钟前

        manager.cleanup_old_tasks(max_age=3600)  # 清理 1 小时前的

        assert manager.get_task("old-1") is None
        assert manager.get_task("new-1") is not None
