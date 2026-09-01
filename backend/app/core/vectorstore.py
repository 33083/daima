"""向量库管理"""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from typing import List, Dict, Any
import uuid

from app.config import settings


_client = None
_embed_fn = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _get_embed_fn():
    """Chroma 用的 embedding 函数（本地模型，无需 API）"""
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _embed_fn


def _collection_name(repo_id: int) -> str:
    """每个仓库一个 collection"""
    return f"repo_{repo_id}_code"


def get_or_create_collection(repo_id: int):
    client = _get_client()
    name = _collection_name(repo_id)
    return client.get_or_create_collection(
        name=name,
        embedding_function=_get_embed_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def delete_collection(repo_id: int):
    client = _get_client()
    name = _collection_name(repo_id)
    try:
        client.delete_collection(name=name)
    except Exception:
        pass


def add_code_chunks(repo_id: int, chunks: List[Any]):
    """
    添加代码切片到向量库
    chunks: CodeChunk 列表（来自 code_parser）
    """
    if not chunks:
        return 0

    collection = get_or_create_collection(repo_id)

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        ids.append(chunk_id)
        documents.append(chunk.content)
        metadatas.append({
            "file_path": chunk.file_path,
            "file_name": chunk.file_name,
            "language": chunk.language,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "chunk_type": chunk.chunk_type,
            "symbol_name": chunk.symbol_name,
        })

    # 分批添加（避免一次性太大）
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        batch_end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:batch_end],
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )

    return len(ids)


def search_code(repo_id: int, query: str, top_k: int = 8) -> List[Dict]:
    """检索相关代码片段"""
    collection = get_or_create_collection(repo_id)

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    items = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i] if results["distances"] else 0
            # chroma 用 cosine distance，转成相似度分数
            score = 1.0 - dist
            items.append({
                "file_path": meta.get("file_path", ""),
                "file_name": meta.get("file_name", ""),
                "language": meta.get("language", ""),
                "start_line": int(meta.get("start_line", 0)),
                "end_line": int(meta.get("end_line", 0)),
                "content": doc,
                "score": round(score, 4),
                "vector_score": round(score, 4),
                "chunk_type": meta.get("chunk_type", ""),
                "symbol_name": meta.get("symbol_name", ""),
            })

    return items


def count_chunks(repo_id: int) -> int:
    """统计切片数量"""
    try:
        collection = get_or_create_collection(repo_id)
        return collection.count()
    except Exception:
        return 0
