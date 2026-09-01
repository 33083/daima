"""
代码解析器单元测试
测试核心的代码切片、语言识别、符号提取功能
"""
import os
import tempfile
import pytest

from app.services.code_parser import (
    detect_language,
    should_skip_file,
    collect_code_files,
    chunk_code_file,
    get_file_info,
    detect_repo_language,
    _extract_symbol_names,
    _chunk_by_symbols,
)


class TestDetectLanguage:
    """语言检测测试"""

    def test_python(self):
        assert detect_language("main.py") == "python"

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert detect_language("index.ts") == "typescript"

    def test_vue(self):
        assert detect_language("App.vue") == "vue"

    def test_java(self):
        assert detect_language("User.java") == "java"

    def test_cpp(self):
        assert detect_language("main.cpp") == "cpp"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_unknown(self):
        assert detect_language("file.xyz") is None


class TestShouldSkipFile:
    """文件过滤测试"""

    def test_skip_image(self):
        assert should_skip_file("test.png") is True

    def test_skip_pdf(self):
        assert should_skip_file("doc.pdf") is True

    def test_skip_node_modules(self):
        assert should_skip_file("node_modules/pkg/index.js") is True

    def test_skip_git(self):
        assert should_skip_file(".git/config") is True

    def test_not_skip_python(self):
        assert should_skip_file("app/main.py") is False

    def test_not_skip_js(self):
        assert should_skip_file("src/utils.js") is False


class TestCodeChunker:
    """代码切片测试"""

    @pytest.fixture
    def python_file(self):
        content = '''"""测试文件"""
import os
import sys

class Calculator:
    """计算器类"""

    def __init__(self, initial=0):
        self.value = initial

    def add(self, x):
        """加法"""
        self.value += x
        return self.value

    def subtract(self, x):
        """减法"""
        self.value -= x
        return self.value


def helper_function(a, b):
    """辅助函数"""
    return a + b


def main():
    calc = Calculator(10)
    result = calc.add(5)
    print(result)


if __name__ == "__main__":
    main()
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            path = f.name
        yield path
        os.unlink(path)

    def test_python_symbol_extraction(self, python_file):
        with open(python_file, "r") as f:
            lines = f.readlines()

        functions, classes = _extract_symbol_names(lines, "python")

        assert "Calculator" in classes
        assert "add" in functions
        assert "subtract" in functions
        assert "helper_function" in functions
        assert "main" in functions

    def test_python_chunk_by_symbols(self, python_file):
        with open(python_file, "r") as f:
            lines = f.readlines()

        chunks = _chunk_by_symbols(lines, "test.py", "test.py", "python")

        # 至少能切出类和函数
        chunk_types = [c.chunk_type for c in chunks]
        assert "class" in chunk_types
        assert "function" in chunk_types

        # 检查内容不为空
        for chunk in chunks:
            assert len(chunk.content) > 0
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line

    def test_chunk_code_file_has_summary(self, python_file):
        chunks = chunk_code_file(python_file, os.path.dirname(python_file))

        # 应该至少有文件摘要 + 几个函数/类
        assert len(chunks) >= 3

        # 第一个应该是文件摘要
        assert chunks[0].chunk_type == "file_summary"
        assert "Calculator" in chunks[0].content

    def test_get_file_info(self, python_file):
        info = get_file_info(python_file, os.path.dirname(python_file))

        assert info.language == "python"
        assert info.line_count > 0
        assert info.function_count >= 4
        assert info.class_count >= 1


class TestCollectFiles:
    """文件收集测试"""

    @pytest.fixture
    def test_repo(self):
        """创建一个模拟代码仓库"""
        repo_dir = tempfile.mkdtemp()

        # 创建各种文件
        files = {
            "main.py": "print('hello')",
            "utils/helper.py": "def foo(): pass",
            "src/app.js": "console.log('hi')",
            "src/components/Button.tsx": "export const Button = () => <button/>",
            "README.md": "# Test",
            "node_modules/bad.js": "bad",  # 应该被跳过
            ".git/config": "[core]",       # 应该被跳过
            "docs/doc.pdf": "pdf binary",  # 应该被跳过
        }

        for rel_path, content in files.items():
            full_path = os.path.join(repo_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        yield repo_dir

        import shutil
        shutil.rmtree(repo_dir)

    def test_collect_code_files(self, test_repo):
        files = collect_code_files(test_repo)

        # 应该找到 4 个代码文件（不包括 node_modules/.git/.pdf）
        file_names = [os.path.basename(f) for f in files]
        assert "main.py" in file_names
        assert "helper.py" in file_names
        assert "app.js" in file_names
        assert "Button.tsx" in file_names

        # 不应该包含被跳过的文件
        assert "bad.js" not in file_names
        assert "doc.pdf" not in file_names

    def test_detect_repo_language(self, test_repo):
        files = collect_code_files(test_repo)
        lang = detect_repo_language(files)
        # Python 文件 2 个，是最多的
        assert lang == "python"
