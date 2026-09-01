"""
Agent 工具测试
"""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from app.services.agent_tools import CodeAgentTools


@pytest.fixture
def mock_repo():
    """创建模拟代码仓库"""
    repo_dir = tempfile.mkdtemp()

    # 创建测试文件
    files = {
        "app/main.py": '''"""主入口"""
from fastapi import FastAPI
from app.routes import router

app = FastAPI()
app.include_router(router)

@app.get("/")
def root():
    return {"message": "hello"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
''',
        "app/routes.py": '''"""路由"""
from fastapi import APIRouter
from app.services.user import get_user, create_user

router = APIRouter()

@router.get("/users/{user_id}")
def get_user_route(user_id: int):
    return get_user(user_id)

@router.post("/users")
def create_user_route(data: dict):
    return create_user(data)
''',
        "app/services/user.py": '''"""用户服务"""
from app.models import User

def get_user(user_id: int):
    """根据 ID 获取用户"""
    return User.query.get(user_id)

def create_user(data: dict):
    """创建用户"""
    user = User(**data)
    user.save()
    return user

def delete_user(user_id: int):
    """删除用户"""
    user = get_user(user_id)
    if user:
        user.delete()
''',
        "app/models/__init__.py": '''from app.models.user import User
''',
        "app/models/user.py": '''"""用户模型"""
from sqlalchemy import Column, Integer, String
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(200))
    password_hash = Column(String(200))

    def save(self):
        pass

    def delete(self):
        pass
''',
        "README.md": "# Test Repo\n\n这是一个测试仓库。",
    }

    for rel_path, content in files.items():
        full_path = os.path.join(repo_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    yield repo_dir

    import shutil
    shutil.rmtree(repo_dir)


class TestAgentTools:
    """Agent 工具测试"""

    @pytest.fixture
    def tools(self, mock_repo):
        """创建工具实例（mock db 和 repo_service）"""
        with patch("app.services.agent_tools.RepoService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            # mock repo
            mock_repo_obj = MagicMock()
            mock_repo_obj.id = 1
            mock_repo_obj.local_path = mock_repo
            mock_repo_obj.language = "python"
            mock_svc.get_repo.return_value = mock_repo_obj

            # mock get_file_content
            def mock_get_file_content(repo_id, file_path):
                full_path = os.path.join(mock_repo, file_path)
                if os.path.exists(full_path):
                    with open(full_path, "r") as f:
                        return f.read()
                return None
            mock_svc.get_file_content = mock_get_file_content

            mock_db = MagicMock()
            tools = CodeAgentTools(mock_db, 1)
            tools.repo = mock_repo_obj
            return tools

    def test_list_dir_root(self, tools):
        """列出根目录"""
        result = tools.list_dir("")
        assert "app/" in result
        assert "README.md" in result

    def test_list_dir_app(self, tools):
        """列出 app 目录"""
        result = tools.list_dir("app")
        assert "main.py" in result
        assert "routes.py" in result
        assert "services/" in result
        assert "models/" in result

    def test_view_file(self, tools):
        """查看文件内容"""
        result = tools.view_file("app/main.py")
        assert "FastAPI" in result
        assert "def root():" in result
        assert "app/main.py" in result

    def test_view_file_with_line_range(self, tools):
        """指定行号范围查看"""
        result = tools.view_file("app/main.py", start_line=1, end_line=5)
        lines = result.split("\n")
        # 加上 header 和分隔线，应该不会太多行
        assert len(lines) < 20

    def test_view_file_not_found(self, tools):
        """查看不存在的文件"""
        result = tools.view_file("nonexistent.py")
        assert "不存在" in result

    def test_find_symbol_function(self, tools):
        """查找函数定义"""
        result = tools.find_symbol("get_user")
        assert "找到" in result
        assert "user.py" in result

    def test_find_symbol_class(self, tools):
        """查找类定义"""
        result = tools.find_symbol("User")
        assert "找到" in result
        assert "user.py" in result

    def test_find_symbol_not_found(self, tools):
        """查找不存在的符号"""
        result = tools.find_symbol("NonExistentFunction")
        assert "未找到" in result

    def test_search_text(self, tools):
        """全文关键词搜索"""
        result = tools.search_text("FastAPI")
        assert "找到" in result
        assert "main.py" in result

    def test_search_text_not_found(self, tools):
        """搜索不存在的关键词"""
        result = tools.search_text("xyznonexistent")
        assert "未找到" in result

    def test_get_tools_schema(self, tools):
        """获取工具定义 schema"""
        schema = tools.get_tools_schema()
        assert len(schema) == 5  # 5 个工具

        tool_names = [s["function"]["name"] for s in schema]
        assert "search_code" in tool_names
        assert "view_file" in tool_names
        assert "list_dir" in tool_names
        assert "find_symbol" in tool_names
        assert "search_text" in tool_names

        # 检查格式是否符合 OpenAI function calling 规范
        for s in schema:
            assert s["type"] == "function"
            assert "name" in s["function"]
            assert "description" in s["function"]
            assert "parameters" in s["function"]

    def test_call_tool_view_file(self, tools):
        """通过 call_tool 调用 view_file"""
        result = tools.call_tool("view_file", {"file_path": "app/main.py"})
        assert "FastAPI" in result

    def test_call_tool_list_dir(self, tools):
        """通过 call_tool 调用 list_dir"""
        result = tools.call_tool("list_dir", {"dir_path": ""})
        assert "app/" in result

    def test_call_unknown_tool(self, tools):
        """调用未知工具"""
        result = tools.call_tool("nonexistent_tool", {})
        assert "未知工具" in result
