"""
代码 Agent 工具集
LLM 可以主动调用这些工具来探索代码库

工具列表：
1. search_code       - 语义搜索代码
2. view_file         - 查看完整文件
3. list_dir          - 列出目录结构
4. find_symbol       - 查找函数/类定义
5. search_text       - 全文关键词搜索
6. git_log           - 查看最近提交记录
7. git_diff          - 查看某次提交的代码变更
"""
import os
import re
import subprocess
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.services import rag_service
from app.services.repo_service import RepoService
from app.services.code_parser import _extract_symbol_names


class CodeAgentTools:
    """代码助手可用的工具集合"""

    def __init__(self, db: Session, repo_id: int):
        self.db = db
        self.repo_id = repo_id
        self.repo_service = RepoService(db)
        self.repo = self.repo_service.get_repo(repo_id)

    # ==================== 工具定义 ====================

    def search_code(self, query: str, top_k: int = 5) -> str:
        """
        【工具】语义搜索代码
        用自然语言描述你想找的代码，返回最相关的代码片段。
        适合：找某个功能的实现位置、找相似代码。

        参数:
            query: 搜索描述，比如"用户登录逻辑"、"数据库连接配置"
            top_k: 返回结果数量，默认 5
        """
        results = rag_service.search_related_code(self.repo_id, query, top_k=top_k)
        if not results:
            return "未找到相关代码"

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] {r['file_path']} (L{r['start_line']}-{r['end_line']}, "
                f"相关度: {r.get('rerank_score', r.get('rrf_score', r['score'])):.3f})\n"
                f"```\n{r['content'][:500]}\n```"
            )
        return "\n\n".join(parts)

    def view_file(self, file_path: str, start_line: int = 1, end_line: int = 200) -> str:
        """
        【工具】查看文件内容
        传入文件路径，返回文件的具体代码内容。可以指定行号范围。
        适合：看完整函数实现、看文件整体结构。

        参数:
            file_path: 文件的相对路径，比如 "app/main.py"
            start_line: 起始行号，默认 1
            end_line: 结束行号，默认 200
        """
        content = self.repo_service.get_file_content(self.repo_id, file_path)
        if content is None:
            return f"文件不存在: {file_path}"

        lines = content.split("\n")
        total_lines = len(lines)
        start = max(0, start_line - 1)
        end = min(total_lines, end_line)

        selected = lines[start:end]
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i:>4} | {line}")

        header = f"文件: {file_path} (共 {total_lines} 行，显示第 {start+1}-{end} 行)\n"
        return header + "-" * 60 + "\n" + "\n".join(numbered)

    def list_dir(self, dir_path: str = "") -> str:
        """
        【工具】列出目录结构
        查看指定目录下的文件和子目录，用于浏览项目结构。

        参数:
            dir_path: 目录相对路径，留空表示根目录
        """
        if not self.repo:
            return "仓库不存在"

        full_path = os.path.join(self.repo.local_path, dir_path) if dir_path else self.repo.local_path
        if not os.path.exists(full_path) or not os.path.isdir(full_path):
            return f"目录不存在: {dir_path}"

        # 跳过的目录
        skip_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build'}

        try:
            entries = sorted(os.listdir(full_path))
            dirs = []
            files = []
            for e in entries:
                if e.startswith('.'):
                    continue
                full_e = os.path.join(full_path, e)
                if os.path.isdir(full_e):
                    if e in skip_dirs:
                        continue
                    dirs.append(f"📁 {e}/")
                else:
                    files.append(f"📄 {e}")

            result = f"目录: {dir_path or '/'}\n" + "-" * 40 + "\n"
            result += "\n".join(dirs + files)
            if not dirs and not files:
                result += "(空目录)"
            return result
        except Exception as e:
            return f"读取目录失败: {e}"

    def find_symbol(self, symbol_name: str) -> str:
        """
        【工具】查找函数/类定义
        根据符号名（函数名、类名）查找其在代码中的定义位置。
        如果未找到函数/类定义（可能是变量/常量），会自动回退到全文搜索。

        参数:
            symbol_name: 函数名或类名，比如 "get_user"、"UserService"
        """
        if not self.repo:
            return "仓库不存在"

        symbol_lower = symbol_name.lower()
        matches = []

        # 遍历文件，搜索符号定义
        from app.services.code_parser import collect_code_files
        code_files = collect_code_files(self.repo.local_path)

        for file_path in code_files:
            rel_path = os.path.relpath(file_path, self.repo.local_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            # 在每一行中搜索
            for i, line in enumerate(lines):
                stripped = line.strip()
                # 匹配函数或类定义行
                if re.search(r'(def |class |function |const |let |var |=.*=>|interface |type )', stripped):
                    if symbol_lower in stripped.lower():
                        # 取前后 5 行作为上下文
                        start = max(0, i - 2)
                        end = min(len(lines), i + 8)
                        snippet = "".join(lines[start:end])
                        matches.append({
                            "file": rel_path,
                            "line": i + 1,
                            "snippet": snippet.strip(),
                        })
                        if len(matches) >= 10:
                            break
            if len(matches) >= 10:
                break

        if not matches:
            # ===== 代码层自动回退：find_symbol 无结果时，用 search_text 搜同一个名字 =====
            # 格式设计：正确数据放最前面（以"找到 N 处"开头），解释信息放最后
            # 目的：LLM 顺序处理文本，开头是"找到"而非"未找到"，大概率直接用数据
            text_results = self._full_text_search_internal(symbol_name, max_results=10)
            if text_results:
                result = f"找到 {len(text_results)} 处匹配:\n\n"
                for i, m in enumerate(text_results, 1):
                    result += f"[{i}] {m['file']}:{m['line']} — {m['content']}\n"
                result += (
                    f"\n(find_symbol 的 AST 搜索无结果，以上为自动回退的全文搜索结果。"
                    f"'{symbol_name}' 可能是变量/常量而非函数/类。)"
                )
                return result
            else:
                return f"未找到 '{symbol_name}'：函数/类定义和全文搜索均无结果。"

        result = f"找到 {len(matches)} 个匹配:\n\n"
        for i, m in enumerate(matches, 1):
            result += f"[{i}] {m['file']} (第 {m['line']} 行)\n"
            result += f"```\n{m['snippet'][:300]}\n```\n\n"
        return result

    def _full_text_search_internal(self, keyword: str, max_results: int = 30) -> list:
        """全文搜索的内部实现，供 find_symbol 回退使用，不额外消耗调用配额"""
        keyword_lower = keyword.lower()
        matches = []

        from app.services.code_parser import collect_code_files
        code_files = collect_code_files(self.repo.local_path)

        for file_path in code_files:
            rel_path = os.path.relpath(file_path, self.repo.local_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if keyword_lower in line.lower():
                    matches.append({
                        "file": rel_path,
                        "line": i + 1,
                        "content": line.strip()[:200],
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        return matches

    def search_text(self, keyword: str) -> str:
        """
        【工具】全文关键词搜索
        在所有代码文件中搜索指定关键词，返回匹配的行。
        适合：找字符串常量、错误信息、特定注释等。

        参数:
            keyword: 要搜索的关键词
        """
        if not self.repo:
            return "仓库不存在"

        keyword_lower = keyword.lower()
        matches = []

        from app.services.code_parser import collect_code_files
        code_files = collect_code_files(self.repo.local_path)

        for file_path in code_files:
            rel_path = os.path.relpath(file_path, self.repo.local_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if keyword_lower in line.lower():
                    matches.append({
                        "file": rel_path,
                        "line": i + 1,
                        "content": line.strip()[:200],
                    })
                    if len(matches) >= 30:
                        break
            if len(matches) >= 30:
                break

        if not matches:
            return f"未找到关键词: {keyword}"

        result = f"找到 {len(matches)} 处匹配（最多显示 30 条）:\n\n"
        for i, m in enumerate(matches, 1):
            result += f"[{i}] {m['file']}:{m['line']} — {m['content']}\n"
        return result

    # ===== Git 相关工具 =====

    def _run_git(self, *args) -> str:
        """执行 git 命令"""
        if not self.repo or not self.repo.local_path:
            return "仓库路径不存在"

        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo.local_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode != 0:
                return f"Git 命令执行失败: {result.stderr.strip()}"
            return result.stdout.strip() or "（无输出）"
        except subprocess.TimeoutExpired:
            return "Git 命令超时"
        except FileNotFoundError:
            return "未找到 git 命令"
        except Exception as e:
            return f"执行 git 命令出错: {str(e)}"

    def git_log(self, limit: int = 10) -> str:
        """
        【工具】查看最近 Git 提交记录
        返回最近的 commit 列表，包含哈希、作者、时间、提交信息。

        参数:
            limit: 返回最近几条提交，默认 10
        """
        log_format = "%h | %an | %ad | %s"
        output = self._run_git(
            "log", f"--format={log_format}",
            f"-{limit}", "--date=short",
        )
        if not output or output.startswith("Git") or output.startswith("未找到"):
            return f"无法获取 git 日志: {output}"

        lines = output.split("\n")
        result = f"最近 {len(lines)} 条提交:\n\n"
        for line in lines:
            parts = line.split(" | ", 3)
            if len(parts) == 4:
                result += f"commit: {parts[0]}\n作者: {parts[1]}\n时间: {parts[2]}\n信息: {parts[3]}\n\n"
            else:
                result += line + "\n\n"
        return result

    def git_diff(self, commit: str = None, compare: str = None, max_files: int = 20) -> str:
        """
        【工具】查看 Git 代码变更（diff）
        可以查看：
        - 某次提交的变更：传 commit
        - 两个提交之间的差异：传 commit 和 compare
        - 工作区 vs HEAD：都不传

        参数:
            commit: commit 哈希（短哈希也行）
            compare: 要对比的另一个 commit（可选）
            max_files: 最多显示几个文件的 diff，默认 20
        """
        if commit and compare:
            output = self._run_git("diff", f"--stat={max_files}", commit, compare)
            full_diff = self._run_git("diff", commit, compare)
        elif commit:
            output = self._run_git("diff", f"--stat={max_files}", f"{commit}^", commit)
            full_diff = self._run_git("diff", f"{commit}^", commit)
        else:
            output = self._run_git("diff", f"--stat={max_files}")
            full_diff = self._run_git("diff")

        if not output or output.startswith("Git") or output.startswith("未找到"):
            return f"无法获取 diff: {output}"

        # 限制 diff 长度（避免太大）
        diff_lines = full_diff.split("\n")
        if len(diff_lines) > 500:
            truncated_diff = "\n".join(diff_lines[:500])
            truncated_diff += f"\n...（diff 过长，已截断，共 {len(diff_lines)} 行）"
        else:
            truncated_diff = full_diff

        return f"变更统计:\n{output}\n\n===== 详细 Diff =====\n{truncated_diff}"

    # ==================== 工具元数据 ====================

    def get_tools_schema(self) -> List[Dict]:
        """
        返回 OpenAI Function Calling 格式的工具定义
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "语义搜索代码，用自然语言描述你想找的代码，返回最相关的代码片段。适合查找某个功能的实现位置。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索描述，比如'用户登录逻辑'、'数据库连接配置'",
                            },
                            "top_k": {
                                "type": "number",
                                "description": "返回结果数量，默认 5",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "view_file",
                    "description": "查看文件的具体代码内容，可以指定行号范围。适合看完整函数实现、看文件整体结构。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "文件的相对路径，比如 app/main.py",
                            },
                            "start_line": {
                                "type": "number",
                                "description": "起始行号，默认 1",
                                "default": 1,
                            },
                            "end_line": {
                                "type": "number",
                                "description": "结束行号，默认 200",
                                "default": 200,
                            },
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "列出目录下的文件和子目录，用于浏览项目结构。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dir_path": {
                                "type": "string",
                                "description": "目录相对路径，留空表示根目录",
                                "default": "",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_symbol",
                    "description": "根据函数名或类名查找其定义位置。如果未找到（可能是变量/常量），会自动回退到全文搜索，无需手动换工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol_name": {
                                "type": "string",
                                "description": "函数名或类名，比如 get_user、UserService",
                            },
                        },
                        "required": ["symbol_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "全文关键词搜索，在所有代码文件中搜索指定关键词。适合找字符串常量、错误信息等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "要搜索的关键词",
                            },
                        },
                        "required": ["keyword"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_log",
                    "description": "查看最近的 Git 提交记录，包含 commit 哈希、作者、时间和提交信息。适合了解项目最近的开发动态。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "number",
                                "description": "返回最近几条提交，默认 10",
                                "default": 10,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "查看 Git 代码变更（diff），可以看某次提交的改动、两个提交之间的差异、或工作区未提交的改动。适合分析代码变更内容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "commit": {
                                "type": "string",
                                "description": "commit 哈希，不传则看工作区未提交的改动",
                            },
                            "compare": {
                                "type": "string",
                                "description": "要对比的另一个 commit（可选），不传则对比该 commit 的前一个",
                            },
                        },
                    },
                },
            },
        ]

    def call_tool(self, name: str, args: Dict) -> str:
        """调用工具，返回结果字符串"""
        try:
            if name == "search_code":
                return self.search_code(args.get("query", ""), int(args.get("top_k", 5)))
            elif name == "view_file":
                return self.view_file(
                    args.get("file_path", ""),
                    int(args.get("start_line", 1)),
                    int(args.get("end_line", 200)),
                )
            elif name == "list_dir":
                return self.list_dir(args.get("dir_path", ""))
            elif name == "find_symbol":
                return self.find_symbol(args.get("symbol_name", ""))
            elif name == "search_text":
                return self.search_text(args.get("keyword", ""))
            elif name == "git_log":
                return self.git_log(int(args.get("limit", 10)))
            elif name == "git_diff":
                return self.git_diff(
                    args.get("commit"),
                    args.get("compare"),
                    int(args.get("max_files", 20)),
                )
            else:
                return f"未知工具: {name}"
        except Exception as e:
            return f"工具调用失败: {str(e)}"
