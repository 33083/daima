"""
项目架构概览服务
自动分析代码仓库的目录结构，生成架构说明
"""
import os
import json
from collections import defaultdict
from sqlalchemy.orm import Session

from app.services.repo_service import RepoService
from app.services.code_parser import collect_code_files, detect_language, get_file_info


# 常见架构目录关键词 → 模块说明
ARCH_PATTERNS = {
    # 后端
    "controllers": "控制层 / API 接口层",
    "controller": "控制层 / API 接口层",
    "api": "API 接口",
    "routes": "路由层",
    "router": "路由层",
    "handlers": "请求处理层",
    "services": "业务逻辑层 / 服务层",
    "service": "业务逻辑层 / 服务层",
    "models": "数据模型层 / ORM 实体",
    "model": "数据模型层 / ORM 实体",
    "schemas": "数据校验模型 / DTO",
    "schema": "数据校验模型 / DTO",
    "repository": "数据访问层 / Repository",
    "repositories": "数据访问层 / Repository",
    "dao": "数据访问对象",
    "db": "数据库模块",
    "database": "数据库模块",
    "core": "核心配置 / 工具",
    "config": "配置模块",
    "utils": "工具函数",
    "util": "工具函数",
    "helpers": "辅助函数",
    "middleware": "中间件",
    "exceptions": "异常处理",
    "errors": "错误处理",
    "tests": "单元测试",
    "test": "单元测试",

    # 前端
    "components": "组件库",
    "component": "组件库",
    "views": "页面视图",
    "view": "页面视图",
    "pages": "页面",
    "page": "页面",
    "store": "状态管理",
    "stores": "状态管理",
    "hooks": "自定义 Hooks",
    "hook": "自定义 Hooks",
    "composables": "组合式函数",
    "assets": "静态资源",
    "styles": "样式文件",
    "style": "样式文件",
    "public": "公共静态资源",
    "router": "路由配置",
    "layouts": "布局组件",
    "layout": "布局组件",

    # 通用
    "common": "公共模块",
    "shared": "共享模块",
    "lib": "第三方库封装",
    "libs": "第三方库封装",
    "vendor": "第三方依赖",
    "docs": "文档",
    "doc": "文档",
    "example": "示例代码",
    "examples": "示例代码",
    "demo": "演示代码",
    "scripts": "脚本工具",
    "script": "脚本工具",
    "build": "构建配置",
    "deploy": "部署配置",
    "docker": "Docker 部署",
}


class ArchitectureService:
    """项目架构分析服务"""

    def __init__(self, db: Session):
        self.db = db
        self.repo_service = RepoService(db)

    def generate_overview(self, repo_id: int) -> dict:
        """
        生成项目架构概览
        返回：项目结构、模块说明、技术栈推断、统计数据
        """
        repo = self.repo_service.get_repo(repo_id)
        if not repo:
            return {"error": "仓库不存在"}

        root_path = repo.local_path

        # 1. 收集顶层目录结构
        tree = self._build_tree(root_path, max_depth=3)

        # 2. 分析模块职责
        modules = self._analyze_modules(root_path)

        # 3. 推断技术栈
        tech_stack = self._detect_tech_stack(root_path)

        # 4. 统计信息
        stats = self._compute_stats(root_path)

        # 5. 入口文件分析
        entry_points = self._find_entry_points(root_path)

        return {
            "repo_name": repo.name,
            "tree": tree,
            "modules": modules,
            "tech_stack": tech_stack,
            "stats": stats,
            "entry_points": entry_points,
        }

    def _build_tree(self, root_path: str, max_depth: int = 3) -> dict:
        """构建目录树（只显示前 N 层）"""

        def build(path: str, depth: int = 0) -> dict:
            name = os.path.basename(path) or path
            node = {
                "name": name,
                "type": "dir" if os.path.isdir(path) else "file",
                "children": [],
            }
            if depth >= max_depth or not os.path.isdir(path):
                return node

            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                return node

            # 过滤掉明显不需要的
            skip_dirs = {
                "__pycache__", "node_modules", ".git", ".idea", ".vscode",
                "dist", "build", "target", "bin", "obj", ".next", ".nuxt",
                "venv", "env", ".env", "coverage", ".pytest_cache",
            }
            skip_files_ext = {".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe"}

            for entry in entries:
                entry_path = os.path.join(path, entry)
                if entry.startswith(".") and entry not in {".github", ".dockerignore", ".env.example"}:
                    continue
                if os.path.isdir(entry_path) and entry.lower() in skip_dirs:
                    continue
                if os.path.isfile(entry_path):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in skip_files_ext:
                        continue
                    # 文件太多的目录只显示前 10 个
                    if len(node["children"]) > 15:
                        node["children"].append({
                            "name": "...",
                            "type": "more",
                            "children": [],
                        })
                        break
                node["children"].append(build(entry_path, depth + 1))

            return node

        return build(root_path)

    def _analyze_modules(self, root_path: str) -> list:
        """分析各模块的职责"""
        modules = []
        seen = set()

        try:
            entries = sorted(os.listdir(root_path))
        except PermissionError:
            return []

        for entry in entries:
            entry_path = os.path.join(root_path, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry.startswith(".") or entry.lower() in {
                "__pycache__", "node_modules", ".git", "venv", "dist", "build",
            }:
                continue

            # 找最匹配的描述
            key = entry.lower()
            desc = ARCH_PATTERNS.get(key)

            # 如果没有直接匹配，看是否包含关键词
            if not desc:
                for pattern, pattern_desc in ARCH_PATTERNS.items():
                    if pattern in key and len(pattern) >= 4:
                        desc = pattern_desc
                        break

            if desc:
                modules.append({
                    "name": entry,
                    "description": desc,
                    "confidence": "high" if key in ARCH_PATTERNS else "medium",
                })
            else:
                # 估算一下目录里有什么
                file_types = self._sample_dir_types(entry_path)
                if file_types:
                    desc = f"{', '.join(file_types[:3])} 代码目录"
                else:
                    desc = "其他目录"
                modules.append({
                    "name": entry,
                    "description": desc,
                    "confidence": "low",
                })

        return modules

    def _sample_dir_types(self, dir_path: str, limit: int = 20) -> list:
        """采样目录中的文件类型"""
        types = set()
        count = 0
        try:
            for root, dirs, files in os.walk(dir_path):
                # 跳过常见的无关目录
                dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in {
                    "__pycache__", "node_modules", "venv",
                }]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext and len(ext) <= 5:
                        types.add(ext.lstrip("."))
                        count += 1
                        if count >= limit:
                            return list(types)
                if count >= limit:
                    break
        except Exception:
            pass
        return list(types)

    def _detect_tech_stack(self, root_path: str) -> dict:
        """推断技术栈"""
        stack = {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "build_tools": [],
            "other": [],
        }

        # 顶层文件
        try:
            top_files = set(os.listdir(root_path))
        except Exception:
            top_files = set()

        # 语言 & 框架检测
        if "package.json" in top_files:
            stack["languages"].append("JavaScript / TypeScript")
            pkg = self._read_json(os.path.join(root_path, "package.json"))
            if pkg:
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "vue" in deps:
                    stack["frameworks"].append("Vue.js")
                if "react" in deps:
                    stack["frameworks"].append("React")
                if "next" in deps:
                    stack["frameworks"].append("Next.js")
                if "nuxt" in deps:
                    stack["frameworks"].append("Nuxt.js")
                if "express" in deps:
                    stack["frameworks"].append("Express")
                if "nest" in deps or "@nestjs/core" in deps:
                    stack["frameworks"].append("NestJS")
                if "vite" in deps:
                    stack["build_tools"].append("Vite")
                if "webpack" in deps:
                    stack["build_tools"].append("Webpack")

        if "requirements.txt" in top_files or "pyproject.toml" in top_files:
            stack["languages"].append("Python")
            if "pyproject.toml" in top_files:
                pyproject = self._read_text(os.path.join(root_path, "pyproject.toml"))
                if "fastapi" in pyproject.lower():
                    stack["frameworks"].append("FastAPI")
                if "flask" in pyproject.lower():
                    stack["frameworks"].append("Flask")
                if "django" in pyproject.lower():
                    stack["frameworks"].append("Django")
            if "requirements.txt" in top_files:
                req = self._read_text(os.path.join(root_path, "requirements.txt"))
                if "fastapi" in req.lower():
                    stack["frameworks"].append("FastAPI")
                if "flask" in req.lower():
                    stack["frameworks"].append("Flask")
                if "django" in req.lower():
                    stack["frameworks"].append("Django")
                if "sqlalchemy" in req.lower():
                    stack["databases"].append("SQLAlchemy ORM")

        if "pom.xml" in top_files:
            stack["languages"].append("Java")
            stack["build_tools"].append("Maven")
            pom = self._read_text(os.path.join(root_path, "pom.xml"))
            if "spring-boot" in pom.lower():
                stack["frameworks"].append("Spring Boot")

        if "build.gradle" in top_files or "build.gradle.kts" in top_files:
            stack["languages"].append("Java / Kotlin")
            stack["build_tools"].append("Gradle")

        if "go.mod" in top_files:
            stack["languages"].append("Go")
            stack["build_tools"].append("Go Modules")

        if "Cargo.toml" in top_files:
            stack["languages"].append("Rust")
            stack["build_tools"].append("Cargo")

        if "Gemfile" in top_files:
            stack["languages"].append("Ruby")

        if "composer.json" in top_files:
            stack["languages"].append("PHP")

        # 数据库
        if any(f in top_files for f in ["docker-compose.yml", "docker-compose.yaml"]):
            dc = self._read_text(os.path.join(root_path,
                "docker-compose.yml" if "docker-compose.yml" in top_files else "docker-compose.yaml"))
            if "mysql" in dc.lower():
                stack["databases"].append("MySQL")
            if "postgres" in dc.lower():
                stack["databases"].append("PostgreSQL")
            if "redis" in dc.lower():
                stack["databases"].append("Redis")
            if "mongo" in dc.lower():
                stack["databases"].append("MongoDB")

        # Docker
        if "Dockerfile" in top_files:
            stack["other"].append("Docker")
        if "docker-compose.yml" in top_files or "docker-compose.yaml" in top_files:
            stack["other"].append("Docker Compose")

        # 去重
        for key in stack:
            stack[key] = list(dict.fromkeys(stack[key]))

        return stack

    def _compute_stats(self, root_path: str) -> dict:
        """计算代码统计"""
        code_files = collect_code_files(root_path)

        lang_stats = defaultdict(lambda: {"files": 0, "lines": 0})
        total_files = 0
        total_lines = 0
        total_functions = 0
        total_classes = 0

        for fpath in code_files:
            try:
                lang = detect_language(fpath)
                info = get_file_info(fpath, root_path)
                lang_stats[lang]["files"] += 1
                lang_stats[lang]["lines"] += info.line_count
                total_files += 1
                total_lines += info.line_count
                total_functions += info.function_count
                total_classes += info.class_count
            except Exception:
                continue

        # 按行数排序
        sorted_langs = sorted(
            [{"language": k, **v} for k, v in lang_stats.items()],
            key=lambda x: x["lines"],
            reverse=True,
        )

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "by_language": sorted_langs[:10],
        }

    def _find_entry_points(self, root_path: str) -> list:
        """查找项目入口文件"""
        candidates = [
            ("main.py", "Python 主入口"),
            ("app.py", "Flask/FastAPI 入口"),
            ("app/main.py", "FastAPI 入口"),
            ("main.ts", "TypeScript 主入口"),
            ("main.js", "JavaScript 主入口"),
            ("src/main.ts", "Vue 入口"),
            ("src/main.js", "Vue/React 入口"),
            ("index.js", "Node.js 入口"),
            ("index.ts", "Node.js 入口"),
            ("server.js", "Node.js 服务入口"),
            ("App.vue", "Vue 根组件"),
            ("App.tsx", "React 根组件"),
            ("App.jsx", "React 根组件"),
        ]
        found = []
        for rel_path, desc in candidates:
            full = os.path.join(root_path, rel_path)
            if os.path.isfile(full):
                found.append({"path": rel_path, "description": desc})
        return found

    def _read_text(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    def _read_json(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return json.load(f)
        except Exception:
            return {}
