"""
BM25 检索器 + RRF 融合测试
"""
import pytest
from app.services.bm25_service import BM25Retriever
from app.services.rag_service import rrf_fusion


class TestBM25Retriever:
    """BM25 检索测试"""

    @pytest.fixture
    def retriever(self):
        r = BM25Retriever()
        chunks = [
            {
                "content": "def login_user(username, password):\n    # 用户登录逻辑\n    check_password(password)\n    return User.get(username)",
                "file_path": "auth.py",
                "file_name": "auth.py",
                "start_line": 1,
                "end_line": 5,
            },
            {
                "content": "def register_user(email, password):\n    # 用户注册\n    user = User.create(email, password)\n    send_welcome_email(email)\n    return user",
                "file_path": "auth.py",
                "file_name": "auth.py",
                "start_line": 10,
                "end_line": 15,
            },
            {
                "content": "class DatabaseConnection:\n    def __init__(self, host, port):\n        self.host = host\n        self.port = port\n    def connect(self):\n        pass",
                "file_path": "db.py",
                "file_name": "db.py",
                "start_line": 1,
                "end_line": 7,
            },
            {
                "content": "function fetchUserData(userId) {\n  // 获取用户数据\n  return axios.get(`/api/users/${userId}`);\n}",
                "file_path": "api.js",
                "file_name": "api.js",
                "start_line": 1,
                "end_line": 4,
            },
        ]
        r.index(1, chunks)
        return r

    def test_search_login(self, retriever):
        results = retriever.search(1, "login user password")
        assert len(results) > 0
        # 第一个结果应该是登录函数
        assert "login_user" in results[0]["content"]

    def test_search_database(self, retriever):
        results = retriever.search(1, "database connection")
        assert len(results) > 0
        assert "DatabaseConnection" in results[0]["content"]

    def test_search_returns_scores(self, retriever):
        results = retriever.search(1, "user login")
        assert len(results) > 0
        assert "score" in results[0]
        assert results[0]["score"] > 0

    def test_search_no_results(self, retriever):
        results = retriever.search(1, "xyznonexistentkeyword")
        assert len(results) == 0

    def test_delete_index(self, retriever):
        assert retriever.has_index(1) is True
        retriever.delete_index(1)
        assert retriever.has_index(1) is False

    def test_camel_case_tokenization(self, retriever):
        """测试驼峰命名分词"""
        results = retriever.search(1, "fetchUserData")
        # 驼峰拆分后应该能匹配到 fetch + user + data
        assert len(results) > 0
        assert "fetchUserData" in results[0]["content"]


class TestRRFFusion:
    """RRF 融合测试"""

    def test_basic_fusion(self):
        """基本融合：两个列表有重叠元素"""
        list_a = [
            {"file_path": "a.py", "start_line": 1, "end_line": 10, "content": "a"},
            {"file_path": "b.py", "start_line": 1, "end_line": 10, "content": "b"},
            {"file_path": "c.py", "start_line": 1, "end_line": 10, "content": "c"},
        ]
        list_b = [
            {"file_path": "b.py", "start_line": 1, "end_line": 10, "content": "b"},
            {"file_path": "c.py", "start_line": 1, "end_line": 10, "content": "c"},
            {"file_path": "d.py", "start_line": 1, "end_line": 10, "content": "d"},
        ]

        merged = rrf_fusion([list_a, list_b], top_k=5)

        # b 和 c 在两个列表都出现，分数应该更高
        paths = [m["file_path"] for m in merged]
        assert "b.py" in paths
        assert "c.py" in paths
        assert "a.py" in paths
        assert "d.py" in paths

        # b 排名应该比 a 高（b 在两个列表排名都靠前）
        assert paths.index("b.py") < paths.index("a.py")

    def test_no_overlap(self):
        """无重叠元素的融合"""
        list_a = [
            {"file_path": "a.py", "start_line": 1, "end_line": 1, "content": "a"},
        ]
        list_b = [
            {"file_path": "b.py", "start_line": 1, "end_line": 1, "content": "b"},
        ]

        merged = rrf_fusion([list_a, list_b])
        assert len(merged) == 2

    def test_top_k_limit(self):
        """结果数量受 top_k 限制"""
        list_a = [
            {"file_path": f"{i}.py", "start_line": 1, "end_line": 1, "content": str(i)}
            for i in range(10)
        ]

        merged = rrf_fusion([list_a], top_k=3)
        assert len(merged) == 3

    def test_rrf_score_present(self):
        """融合后应该有 rrf_score 字段"""
        list_a = [
            {"file_path": "a.py", "start_line": 1, "end_line": 1, "content": "a"},
        ]
        merged = rrf_fusion([list_a])
        assert "rrf_score" in merged[0]
        assert merged[0]["rrf_score"] > 0
