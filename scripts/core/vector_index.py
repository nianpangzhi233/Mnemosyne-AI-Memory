"""FAISS vector index wrapper for fast similarity search.

Falls back to brute-force numpy search when faiss is not installed.
"""

import numpy as np


class VectorIndex:
    """Wraps faiss.IndexFlatIP for in-memory vector search.
    Falls back to numpy brute-force if faiss is unavailable."""

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self._index = None
        self._id_map = []
        self._vectors = None  # numpy array backup
        self._deleted_ids = set()  # v6.1: synaptic pruning
        self._use_faiss = False
        try:
            import faiss
            self._use_faiss = True
        except ImportError:
            pass

    def build(self, vectors: np.ndarray, ids: list):
        if self._use_faiss:
            import faiss
            self._index = faiss.IndexFlatIP(self._dimension)
            if len(vectors) > 0:
                self._index.add(vectors.astype(np.float32))
        if len(vectors) > 0:
            self._vectors = vectors.astype(np.float32)
        else:
            self._vectors = np.empty((0, self._dimension), dtype=np.float32)
        self._id_map = list(ids)
        self._deleted_ids.clear()  # v6.1: clean stale marks on rebuild

    def add(self, node_id: str, vector: np.ndarray):
        v = vector.reshape(1, -1).astype(np.float32)
        if self._use_faiss:
            if self._index is None:
                import faiss
                self._index = faiss.IndexFlatIP(self._dimension)
            self._index.add(v)
        self._vectors = np.vstack([self._vectors, v]) if self._vectors is not None and len(self._vectors) > 0 else v
        self._id_map.append(node_id)

    def search(self, query_vec: np.ndarray, top: int = 5) -> list:
        if len(self._id_map) == 0:
            return []
        q = query_vec.reshape(1, -1).astype(np.float32)
        # Fetch slightly more to account for deleted IDs being filtered out
        fetch_k = min(top + len(self._deleted_ids), len(self._id_map))
        if self._use_faiss and self._index is not None:
            scores, indices = self._index.search(q, fetch_k)
            results = []
            for s, i in zip(scores[0], indices[0]):
                if i >= 0 and i < len(self._id_map):
                    nid = self._id_map[i]
                    if nid not in self._deleted_ids:
                        results.append((nid, float(s)))
        else:
            if self._vectors is None or len(self._vectors) == 0:
                return []
            sims = np.dot(self._vectors, q.flatten())
            top_k = min(fetch_k, len(sims))
            idx = np.argpartition(sims, -top_k)[-top_k:]
            idx = idx[np.argsort(-sims[idx])]
            results = []
            for i in idx:
                if i < len(self._id_map):
                    nid = self._id_map[i]
                    if nid not in self._deleted_ids:
                        results.append((nid, float(sims[i])))
        return results[:top]

    def mark_deleted(self, node_id: str):
        """v6.1: Mark node as deleted (synaptic weakening before pruning)"""
        self._deleted_ids.add(node_id)

    def rebuild_needed(self) -> bool:
        """v6.1: Check if stale ratio exceeds 10% threshold"""
        if len(self._id_map) == 0:
            return False
        return len(self._deleted_ids) / len(self._id_map) > 0.1

    def rebuild_if_needed(self, vectors: np.ndarray, ids: list):
        """v6.1: Full rebuild when stale ratio exceeds threshold"""
        if self.rebuild_needed():
            self.build(vectors, ids)
            self._deleted_ids.clear()
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._id_map)
