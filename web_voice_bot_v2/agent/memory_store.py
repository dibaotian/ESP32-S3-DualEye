"""
向量长期记忆 —— 轻量 numpy 实现(不依赖 chromadb)。

用途:把每轮对话写入向量库,下轮检索与当前问题语义最相关的旧记忆,
注入 system 提示,让"超出最近窗口"的老事实也能被想起来。

- 嵌入模型:默认 BAAI/bge-small-zh-v1.5(~95MB,中文强,CPU 快),可用
  MEMORY_EMBED_MODEL 覆盖。
- 存储:embeddings.npy(float32 矩阵) + docs.json(文本+元数据),原子落盘。
- 检索:余弦相似度 top-k,带最低分阈值。

注:模型首次加载较慢(几秒),之后常驻。单用户够用;多用户时按 client_id
分库即可(预留 namespace 参数)。
"""

import os
import json
import logging
import threading
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("MEMORY_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
# bge-zh 推荐给"查询"加指令前缀以提升检索效果(被检索的段落不加)
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class VectorMemory:
    def __init__(self, persist_dir: str, model_name: str = DEFAULT_MODEL):
        self.persist_dir = persist_dir
        self.model_name = model_name
        self.emb_path = os.path.join(persist_dir, "embeddings.npy")
        self.docs_path = os.path.join(persist_dir, "docs.json")

        self._lock = threading.Lock()
        self._model = None  # 懒加载
        self._embs: Optional[np.ndarray] = None  # (N, D) float32, 已归一化
        self._docs: List[dict] = []
        self._is_bge = "bge" in model_name.lower()

        os.makedirs(persist_dir, exist_ok=True)
        self._load()

    # -- 模型 --------------------------------------------------------------
    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s (CPU)", self.model_name)
            self._model = SentenceTransformer(self.model_name, device="cpu")
            logger.info("✓ embedding model loaded")

    def _embed(self, texts: List[str], is_query: bool) -> np.ndarray:
        self._ensure_model()
        if self._is_bge and is_query:
            texts = [BGE_QUERY_PREFIX + t for t in texts]
        vecs = self._model.encode(texts, normalize_embeddings=True,
                                  convert_to_numpy=True, show_progress_bar=False)
        return vecs.astype(np.float32)

    # -- 持久化 ------------------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(self.emb_path) and os.path.exists(self.docs_path):
                self._embs = np.load(self.emb_path)
                with open(self.docs_path, "r", encoding="utf-8") as f:
                    self._docs = json.load(f)
                logger.info("Loaded %d memories from %s", len(self._docs), self.persist_dir)
        except Exception as e:
            logger.warning("Failed to load memory: %s", e)
            self._embs, self._docs = None, []

    def _save(self):
        try:
            if self._embs is not None:
                np.save(self.emb_path, self._embs)
            tmp = self.docs_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._docs, f, ensure_ascii=False)
            os.replace(tmp, self.docs_path)
        except Exception as e:
            logger.warning("Failed to save memory: %s", e)

    # -- API ---------------------------------------------------------------
    def add(self, text: str, meta: Optional[dict] = None):
        text = (text or "").strip()
        if not text:
            return
        with self._lock:
            vec = self._embed([text], is_query=False)  # (1, D)
            self._embs = vec if self._embs is None else np.vstack([self._embs, vec])
            self._docs.append({"text": text, "meta": meta or {}})
            self._save()

    def recall(self, query: str, k: int = 3, min_score: float = 0.35) -> List[str]:
        query = (query or "").strip()
        with self._lock:
            if not query or self._embs is None or len(self._docs) == 0:
                return []
            q = self._embed([query], is_query=True)[0]  # (D,)
            sims = self._embs @ q  # 余弦(向量已归一化)
            n = len(self._docs)
            idx = np.argsort(-sims)[:min(k, n)]
            return [self._docs[i]["text"] for i in idx if sims[i] >= min_score]

    def count(self) -> int:
        return len(self._docs)

    def warmup(self):
        """强制加载嵌入模型(空库时 recall 会提前返回,故单独预热)。"""
        self._embed(["warmup"], is_query=True)
