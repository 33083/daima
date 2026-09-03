"""
对话服务：Agent 模式 + 流式问答
- 普通问答：直接检索 + 生成
- Agent 模式：LLM 可以调用工具（search_code, view_file, list_dir 等），多轮思考后给出答案
"""
import json
import uuid
import re
from typing import AsyncGenerator, List, Dict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from sqlalchemy.orm import Session

from app.core.llm import get_llm
from app.services import rag_service
from app.services.repo_service import RepoService
from app.services.agent_tools import CodeAgentTools
from app.services.conversation_service import ConversationService


SYSTEM_PROMPT = """你是一个资深的代码分析助手，精通各种编程语言和代码架构分析。
用户会问你关于代码仓库的问题，你需要准确、专业地回答。

## 安全边界（代码强制，你无法绕过，与语义无关）
以下限制由系统代码强制执行，不管你做什么判断都会生效：
- 最多调用 8 次工具，超过后系统强制停止并要求你给出最终回答
- find_symbol 基于 AST 解析 def/class 语句，只能找函数和类
  如果你用 find_symbol 查一个变量名（如 SECRET_KEY），AST 搜索无结果时，
  系统会自动回退到全文搜索并返回结果。回退结果以"找到 N 处匹配"开头，
  你应该直接用这些结果回答，不需要再手动调 search_text。
  代码保证搜索一定发生、数据一定出现在返回里；不保证你一定能正确解读这些数据。

这些保证的是"系统不会崩溃"和"搜索一定发生"，不保证"答案是对的"。

## 你的工作方式
1. 先理解用户的问题，判断用户问的实体是什么类型（功能描述？函数/类名？变量/常量？）
2. 根据实体类型和工具能力，选择最合适的工具
3. 每次调用工具前，先简要说明你为什么要调这个工具、期望找到什么
4. 根据工具返回结果决定下一步：信息足够就直接回答，不够就继续调工具
5. 优先用最少的步骤找到答案

## 工具选择框架

### 先理解每个工具能回答什么问题
不要死记决策树——先理解每个工具的本质能力：

- **search_code** 回答："用户描述的功能，语义上和哪些代码相关？"
  适合：用户用自然语言描述功能、行为、流程（如"登录逻辑在哪""错误处理怎么做的"）

- **find_symbol** 回答："这个函数/类在哪定义、怎么实现的？"
  适合：用户给了确切的函数名或类名（如"find_user 函数""UserController 类"）
  能力边界：基于 AST 解析 def/class 语句，只能找函数和类。
  变量、常量、import 的符号查不到——如果你用 find_symbol 查 SECRET_KEY，它会返回空。

- **search_text** 回答："这个字符串在哪些文件出现过？"
  适合：变量名、常量名、配置项名、错误信息（如"SECRET_KEY""DATABASE_URL""ConnectionError"）
  当你要找的符号不是函数/类时，用 search_text 替代 find_symbol。

- **view_file** 回答："这个文件里某段代码的上下文是什么？"
  适合：拿到文件路径后想看 import 来源、模块级常量定义、函数完整实现、类的全貌。
  通常不是第一个动作——在 search_code / find_symbol / search_text 给你文件路径之后使用。
  但如果用户直接给了文件路径，跳过搜索直接 view_file 也合理。

- **list_dir** 回答："这个目录下有哪些文件和子目录？"
  适合：了解项目结构。建议不超过 2 次，但你有判断权。

- **git_log** 回答："最近有哪些提交？"
- **git_diff** 回答："某次提交改了什么？"

### 选择方法：问自己两个问题

**问题 1：用户问的"实体"是什么类型？**
- 功能/行为描述 → search_code
- 函数名/类名 → find_symbol
- 变量名/常量/字符串 → search_text
- Git 历史 → git_log，再 git_diff 看变更
- 项目结构 → list_dir

**问题 2：拿到结果后，信息够回答用户问题了吗？**
- 够 → 直接回答
- 不够，需要看文件上下文（import、常量、完整函数体）→ view_file
- 不够，需要追另一个符号的定义 → 回到问题 1

### find_symbol 查不到的实体（重要）
代码里的命名实体分两类：
- def/class 定义的：函数、方法、类 → find_symbol 能找到
- 赋值/import 的：变量、常量、配置项、import 的符号 → find_symbol 查不到

如果你要找的是 SECRET_KEY、DATABASE_URL 这类变量/常量，用 find_symbol 会触发自动回退（见安全边界）。
你也可以直接用 search_text 精确搜索，或用 view_file 看文件顶部的定义。

### find_symbol 自动回退（代码强制的搜索，非代码强制的解读）
如果你用 find_symbol 查了一个名字，AST 无结果时，代码会自动用全文搜索补搜一次。
回退结果以"找到 N 处匹配"开头（和正常 search_text 格式一致），数据在最前面，解释在最后。
直接用返回的数据回答即可，不需要再手动调 search_text，不额外消耗调用配额。

注意：代码保证搜索一定发生、数据一定出现在返回里。但是否正确理解和使用这些数据，仍然取决于你。

### 以下全部是指引，不是代码强制
以上工具选择框架、两个问题——全部是指引，不是系统强制的规则。
系统不会检查你是否遵守了"第一次优先 search_code"或"变量走 search_text"。
你读了这些指引后是否遵守，完全取决于你自己的判断。

这意味着：
- 如果你判断偏离指引更合理（如用户直接给了文件路径），可以偏离。
- 如果你无视指引乱调工具，系统不会阻止你，但会浪费调用配额。
- 8 次调用用完后系统强制停止——这就是安全边界兜住的地方。

你的责任：理解每条指引背后的理由，在具体场景中判断是否适用。
系统的责任：保证你最多浪费 8 次调用后能给出一个答案。

## 可用工具（7 个）：
- search_code(query, top_k) - 语义搜索代码，用自然语言找相关代码
- view_file(file_path, start_line, end_line) - 查看文件的具体内容（看上下文）
- list_dir(dir_path) - 浏览目录结构
- find_symbol(symbol_name) - 按函数名/类名查找定义（仅 def/class，不含变量）
- search_text(keyword) - 全文精确搜索字符串（变量名、常量名、错误信息）
- git_log(limit) - 查看最近 Git 提交记录
- git_diff(commit, compare) - 查看某次提交的代码变更

## 回答要求：
1. 回答要具体，引用具体的文件名、行号和函数名
2. 如果代码比较复杂，可以分步解释
3. 用代码块展示关键代码
4. 诚实说明：如果信息不足，告诉用户你还需要查看哪些文件

## 代码库语言：{language}
"""


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.repo_service = RepoService(db)
        self.llm = get_llm()
        # 简易内存会话
        self._conversations: Dict[str, List] = {}
        # Agent 工具调用记录（用于前端展示）
        self._agent_actions: Dict[str, List] = {}

    async def chat_stream(self, repo_id: int, question: str,
                          conversation_id: str = None,
                          use_agent: bool = True,
                          max_tool_calls: int = 8) -> AsyncGenerator[str, None]:
        """
        流式问答（Agent 模式）
        流程：
        1. 第一次生成：LLM 可能选择调用工具
        2. 执行工具，把结果返回给 LLM
        3. 重复直到 LLM 不再调用工具或达到最大次数
        4. 最终流式输出答案
        """
        repo = self.repo_service.get_repo(repo_id)
        if not repo:
            yield f"event: error\ndata: {json.dumps({'message': '仓库不存在'})}\n\n"
            return

        if repo.status != "ready":
            yield f"event: error\ndata: {json.dumps({'message': f'仓库状态：{repo.status}，暂不可问答'})}\n\n"
            return

        # 生成/获取会话 ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # 初始化 Agent 工具
        agent_tools = CodeAgentTools(self.db, repo_id)
        tools_schema = agent_tools.get_tools_schema()

        # 构建系统消息
        system_prompt = SYSTEM_PROMPT.format(language=repo.language or "未知")

        # 获取历史消息
        history = self._conversations.get(conversation_id, [])
        messages = [SystemMessage(content=system_prompt)] + history + [HumanMessage(content=question)]

        # 记录本次对话的 Agent 动作
        action_log = []

        # 发送 start 事件
        start_data = {
            "conversation_id": conversation_id,
            "repo_name": repo.name,
            "language": repo.language,
            "agent_mode": use_agent,
        }
        yield f"event: start\ndata: {json.dumps(start_data)}\n\n"

        try:
            # Agent 循环：LLM 调用工具 → 执行工具 → 继续思考
            tool_call_count = 0

            while tool_call_count < max_tool_calls:
                # 调用 LLM
                if use_agent:
                    response = await self.llm.ainvoke(messages, tools=tools_schema)
                else:
                    response = await self.llm.ainvoke(messages)

                # 检查是否有工具调用
                tool_calls = getattr(response, 'tool_calls', None) or []

                if not tool_calls or not use_agent:
                    # 没有工具调用，流式输出最终回答
                    break

                # 处理工具调用
                messages.append(response)  # 把 AI 的 tool_calls 消息加入历史

                for tool_call in tool_calls:
                    tool_call_count += 1
                    if isinstance(tool_call, dict):
                        tool_name = tool_call["name"]
                        tool_args = tool_call.get("args", {})
                        tool_call_id = tool_call.get("id", "")
                    else:
                        tool_name = tool_call.name
                        tool_args = tool_call.args
                        tool_call_id = getattr(tool_call, "id", "")

                    # 通知前端：正在调用工具
                    action_data = {
                        "tool": tool_name,
                        "args": tool_args,
                        "step": tool_call_count,
                    }
                    yield f"event: tool_call\ndata: {json.dumps(action_data)}\n\n"

                    action_log.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "step": tool_call_count,
                    })

                    # 执行工具
                    tool_result = agent_tools.call_tool(tool_name, tool_args)

                    # 把工具结果返回给 LLM
                    tool_msg = ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call_id,
                    )
                    messages.append(tool_msg)

                    # 通知前端：工具返回结果
                    result_data = {
                        "tool": tool_name,
                        "step": tool_call_count,
                        "result_length": len(tool_result),
                    }
                    yield f"event: tool_result\ndata: {json.dumps(result_data)}\n\n"

                if tool_call_count >= max_tool_calls:
                    # 达到最大调用次数，强制生成最终答案
                    messages.append(HumanMessage(
                        content=f"（已达到最大工具调用次数 {max_tool_calls}，请基于已有信息给出最终回答）"
                    ))

            # 流式输出最终回答
            full_content = ""
            # 用流式方式生成最终回答
            llm_for_stream = self.llm  # 复用同一个 LLM
            async for chunk in llm_for_stream.astream(messages):
                content = chunk.content or ""
                if content:
                    full_content += content
                    delta_data = {"content": content}
                    yield f"event: delta\ndata: {json.dumps(delta_data)}\n\n"

            # 保存历史（只存用户消息和最终 AI 回答，工具调用过程不存历史，节省上下文）
            history.append(HumanMessage(content=question))
            history.append(AIMessage(content=full_content))
            if len(history) > 20:
                history = history[-20:]
            self._conversations[conversation_id] = history
            self._agent_actions[conversation_id] = action_log

            # 发送 end 事件
            end_data = {
                "agent_actions": action_log,
                "tool_call_count": tool_call_count,
            }
            yield f"event: end\ndata: {json.dumps(end_data)}\n\n"

        except Exception as e:
            err_data = {"message": f"生成失败: {str(e)}"}
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"

    async def chat_stream_with_conv(self, repo_id: int, question: str,
                                     conv_id: int = None,
                                     use_agent: bool = True,
                                     max_tool_calls: int = 8) -> AsyncGenerator[str, None]:
        """
        流式问答（数据库持久化版本）
        对话历史存数据库，支持多会话管理
        """
        repo = self.repo_service.get_repo(repo_id)
        if not repo:
            yield f"event: error\ndata: {json.dumps({'message': '仓库不存在'})}\n\n"
            return

        if repo.status != "ready":
            yield f"event: error\ndata: {json.dumps({'message': f'仓库状态：{repo.status}，暂不可问答'})}\n\n"
            return

        conv_service = ConversationService(self.db)

        # 创建/获取会话
        if not conv_id:
            conv = conv_service.create_conversation(
                repo_id=repo_id,
                mode="agent" if use_agent else "quick",
            )
            conv_id = conv.id
        else:
            conv = conv_service.get_conversation(conv_id)
            if not conv:
                yield f"event: error\ndata: {json.dumps({'message': '会话不存在'})}\n\n"
                return

        # 从数据库加载历史消息（最近 10 轮）
        db_messages, _ = conv_service.list_messages(conv_id, page_size=20)
        history = []
        for msg in db_messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history.append(AIMessage(content=msg.content))
        # 只保留最近 10 轮
        if len(history) > 20:
            history = history[-20:]

        # 初始化 Agent 工具
        agent_tools = CodeAgentTools(self.db, repo_id)
        tools_schema = agent_tools.get_tools_schema()

        # 构建系统消息
        system_prompt = SYSTEM_PROMPT.format(language=repo.language or "未知")

        messages = [SystemMessage(content=system_prompt)] + history + [HumanMessage(content=question)]
        action_log = []

        # 发送 start 事件
        start_data = {
            "conversation_id": str(conv_id),
            "conv_id": conv_id,
            "repo_name": repo.name,
            "language": repo.language,
            "agent_mode": use_agent,
        }
        yield f"event: start\ndata: {json.dumps(start_data)}\n\n"

        try:
            # Agent 循环
            tool_call_count = 0

            while tool_call_count < max_tool_calls:
                if use_agent:
                    response = await self.llm.ainvoke(messages, tools=tools_schema)
                else:
                    response = await self.llm.ainvoke(messages)

                tool_calls = getattr(response, 'tool_calls', None) or []

                if not tool_calls or not use_agent:
                    break

                messages.append(response)

                for tool_call in tool_calls:
                    tool_call_count += 1
                    if isinstance(tool_call, dict):
                        tool_name = tool_call["name"]
                        tool_args = tool_call.get("args", {})
                        tool_call_id = tool_call.get("id", "")
                    else:
                        tool_name = tool_call.name
                        tool_args = tool_call.args
                        tool_call_id = getattr(tool_call, "id", "")

                    action_data = {
                        "tool": tool_name,
                        "args": tool_args,
                        "step": tool_call_count,
                    }
                    yield f"event: tool_call\ndata: {json.dumps(action_data)}\n\n"

                    action_log.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "step": tool_call_count,
                    })

                    tool_result = agent_tools.call_tool(tool_name, tool_args)

                    tool_msg = ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call_id,
                    )
                    messages.append(tool_msg)

                    result_data = {
                        "tool": tool_name,
                        "step": tool_call_count,
                        "result_length": len(tool_result),
                    }
                    yield f"event: tool_result\ndata: {json.dumps(result_data)}\n\n"

                if tool_call_count >= max_tool_calls:
                    messages.append(HumanMessage(
                        content=f"（已达到最大工具调用次数 {max_tool_calls}，请基于已有信息给出最终回答）"
                    ))

            # 流式输出最终回答
            full_content = ""
            async for chunk in self.llm.astream(messages):
                content = chunk.content or ""
                if content:
                    full_content += content
                    delta_data = {"content": content}
                    yield f"event: delta\ndata: {json.dumps(delta_data)}\n\n"

            # 持久化保存用户消息和 AI 回答
            conv_service.add_message(conv_id, "user", question)
            conv_service.add_message(conv_id, "assistant", full_content, meta={
                "agent_actions": action_log,
                "tool_call_count": tool_call_count,
            })

            # 发送 end 事件
            end_data = {
                "conv_id": conv_id,
                "agent_actions": action_log,
                "tool_call_count": tool_call_count,
            }
            yield f"event: end\ndata: {json.dumps(end_data)}\n\n"

        except Exception as e:
            err_data = {"message": f"生成失败: {str(e)}"}
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"
