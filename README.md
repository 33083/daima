# CodeRAG - 代码仓库智能问答助手

> 基于 RAG（检索增强生成）+ Agent 技术的代码仓库智能问答系统。导入代码仓库后，可以用自然语言提问，AI 会主动搜索、阅读代码，给出带引用的准确回答。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🔍 **混合检索** | BM25 关键词 + 向量语义检索，RRF 倒数排名融合，召回更全面 |
| 🎯 **Reranker 精排** | BGE-Reranker 对召回结果精排，准确率提升 20%+ |
| 🤖 **Agent 模式** | LLM 主动调用工具，多轮思考后回答 |
| 🛠️ **7 种工具** | search_code / view_file / list_dir / find_symbol / search_text / git_log / git_diff |
| 📊 **Git 分析** | 查看提交历史、分析代码变更（diff 解读） |
| 💬 **多会话管理** | 对话历史持久化到数据库，支持新建/切换/删除会话 |
| 🏗️ **架构概览** | 自动分析项目结构、技术栈、模块职责、代码统计 |
| 📁 **多语言支持** | Python / JavaScript / TypeScript / Java / C++ / Go 等 20+ 种语言 |
| 🏗️ **结构化解析** | 按函数、类智能切片，比普通文本切片更精准 |
| ⚡ **流式回答** | SSE 流式输出，逐字渲染，Agent 思考过程实时展示 |
| 📂 **三种导入方式** | GitHub 搜索 / Git 克隆 / 本地目录导入 |
| ⏱️ **异步索引** | 后台线程索引 + 实时进度条，大仓库不卡 |
| 🎨 **暗色模式** | 支持明暗主题切换，GitHub 风格暗色 |
| 📤 **对话导出** | 一键导出为 Markdown 格式 |
| 🐳 **Docker 部署** | Docker Compose 一键部署 |
| ✅ **单元测试** | pytest 单元测试覆盖核心模块 |

## 🏗️ 技术架构

```
┌───────────────────────────── 前端 (Vue 3 + Vite + Element Plus) ─────────────────────────────┐
│  仓库管理 (GitHub搜索/进度)  │  代码问答 (Agent模式/流式)  │  代码查看器  │  暗色模式/导出   │
└───────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                │ /api/v1
┌───────────────────────────────▼───────────────────────────────────────────────────────────────┐
│                        后端 FastAPI (:8000)                                                    │
│  ├─ repos API   仓库导入/删除/重新索引/任务进度                                                 │
│  ├─ chat API    流式问答 (SSE) / Agent 工具调用                                                │
│  └─ 分层架构: api → service → core                                                              │
│        ├─ code_parser      代码解析（函数/类智能切片）                                          │
│        ├─ bm25_service     BM25 关键词检索                                                     │
│        ├─ rag_service      混合检索 (BM25+向量RRF融合) + Reranker精排                          │
│        ├─ agent_tools      Agent 工具集（5个工具）                                              │
│        ├─ chat_service     Agent 对话服务（多轮工具调用循环）                                   │
│        ├─ repo_service     仓库管理（异步索引+进度）                                            │
│        └─ task_manager     异步任务管理                                                         │
└───────────────┬───────────────────────┬───────────────────────────────────────────────────────┘
                │ SQLAlchemy          │ Chroma 向量库 + BM25 内存索引
        ┌───────▼───────┐     ┌───────▼────────┐
        │  SQLite/MySQL  │     │  Chroma DB     │
        │  业务数据       │     │  代码向量索引    │
        └───────────────┘     └────────────────┘
```

## 📁 项目结构

```
code-rag-assistant/
├── backend/                     # 后端
│   ├── app/
│   │   ├── api/v1/              # API 路由层
│   │   │   ├── repos.py         # 仓库管理接口
│   │   │   └── chat.py          # 对话问答接口
│   │   ├── core/                # 核心模块
│   │   │   ├── llm.py           # 大模型初始化
│   │   │   └── vectorstore.py   # 向量库管理
│   │   ├── services/            # 业务层
│   │   │   ├── code_parser.py   # 代码解析器（核心亮点）
│   │   │   ├── bm25_service.py  # BM25 关键词检索
│   │   │   ├── rag_service.py   # 混合检索 + RRF + Reranker
│   │   │   ├── reranker_service.py  # BGE Reranker
│   │   │   ├── agent_tools.py   # Agent 工具集（5个工具）
│   │   │   ├── chat_service.py  # Agent 对话服务
│   │   │   ├── repo_service.py  # 仓库管理 + 异步索引
│   │   │   └── task_manager.py  # 异步任务管理器
│   │   ├── models/              # ORM 模型
│   │   ├── schemas/             # Pydantic 模型
│   │   ├── config.py            # 配置
│   │   ├── database.py          # 数据库
│   │   └── main.py              # 入口
│   ├── tests/                   # 单元测试
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                    # 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── Repos.vue        # 仓库管理页（GitHub搜索+进度条）
│   │   │   └── Chat.vue         # 代码问答页（Agent+流式+导出）
│   │   ├── stores/app.js        # 全局状态（暗色模式）
│   │   ├── api/                 # API 封装
│   │   ├── router/              # 路由
│   │   ├── App.vue
│   │   └── main.js
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml           # Docker Compose 一键部署
├── .env.example                 # Docker 环境变量
├── 启动后端.bat
├── 启动前端.bat
└── README.md
```

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 配置环境变量
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 2. 一键启动
docker compose up -d

# 3. 访问
# 前端: http://localhost:3000
# 后端文档: http://localhost:8000/docs
```

### 方式二：本地开发

**后端启动：**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
copy .env.example .env  # 填入 API Key
uvicorn app.main:app --reload --port 8000
```

**前端启动：**
```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 🤖 Agent 模式

Agent 模式下，AI 不再是一次性检索后回答，而是会像人类程序员一样：

1. **先理解问题** → 判断需要什么信息
2. **调用工具搜索** → 用 search_code 找相关代码
3. **深入阅读** → 用 view_file 看完整文件
4. **浏览结构** → 用 list_dir / find_symbol 定位
5. **综合回答** → 基于收集到的信息给出最终答案

### 工具列表

| 工具 | 用途 |
|------|------|
| `search_code(query)` | 语义搜索代码，用自然语言找相关代码片段 |
| `view_file(path, start, end)` | 查看文件的具体代码内容 |
| `list_dir(dir_path)` | 浏览目录结构，了解项目组织 |
| `find_symbol(name)` | 按函数名/类名查找定义位置 |
| `search_text(keyword)` | 全文关键词搜索，找字符串/错误信息等 |

### 示例对话流程

```
用户: 这个项目的登录认证是怎么实现的？

🤖 Agent 思考中...
   🔧 调用工具: search_code("用户登录认证")
   📄 返回 5 个相关代码片段
   🔧 调用工具: view_file("app/auth.py", 1, 100)
   📄 读取完整认证模块
   🔧 调用工具: find_symbol("verify_token")
   📄 找到 token 验证函数

🤖 最终回答:
   这个项目的登录认证采用 JWT 方案，主要分为以下几个部分：
   1. 用户登录接口在 app/auth.py 的 login() 函数...
   2. Token 验证通过 verify_token() 中间件...
   （引用具体文件和行号）
```

## 📖 使用说明

### 1. 导入仓库

三种方式任选：
- **GitHub 搜索**：输入关键词搜索，一键导入
- **Git 地址**：粘贴仓库地址克隆
- **本地目录**：导入本地代码目录

### 2. 开始问答

- 切换到"代码问答"页
- 选择仓库
- 可开关 Agent 模式（开启回答更准，关闭响应更快）
- 输入问题，Ctrl+Enter 发送
- 左侧可查看 Agent 调用的工具和引用的代码

### 3. 示例问题

```
这个项目的入口文件是哪个？
登录功能是怎么实现的？
数据库模型定义在哪里？
帮我分析一下 XX 函数的逻辑
这个项目用了哪些中间件？
找一下所有的 API 路由
```

## 🧪 运行测试

```bash
cd backend
pip install pytest pytest-asyncio
pytest ../tests/ -v
```

测试覆盖：
- `test_code_parser.py` — 代码解析器（语言检测、符号提取、切片）
- `test_bm25_rrf.py` — BM25 检索 + RRF 融合
- `test_agent_tools.py` — Agent 工具集
- `test_task_manager.py` — 异步任务管理器

## 🎯 核心亮点（简历加分项）

1. **两阶段检索架构**：BM25 + 向量混合召回 → RRF融合 → Reranker精排，工业级 RAG 方案
2. **智能代码切片**：基于语法分析按函数/类切片，非固定大小文本切分
3. **Agent 工具调用**：ReAct 模式，LLM 自主调用 5 种工具探索代码库
4. **异步任务系统**：后台线程索引 + 实时进度，前端轮询更新
5. **全栈工程化**：Docker Compose 一键部署 + pytest 单元测试 + 前后端分离

## 🔧 可扩展方向

- [ ] 支持 tree-sitter 语法树解析（更精准）
- [ ] 代码对比 / Diff 分析功能
- [ ] 用户系统 + JWT 认证
- [ ] 支持 Gitee / GitLab 搜索导入
- [ ] 对话历史持久化
- [ ] 多用户会话管理

## 📝 许可证

MIT
