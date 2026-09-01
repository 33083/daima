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

## 你的工作方式：
1. 先理解用户的问题
2. 如果你不确定答案或者需要查看更多代码，可以调用工具来探索代码库
3. 你可以多次调用工具，每次调用后根据结果决定下一步
4. 最后给出完整、准确的回答

## 可用工具：
- search_code(query) - 语义搜索代码，用自然语言找相关代码
- view_file(file_path, start_line, end_line) - 查看文件的具体内容
- list_dir(dir_path) - 浏览目录结构
- find_symbol(symbol_name) - 按函数名/类名查找定义
- search_text(keyword) - 全文关键词搜索

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
