"""应用配置"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 基础
    app_name: str = "CodeRAG Assistant"
    app_env: str = "dev"

    # 数据库
    database_url: str = "sqlite:///./dev.db"

    # 大模型
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Embedding
    embedding_provider: str = "deepseek"
    embedding_model: str = "deepseek-embedding"

    # 向量库
    chroma_persist_dir: str = "./chroma_data"

    # 代码仓库
    repo_storage_dir: str = "./repos"

    # GitHub 加速代理（国内 clone 超时用）
    github_proxy: str = "https://gh-proxy.com/"

    # RAG 参数
    rag_top_k: int = 8
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 150


settings = Settings()
