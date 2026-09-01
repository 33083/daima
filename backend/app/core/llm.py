"""大模型初始化"""
from langchain_openai import ChatOpenAI
from app.config import settings


def get_llm():
    """获取 LLM 实例"""
    if settings.llm_provider == "deepseek":
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.3,
            streaming=True,
        )
    elif settings.llm_provider == "openai":
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.3,
            streaming=True,
        )
    else:
        # Echo 模式（无 Key 时降级，方便调试）
        from langchain_community.chat_models import FakeListChatModel
        return FakeListChatModel(responses=["【演示模式】请配置 LLM API Key 后使用"])


def get_embeddings():
    """获取 embedding 模型"""
    if settings.embedding_provider == "deepseek":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    else:
        # 本地 embedding（需要 sentence-transformers）
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
        )
