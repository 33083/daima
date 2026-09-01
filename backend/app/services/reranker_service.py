"""
Reranker 重排序服务
用 BGE-Reranker 对检索结果进行精排，提升 RAG 准确率
"""
from typing import List, Dict
import os
from app.config import settings


class Reranker:
    """BGE Reranker 精排"""

    def __init__(self):
        self._model = None
        self._model_name = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

    def _lazy_load(self):
        """延迟加载模型（首次使用时才加载，节省内存）"""
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
                self._model = FlagReranker(
                    self._model_name,
                    use_fp16=False,
                    device="cpu",
                )
            except Exception as e:
                print(f"[Reranker] 加载模型失败: {e}，将跳过重排序")
                self._model = None  # 标记为加载失败，不再重试
        return self._model is not None

    def rerank(self, query: str, items: List[Dict], top_k: int = 8) -> List[Dict]:
        """
        对检索结果进行重排序
        items: [{content, file_path, ..., score}]
        返回按 rerank 分数排序的 top_k 结果
        """
        if not items:
            return []

        # 先过滤掉内容为空的
        valid_items = [item for item in items if item.get("content")]
        if len(valid_items) <= 1:
            return valid_items[:top_k]

        # 尝试加载模型
        if not self._lazy_load():
            # 加载失败，返回原排序
            return items[:top_k]

        try:
            # 构造 (query, content) 对
            pairs = [[query, item["content"]] for item in valid_items]
            scores = self._model.compute_score(pairs, normalize=True)

            # 附加 rerank 分数并排序
            for i, item in enumerate(valid_items):
                item["rerank_score"] = round(float(scores[i]), 4)

            sorted_items = sorted(
                valid_items,
                key=lambda x: x["rerank_score"],
                reverse=True
            )
            return sorted_items[:top_k]

        except Exception as e:
            print(f"[Reranker] 重排序失败: {e}")
            return items[:top_k]


# 全局单例
reranker = Reranker()
