"""
RAG 检索服务
采用「混合检索 + 重排序」两阶段架构：

阶段一：混合检索（召回）
  - 向量检索（Chroma）：语义匹配
  - BM25 检索（关键词）：精确匹配
  - RRF（倒数排名融合）：融合两路结果

阶段二：重排序（精排）
  - BGE-Reranker：对召回结果精排，提升准确率
"""
from typing import List, Dict
from app.config import settings
from app.core import vectorstore
from app.services.bm25_service import bm25_retriever
from app.services.reranker_service import reranker


def search_related_code(repo_id: int, query: str, top_k: int = None) -> List[Dict]:
    """
    混合检索 + 重排序
    流程：向量检索 + BM25 → RRF 融合 → Reranker 精排 → 返回 top_k
    """
    if top_k is None:
        top_k = settings.rag_top_k

    # 召回阶段：多取一些，留给 reranker 精排
    recall_k = max(top_k * 3, 20)

    # 1. 向量检索
    vector_results = vectorstore.search_code(repo_id, query, top_k=recall_k)

    # 2. BM25 检索
    bm25_results = bm25_retriever.search(repo_id, query, top_k=recall_k)

    # 3. RRF 融合
    merged_results = rrf_fusion([vector_results, bm25_results], top_k=recall_k)

    # 4. 过滤低相关度（向量分数太低的去掉）
    min_vector_score = 0.2
    filtered = []
    for item in merged_results:
        vs = item.get("vector_score", 0)
        bs = item.get("bm25_score", 0)
        # 两路都很低才过滤
        if vs < min_vector_score and bs < 1:
            continue
        filtered.append(item)

    # 5. Reranker 精排
    if filtered:
        reranked = reranker.rerank(query, filtered, top_k=top_k)
        return reranked

    return []


def rrf_fusion(result_lists: List[List[Dict]], top_k: int = 20, k: int = 60) -> List[Dict]:
    """
    RRF（Reciprocal Rank Fusion）倒数排名融合
    公式：score = Σ 1 / (k + rank_i)

    result_lists: [向量结果列表, BM25 结果列表, ...]
    每个列表内的元素按 score 从高到低排序
    """
    # 用文件路径+行号作为唯一标识
    fused = {}  # key -> {item, total_score, ranks}

    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            key = f"{item.get('file_path', '')}:{item.get('start_line', 0)}-{item.get('end_line', 0)}"

            if key not in fused:
                fused[key] = {
                    "item": item.copy(),
                    "total_score": 0.0,
                    "ranks": [],
                }

            fused[key]["total_score"] += 1.0 / (k + rank)
            fused[key]["ranks"].append(rank)

    # 按融合分数排序
    sorted_items = sorted(
        fused.values(),
        key=lambda x: x["total_score"],
        reverse=True
    )[:top_k]

    # 整理输出格式
    output = []
    for entry in sorted_items:
        item = entry["item"]
        item["rrf_score"] = round(entry["total_score"], 4)
        output.append(item)

    return output


def build_context_prompt(references: List[Dict]) -> str:
    """
    把检索到的代码片段格式化成 LLM 的上下文 prompt
    """
    if not references:
        return "（未找到相关代码片段）"

    context_parts = []
    for i, ref in enumerate(references, 1):
        score_info = ""
        if "rerank_score" in ref:
            score_info = f"相关度: {ref['rerank_score']:.3f} (rerank)\n"
        elif "rrf_score" in ref:
            score_info = f"相关度: {ref['rrf_score']:.3f} (rrf)\n"

        context_parts.append(
            f"[代码片段 {i}] 文件: {ref['file_path']}\n"
            f"位置: 第 {ref['start_line']}-{ref['end_line']} 行\n"
            f"类型: {ref.get('chunk_type', '')}\n"
            f"{score_info}"
            f"```\n{ref['content']}\n```"
        )

    return "\n\n".join(context_parts)
