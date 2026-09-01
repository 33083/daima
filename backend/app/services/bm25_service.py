"""
BM25 关键词检索器
与向量检索互补，提升检索准确率
"""
import re
from typing import List, Dict
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """BM25 检索器"""

    def __init__(self):
        self._corpora: Dict[int, dict] = {}  # repo_id -> {bm25, docs, metadatas}

    def _tokenize(self, text: str) -> List[str]:
        """
        简单分词
        - 英文：按空格 + 标点切，转小写
        - 代码：保留标识符（函数名、变量名），按驼峰拆分
        """
        # 先把常见分隔符换成空格
        cleaned = re.sub(r'[(){}\[\],;:.=+\-*/%<>!&|^~`@#$?\'\"\\]', ' ', text)
        tokens = []
        for word in cleaned.split():
            word_lower = word.lower()
            if len(word_lower) < 2:
                continue
            tokens.append(word_lower)
            # 驼峰拆分：camelCase -> camel case
            camel_parts = re.findall(r'[a-z]+|[A-Z][a-z]*|[0-9]+', word)
            if len(camel_parts) > 1:
                tokens.extend([p.lower() for p in camel_parts if len(p) >= 2])
            # 下划线拆分：snake_case -> snake case
            if '_' in word:
                underscore_parts = word.split('_')
                tokens.extend([p.lower() for p in underscore_parts if len(p) >= 2])
        return tokens

    def index(self, repo_id: int, chunks: List[Dict]):
        """
        建立 BM25 索引
        chunks: [{content, file_path, file_name, start_line, end_line, ...}]
        """
        if not chunks:
            return

        documents = [c["content"] for c in chunks]
        metadatas = [{k: v for k, v in c.items() if k != "content"} for c in chunks]
        tokenized_corpus = [self._tokenize(doc) for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)

        self._corpora[repo_id] = {
            "bm25": bm25,
            "documents": documents,
            "metadatas": metadatas,
        }

    def search(self, repo_id: int, query: str, top_k: int = 10) -> List[Dict]:
        """
        BM25 检索
        返回: [{content, file_path, ..., score}]  按 score 从高到低
        """
        if repo_id not in self._corpora:
            return []

        corpus = self._corpora[repo_id]
        bm25 = corpus["bm25"]
        metadatas = corpus["metadatas"]

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = bm25.get_scores(tokenized_query)

        # 按分数排序，取 top_k
        scored_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        results = []
        for idx in scored_indices:
            if scores[idx] <= 0:
                continue
            meta = metadatas[idx].copy()
            meta["score"] = round(float(scores[idx]), 4)
            meta["bm25_score"] = round(float(scores[idx]), 4)
            meta["content"] = corpus["documents"][idx]
            results.append(meta)

        return results

    def delete_index(self, repo_id: int):
        """删除索引"""
        if repo_id in self._corpora:
            del self._corpora[repo_id]

    def has_index(self, repo_id: int) -> bool:
        return repo_id in self._corpora


# 全局单例
bm25_retriever = BM25Retriever()
