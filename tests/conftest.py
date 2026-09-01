"""pytest 配置"""
import sys
import os
import tempfile

# 把 backend 目录加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# 测试用临时目录
TEST_TEMP_DIR = tempfile.mkdtemp(prefix="coderag_test_")

# 覆盖配置（在导入 app.config 之前设置环境变量）
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(TEST_TEMP_DIR, 'test.db')}"
os.environ["CHROMA_PERSIST_DIR"] = os.path.join(TEST_TEMP_DIR, "chroma")
os.environ["REPO_STORAGE_DIR"] = os.path.join(TEST_TEMP_DIR, "repos")
os.environ["DEEPSEEK_API_KEY"] = "test-key"
os.environ["EMBEDDING_PROVIDER"] = "deepseek"
