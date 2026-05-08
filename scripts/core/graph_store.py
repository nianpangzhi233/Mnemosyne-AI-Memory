#!/usr/bin/env python3
"""GraphStore 接口 — 图存储抽象层

基于现有 graph_write.py / graph_query.py 的数据模型，
定义统一的图存储接口，支持节点/边的增删查、向量检索、关键词检索。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractGraphStore(ABC):
    """图存储抽象基类

    方法签名兼容现有 graph_write / graph_query 的调用方式。
    """

    # ── 节点操作 ──────────────────────────────────────────

    @abstractmethod
    def add_node(self, content: str, node_type: str = "experience",
                 task_type: Optional[str] = None, project: Optional[str] = None,
                 tags: Optional[list] = None, principle: Optional[str] = None,
                 **kwargs) -> str:
        """写入一个节点，返回 node_id

        参数与 graph_write.write_node 一致：
        - content: 经验文本
        - node_type: experience / principle / strategy / correction
        - task_type: 任务类型
        - project: 项目名
        - tags: 标签列表
        - principle: 抽象原理（有值时自动建 is_a 边）
        """

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取节点，返回字段字典或 None"""

    # ── 边操作 ────────────────────────────────────────────

    @abstractmethod
    def add_edge(self, from_id: str, to_id: str, relation_type: str,
                 weight: float = 0.5, source: str = "auto",
                 **kwargs) -> str:
        """写入一条边，返回 edge_id（已存在则返回空串）"""

    @abstractmethod
    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取边，返回字段字典或 None"""

    # ── 查询 ──────────────────────────────────────────────

    @abstractmethod
    def traverse(self, node_id: str, depth: int = 2,
                 max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """从给定节点 BFS 遍历关联节点，返回关系列表"""

    @abstractmethod
    def search_by_vector(self, query: str, top: int = 5,
                         **kwargs) -> List[Dict[str, Any]]:
        """向量相似度搜索，返回 top N 结果（含 similarity / score）"""

    @abstractmethod
    def update_node(self, node_id: str, **fields) -> bool:
        """Update node fields (content, confidence, context_tags, principle, etc.)
        Returns True if node was found and updated."""

    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges. Returns True if deleted."""

    @abstractmethod
    def search_spreading(self, query: str, mode: str = "precise",
                         graph_dims: list = None, tags: list = None,
                         top: int = 5, layer: str = "L0", **kwargs) -> list:
        """SYNAPSE-style spreading activation search.
        mode: 'precise' (strong edges only, high threshold)
              'creative' (strong+weak edges, cross-dim, low threshold)
        graph_dims: filter by graph dimensions ['semantic','causal','temporal','entity']
        tags: filter by context_tags
        """

    @abstractmethod
    def match_preconditions(self, context_vector, top: int = 5) -> list:
        """Find memories whose precondition_vec matches the given context vector.
        Returns list of {id, precondition, predicted_outcome, confidence, similarity}."""

    @abstractmethod
    def verify_node(self, node_id: str) -> bool:
        """Mark node as verified: verified_count++, verified_at=now, confidence+=0.05 (max 1.5).
        Returns True if node exists."""

    @abstractmethod
    def search_by_keyword(self, query: str, top: int = 5,
                          **kwargs) -> List[Dict[str, Any]]:
        """FTS5 关键词搜索，返回 top N 结果"""

    def search_hybrid(self, query: str, top: int = 5,
                      vector_weight: float = 0.7,
                      keyword_weight: float = 0.3,
                      **kwargs) -> List[Dict[str, Any]]:
        """混合检索：向量 + 关键词加权融合

        子类可覆盖此方法以优化融合策略。
        默认实现：分别执行 search_by_vector 和 search_by_keyword，按 ID 合并加权。
        """
        raise NotImplementedError("子类需实现 search_hybrid 或使用默认实现")

    # ── 批量操作（Dream Phase 使用）────────────────────────

    def bulk_get_vectors(self) -> List[Dict[str, Any]]:
        """获取所有有向量的节点，返回 [{id, vector_bytes, content, ...}]"""
        raise NotImplementedError

    def bulk_get_nodes_by_task(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 task_type 分组返回节点，{task: [{id, type, result, ts, ...}]}"""
        raise NotImplementedError

    def bulk_add_edges(self, edges: List[Dict[str, Any]]) -> int:
        """批量写边，edges=[{from_id, to_id, relation_type, weight, source}]，返回新增数"""
        raise NotImplementedError

    def bulk_update_decay(self, updates: List[Dict[str, Any]]) -> int:
        """批量更新衰减，updates=[{id, decay_score, tier}]，返回更新数"""
        raise NotImplementedError

    def bulk_get_edge_pairs(self, relation_type: str) -> set:
        """获取某类型边的 (from, to) 对集合（双向），用于去重检查"""
        raise NotImplementedError

    def get_top_hot_nodes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取 decay_score 最高的 hot 节点"""
        raise NotImplementedError

    def query_edges(self, where_clause: str = "",
                    params: tuple = ()) -> List[Dict[str, Any]]:
        """灵活查询边，返回 [{id, from_id, to_id, relation_type, weight, source, ...}]
        where_clause 如 "source='dream' AND status='active'"
        """
        raise NotImplementedError

    def query_nodes(self, where_clause: str = "",
                    params: tuple = ()) -> List[Dict[str, Any]]:
        """灵活查询节点，返回 [{id, type, content, principle, vector, ...}]
        where_clause 如 "task_type IS NOT NULL"
        """
        raise NotImplementedError

    def add_raw_node(self, **fields) -> str:
        """写入节点，字段由调用方指定（含 vector/principle 等），返回 node_id"""
        raise NotImplementedError

    def veto_edges(self, edge_ids: List[str]) -> int:
        """批量否决边（status='vetoed'），返回否决数"""
        raise NotImplementedError

    def update_meta(self, key: str, value: str):
        """更新 meta 表"""
        raise NotImplementedError

    def count_edges_where(self, where_clause: str = "",
                          params: tuple = ()) -> int:
        """按条件统计边数"""
        raise NotImplementedError

    def count_nodes_where(self, where_clause: str = "",
                          params: tuple = ()) -> int:
        """按条件统计节点数"""
        raise NotImplementedError

    # ── 统计 ──────────────────────────────────────────────

    @abstractmethod
    def count_nodes(self) -> int:
        """返回节点总数"""

    @abstractmethod
    def count_edges(self) -> int:
        """返回边总数"""
