"""
代码解析器 —— 项目核心亮点
功能：
1. 识别编程语言
2. 按函数/类/代码块智能切片（比普通文本切片效果好很多）
3. 提取代码结构信息（函数数量、类数量、行数等）

策略：
- 优先用 tree-sitter 做语法树解析（精确，支持函数/类定位）
- tree-sitter 不支持的语言，fallback 到 pygments + 按空行切片
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# 常见代码文件后缀 → 语言
EXT_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".vue": "vue",
}

# 跳过的目录
SKIP_DIRS = {
    "node_modules", ".git", ".svn", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", "__pycache__",
}

# 跳过的文件
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib",
    ".map", ".min.js", ".min.css",
    ".pyc", ".pyo", ".class", ".jar", ".war",
}


@dataclass
class CodeChunk:
    """代码切片"""
    file_path: str
    file_name: str
    language: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str = "code"  # function / class / block / file_summary
    symbol_name: str = ""     # 函数名/类名


@dataclass
class FileInfo:
    """文件信息"""
    file_path: str
    file_name: str
    language: str
    file_size: int
    line_count: int
    function_count: int
    class_count: int


def detect_language(filepath: str) -> Optional[str]:
    """根据文件后缀判断语言"""
    ext = os.path.splitext(filepath)[1].lower()
    return EXT_LANG_MAP.get(ext)


def should_skip_file(filepath: str) -> bool:
    """判断是否跳过该文件"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in SKIP_EXTENSIONS:
        return True
    parts = Path(filepath).parts
    for part in parts:
        if part in SKIP_DIRS:
            return True
    return False


def collect_code_files(repo_path: str) -> List[str]:
    """收集仓库中所有代码文件的路径"""
    code_files = []
    for root, dirs, files in os.walk(repo_path):
        # 过滤掉需要跳过的目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            full_path = os.path.join(root, f)
            if should_skip_file(full_path):
                continue
            lang = detect_language(full_path)
            if lang:
                code_files.append(full_path)
    return sorted(code_files)


# ============ 代码切片 ============

def chunk_code_file(file_path: str, repo_root: str, max_chunk_size: int = 800, overlap: int = 150) -> List[CodeChunk]:
    """
    对单个代码文件进行智能切片
    策略：
    1. 先尝试按函数/类切（用 tree-sitter 或正则）
    2. 如果函数太大，再在函数内部按逻辑块切
    3. 生成文件级别的摘要 chunk（文件路径 + import + 函数列表）
    """
    rel_path = os.path.relpath(file_path, repo_root)
    file_name = os.path.basename(file_path)
    language = detect_language(file_path) or "unknown"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    if not lines:
        return []

    chunks = []

    # 1. 文件摘要 chunk（非常重要，用于整体检索）
    file_summary = _make_file_summary(rel_path, lines, language)
    if file_summary:
        chunks.append(file_summary)

    # 2. 按函数/类切片
    symbol_chunks = _chunk_by_symbols(lines, rel_path, file_name, language)
    chunks.extend(symbol_chunks)

    # 3. 如果没有切出任何符号（比如配置文件），按固定大小切
    if not symbol_chunks:
        block_chunks = _chunk_by_blocks(lines, rel_path, file_name, language, max_chunk_size, overlap)
        chunks.extend(block_chunks)

    return chunks


def get_file_info(file_path: str, repo_root: str) -> FileInfo:
    """获取文件信息"""
    rel_path = os.path.relpath(file_path, repo_root)
    file_name = os.path.basename(file_path)
    language = detect_language(file_path) or "unknown"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        lines = []

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    line_count = len(lines)
    func_count, class_count = _count_symbols(lines, language)

    return FileInfo(
        file_path=rel_path,
        file_name=file_name,
        language=language,
        file_size=file_size,
        line_count=line_count,
        function_count=func_count,
        class_count=class_count,
    )


# ============ 内部方法 ============

def _make_file_summary(file_path: str, lines: List[str], language: str) -> Optional[CodeChunk]:
    """生成文件级摘要 chunk"""
    if len(lines) < 3:
        return None

    # 取前 30 行作为文件概览（通常包含 imports 和文件顶部注释）
    preview_lines = lines[:30]
    preview = "".join(preview_lines)

    # 提取函数/类名列表
    functions, classes = _extract_symbol_names(lines, language)
    symbols_str = ""
    if classes:
        symbols_str += f"\nClasses: {', '.join(classes[:10])}"
    if functions:
        symbols_str += f"\nFunctions: {', '.join(functions[:20])}"

    content = f"# File: {file_path}\n# Language: {language}\n# Total lines: {len(lines)}\n{symbols_str}\n\n--- File Preview ---\n{preview}"

    return CodeChunk(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        language=language,
        content=content,
        start_line=1,
        end_line=len(preview_lines),
        chunk_type="file_summary",
        symbol_name=file_path,
    )


def _chunk_by_symbols(lines: List[str], file_path: str, file_name: str, language: str) -> List[CodeChunk]:
    """
    按函数/类定义切片（用正则实现，不依赖 tree-sitter 编译）
    支持 Python / JavaScript / TypeScript / Java / C++ / Go / C# 等
    """
    chunks = []

    # 不同语言的函数/类定义正则
    patterns = _get_symbol_patterns(language)
    if not patterns:
        return chunks

    # 找到所有符号定义的位置
    symbols = []  # (line_index, symbol_type, symbol_name)
    for i, line in enumerate(lines):
        for sym_type, pattern in patterns.items():
            m = re.match(pattern, line.strip())
            if m:
                name = m.group(1) if m.groups() else line.strip()
                symbols.append((i, sym_type, name))
                break

    if not symbols:
        return chunks

    # 根据符号位置切分
    for idx, (start_idx, sym_type, sym_name) in enumerate(symbols):
        end_idx = symbols[idx + 1][0] if idx + 1 < len(symbols) else len(lines)

        # 找到这个符号的实际结束位置（基于缩进/括号）
        actual_end = _find_symbol_end(lines, start_idx, language)
        end_idx = min(end_idx, actual_end + 1) if actual_end > start_idx else end_idx

        content = "".join(lines[start_idx:end_idx])

        # 太长的函数内部再细分（可选）
        if end_idx - start_idx > 100:
            sub_chunks = _split_long_function(
                lines, start_idx, end_idx, file_path, file_name, language, sym_type, sym_name
            )
            chunks.extend(sub_chunks)
        else:
            chunks.append(CodeChunk(
                file_path=file_path,
                file_name=file_name,
                language=language,
                content=content,
                start_line=start_idx + 1,
                end_line=end_idx,
                chunk_type=sym_type,
                symbol_name=sym_name,
            ))

    return chunks


def _get_symbol_patterns(language: str) -> Dict[str, str]:
    """获取各语言的函数/类定义正则"""
    patterns_map = {
        "python": {
            "class": r"^class\s+([A-Za-z_][A-Za-z0-9_]*)",
            "function": r"^def\s+([A-Za-z_][A-Za-z0-9_]*)",
        },
        "javascript": {
            "class": r"^class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
            "function": r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        },
        "typescript": {
            "class": r"^class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
            "function": r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        },
        "java": {
            "class": r"^(?:public\s+|private\s+|protected\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)",
            "function": r"^(?:public\s+|private\s+|protected\s+)?[\w<>\[\],\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        },
        "cpp": {
            "class": r"^class\s+([A-Za-z_][A-Za-z0-9_]*)",
            "function": r"^[\w:<>\[\],\s*&]+\s+([A-Za-z_~][A-Za-z0-9_]*)\s*\(",
        },
        "go": {
            "function": r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        },
        "csharp": {
            "class": r"^(?:public\s+|private\s+|protected\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)",
            "function": r"^(?:public\s+|private\s+|protected\s+)?[\w<>\[\],\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        },
    }
    return patterns_map.get(language, {})


def _find_symbol_end(lines: List[str], start_idx: int, language: str) -> int:
    """找到函数/类的结束行（基于缩进或括号匹配）"""
    if language == "python":
        # Python 用缩进判断
        start_line = lines[start_idx]
        base_indent = len(start_line) - len(start_line.lstrip())
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent and not line.strip().startswith("#"):
                return i - 1
        return len(lines) - 1
    else:
        # 其他语言用大括号匹配
        brace_count = 0
        found_brace = False
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{")
            brace_count -= line.count("}")
            if "{" in line:
                found_brace = True
            if found_brace and brace_count == 0:
                return i
        return len(lines) - 1


def _split_long_function(lines: List[str], start: int, end: int,
                         file_path: str, file_name: str, language: str,
                         sym_type: str, sym_name: str) -> List[CodeChunk]:
    """长函数按逻辑块（空行/注释）细分"""
    chunks = []
    chunk_size = 50  # 每段 50 行
    overlap = 10

    pos = start
    while pos < end:
        chunk_end = min(pos + chunk_size, end)
        # 尝试在空行处断开
        for i in range(chunk_end - 1, pos + chunk_size // 2, -1):
            if i < len(lines) and lines[i].strip() == "":
                chunk_end = i + 1
                break

        content = "".join(lines[pos:chunk_end])
        header = f"# Part of {sym_type} {sym_name} (lines {pos+1}-{chunk_end})\n"
        chunks.append(CodeChunk(
            file_path=file_path,
            file_name=file_name,
            language=language,
            content=header + content,
            start_line=pos + 1,
            end_line=chunk_end,
            chunk_type=sym_type,
            symbol_name=sym_name,
        ))

        pos = chunk_end - overlap
        if pos >= end or pos == chunk_end - overlap and chunk_end == end:
            break

    return chunks


def _chunk_by_blocks(lines: List[str], file_path: str, file_name: str,
                     language: str, max_size: int, overlap: int) -> List[CodeChunk]:
    """按固定大小 + 空行切片（fallback）"""
    chunks = []
    max_lines = 60
    i = 0
    while i < len(lines):
        end = min(i + max_lines, len(lines))
        # 尽量在空行处断开
        for j in range(end - 1, i + max_lines // 2, -1):
            if j < len(lines) and lines[j].strip() == "":
                end = j + 1
                break
        content = "".join(lines[i:end])
        chunks.append(CodeChunk(
            file_path=file_path,
            file_name=file_name,
            language=language,
            content=content,
            start_line=i + 1,
            end_line=end,
            chunk_type="block",
        ))
        i = end - (overlap // 10)  # 行级 overlap
        if i >= len(lines) or i == end - (overlap // 10) and end == len(lines):
            break
    return chunks


def _extract_symbol_names(lines: List[str], language: str) -> Tuple[List[str], List[str]]:
    """提取文件中的函数名和类名"""
    functions = []
    classes = []
    patterns = _get_symbol_patterns(language)

    for line in lines:
        stripped = line.strip()
        for sym_type, pattern in patterns.items():
            m = re.match(pattern, stripped)
            if m:
                name = m.group(1) if m.groups() else stripped.split()[1].split("(")[0]
                if sym_type == "class":
                    classes.append(name)
                else:
                    functions.append(name)
                break

    return functions, classes


def _count_symbols(lines: List[str], language: str) -> Tuple[int, int]:
    """统计函数和类的数量"""
    funcs, classes = _extract_symbol_names(lines, language)
    return len(funcs), len(classes)


def detect_repo_language(files: List[str]) -> str:
    """判断仓库主要语言"""
    lang_count = {}
    for f in files:
        lang = detect_language(f)
        if lang:
            lang_count[lang] = lang_count.get(lang, 0) + 1
    if not lang_count:
        return "unknown"
    return max(lang_count, key=lang_count.get)
