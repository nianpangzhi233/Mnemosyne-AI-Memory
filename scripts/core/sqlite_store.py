#!/usr/bin/env python3
"""SQLiteStore — 基于 SQLite 的图存储实现

迁入现有 graph_write / graph_query / graph_dream 的核心逻辑：
- add_node: 写节点 + 向量编码 + FTS5 触发器 + principle 自动建 is_a 边
- add_edge: 写边，INSERT OR IGNORE 防重复
- search_by_vector: 余弦相似度搜索，含 decay_score 加权
- search_by_keyword: FTS5 MATCH 搜索
- traverse: BFS 双向遍历关联节点
- count_nodes / count_edges: 统计
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import sqlite3

from .graph_store import AbstractGraphStore
from .embedder import AbstractEmbedder, HarrierEmbedder
from .vector_index import VectorIndex
from .contracts import (
    NODE_UPDATE_FIELDS,
    build_context_tags,
    merge_json_dicts,
    merge_json_lists,
    parse_json_list,
    serialize_node_fields,
)

# 默认 db_path: scripts/core/../../graph.db → 项目根目录下
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "graph.db"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "skills"

HALF_LIFE_BY_TYPE = {"experience": 30.0, "principle": 90.0, "strategy": 60.0, "correction": 60.0, "raw": 15.0}

SKILL_STATUSES = {"embryo", "draft", "tested", "evolved", "approved", "deprecated", "needs_revision", "rejected"}
RISK_LEVELS = {"low", "medium", "high"}


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串"""
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _json_loads(value: Any, default: Any):
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if slug:
        return slug[:80]
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]


_TASK_TYPE_ALIASES = {
    "20260414154831": "workflow",
    "bug fix": "debugging",
    "bug-fix": "debugging",
    "bug_fix": "debugging",
    "bugfix": "debugging",
    "security fix": "debugging",
    "security-fix": "debugging",
    "bug diagnosis": "debugging",
    "bug-diagnosis": "debugging",
    "bug_analysis": "debugging",
    "bug-analysis": "debugging",
    "architecture design": "architecture",
    "architecture-design": "architecture",
    "architecture_design": "architecture",
    "architecture decision": "memory_system",
    "architecture-decision": "memory_system",
    "architecture_decision": "memory_system",
    "architecture/refactoring": "architecture",
    "architecture-refactoring": "architecture",
    "architecture redesign": "architecture",
    "architecture-redesign": "architecture",
    "system design": "architecture",
    "system-design": "architecture",
    "system_design_analysis": "architecture",
    "system-design-analysis": "architecture",
    "system audit": "memory_system",
    "system-audit": "memory_system",
    "system architecture audit": "memory_system",
    "system-architecture-audit": "memory_system",
    "system_architecture_audit": "memory_system",
    "systematic audit": "memory_system",
    "systematic-audit": "memory_system",
    "system improvement": "memory_system",
    "system-improvement": "memory_system",
    "system upgrade": "memory_system",
    "system-upgrade": "memory_system",
    "system_upgrade": "memory_system",
    "knowledge_graph_construction": "memory_system",
    "knowledge-graph-construction": "memory_system",
    "memory_maintenance": "memory_system",
    "memory-maintenance": "memory_system",
    "pipeline validation": "testing",
    "pipeline-validation": "testing",
    "test design": "testing",
    "test-design": "testing",
    "test_design": "testing",
    "test planning": "testing",
    "test-planning": "testing",
    "test_planning": "testing",
    "validation": "testing",
    "verification": "testing",
    "quality assurance": "testing",
    "quality-assurance": "testing",
    "integration testing": "testing",
    "integration-testing": "testing",
    "data cleanup": "memory_system",
    "data-cleanup": "memory_system",
    "data_cleanup_and_commit": "memory_system",
    "data-cleanup-and-commit": "memory_system",
    "data migration": "memory_system",
    "data-migration": "memory_system",
    "data migration / bug fix": "memory_system",
    "data-migration-bug-fix": "memory_system",
    "data_migration_bug_fix": "memory_system",
    "data backfill": "memory_system",
    "data-backfill": "memory_system",
    "pipeline refactoring": "memory_system",
    "pipeline-refactoring": "memory_system",
    "code fix / design decision": "coding",
    "code fix design decision": "coding",
    "code-fix-design-decision": "coding",
    "code_fix_design_decision": "coding",
    "code maintenance": "coding",
    "code-maintenance": "coding",
    "code modification": "coding",
    "code-modification": "coding",
    "code_modification": "coding",
    "code refactoring": "coding",
    "code-refactoring": "coding",
    "code_refactoring": "coding",
    "code review": "coding",
    "code-review": "coding",
    "code review gap analysis": "coding",
    "code-review-gap-analysis": "coding",
    "code_review_gap_analysis": "coding",
    "git workflow": "workflow",
    "git-workflow": "workflow",
    "git usage": "workflow",
    "git-usage": "workflow",
    "git_usage": "workflow",
    "gitignore maintenance": "workflow",
    "gitignore-maintenance": "workflow",
    "workflow instruction": "workflow",
    "workflow-instruction": "workflow",
    "workflow_instruction": "workflow",
    "workflow optimization": "workflow",
    "workflow-optimization": "workflow",
    "workflow_optimization": "workflow",
    "task resumption": "workflow",
    "task-resumption": "workflow",
    "release prep": "deployment",
    "release-prep": "deployment",
    "tool design": "cli_tool",
    "tool-design": "cli_tool",
    "tool usage": "cli_tool",
    "tool-usage": "cli_tool",
    "tool_usage": "cli_tool",
    "cli improvement": "cli_tool",
    "cli-improvement": "cli_tool",
    "cli_improvement": "cli_tool",
    "localization": "documentation",
    "feature specification": "documentation",
    "feature-specification": "documentation",
    "feature_specification": "documentation",
    "image generation": "tupian",
    "image-generation": "tupian",
    "image_generation": "tupian",
    "interface audit": "visual_design",
    "interface-audit": "visual_design",
    "interface_audit": "visual_design",
    "cost optimization": "workflow",
    "cost-optimization": "workflow",
    "cost_optimization": "workflow",
    "data normalization": "memory_system",
    "data-normalization": "memory_system",
    "data_normalization": "memory_system",
    "bug fix system improvement": "memory_system",
    "bug-fix-system-improvement": "memory_system",
    "bug_fix_system_improvement": "memory_system",
    "system evaluation": "memory_system",
    "system-evaluation": "memory_system",
    "system_evaluation": "memory_system",
    "architecture refactoring": "architecture",
    "architecture_refactoring": "architecture",
    "skill emergence": "skill_memory",
    "skill-emergence": "skill_memory",
    "skill evolution": "skill_memory",
    "skill-evolution": "skill_memory",
    "skill_evolution": "skill_memory",
}


def _normalize_task_type(ttype: Optional[str]) -> Optional[str]:
    if not ttype:
        return None
    raw = str(ttype).strip().lower()
    if not raw:
        return None
    raw = raw.replace("/", " ").replace("&", " ")
    raw = re.sub(r"\s+", " ", raw)
    if raw in _TASK_TYPE_ALIASES:
        return _TASK_TYPE_ALIASES[raw]
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if slug in _TASK_TYPE_ALIASES:
        return _TASK_TYPE_ALIASES[slug]
    if not slug:
        return None
    return slug[:80]


_PROJECT_MAP = {
    "memory-evolution": "memory_system",
    "growth-tree": "visual_design",
    "local-api-gateway": "api_proxy",
    "workbuddy": "workflow",
}

_TASK_TYPE_SIMILARITY_THRESHOLD = 0.55


class SQLiteStore(AbstractGraphStore):
    """基于 SQLite + sqlite3 的图存储实现

    内部复用 BgeM3Embedder 做向量编码，
    用标准库 sqlite3 直接操作 graph.db。
    """

    def __init__(self, db_path: Optional[str] = None, embedder=None):
        self._db_path = db_path or str(_DEFAULT_DB_PATH)
        self._embedder = embedder or HarrierEmbedder()
        self._vector_index = None  # lazy init
        self._precondition_index = None  # lazy init
        self._task_type_index = None  # lazy init

    _MAX_ABSTRACT = 150
    _MAX_OVERVIEW = 600

    @staticmethod
    def _make_abstract(content: str, principle: str = None) -> str:
        parts = [content[:150]]
        if principle and len(parts[0]) + len(principle) + 3 <= 150:
            parts.append(principle)
        return " | ".join(parts)[:150]

    @staticmethod
    def _make_overview(content: str, principle: str = None,
                       tags_json: str = None) -> str:
        parts = [content[:600]]
        if principle:
            parts.append(f"principle: {principle}")
        if tags_json and tags_json not in ("[]", "null"):
            parts.append(f"tags: {tags_json}")
        return "\n".join(parts)[:600]

    # ── 连接管理 ──────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_task_type_index(self):
        if self._task_type_index is not None:
            return
        self._task_type_index = VectorIndex()

        conn = self._connect()
        try:
            cur = conn.cursor()

            registered_raw = cur.execute(
                "SELECT value FROM meta WHERE key='registered_task_types'"
            ).fetchone()
            if not registered_raw:
                return
            registered = set()
            try:
                registered = set(json.loads(registered_raw[0]))
            except (json.JSONDecodeError, TypeError):
                return

            for ttype in registered:
                representative_contents = []
                cur.execute(
                    "SELECT content, principle FROM nodes WHERE task_type=? AND type='experience' LIMIT 10",
                    (ttype,)
                )
                for row in cur.fetchall():
                    text = row[0] or ""
                    if row[1]:
                        text += " " + row[1]
                    if text.strip():
                        representative_contents.append(text)

                if representative_contents:
                    combined = " ".join(representative_contents)[:500]
                    vec = self._embedder.encode(combined)
                    self._task_type_index.add(ttype, vec)
        finally:
            conn.close()

    def _register_task_type(self, ttype: str):
        ttype = _normalize_task_type(ttype)
        if not ttype:
            return
        conn = self._connect()
        try:
            cur = conn.cursor()
            registered_raw = cur.execute(
                "SELECT value FROM meta WHERE key='registered_task_types'"
            ).fetchone()
            registered = set()
            if registered_raw:
                try:
                    registered = set(json.loads(registered_raw[0]))
                except (json.JSONDecodeError, TypeError):
                    pass
            if ttype not in registered:
                registered.add(ttype)
                cur.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES('registered_task_types', ?)",
                    (json.dumps(sorted(registered), ensure_ascii=False),)
                )
                conn.commit()
        finally:
            conn.close()

    def _resolve_task_type(self, content: str, task_type: Optional[str],
                           project: Optional[str] = None) -> Optional[str]:
        if task_type:
            task_type = _normalize_task_type(task_type)
            self._register_task_type(task_type)
            return task_type

        if project:
            slug = _slugify(project)
            direct = _PROJECT_MAP.get(slug)
            if direct:
                return direct
            conn = self._connect()
            try:
                cur = conn.cursor()
                registered_raw = cur.execute(
                    "SELECT value FROM meta WHERE key='registered_task_types'"
                ).fetchone()
                if registered_raw:
                    try:
                        registered = set(json.loads(registered_raw[0]))
                        for existing in registered:
                            if slug == existing or slug.startswith(existing) or existing.startswith(slug):
                                return existing
                    except (json.JSONDecodeError, TypeError):
                        pass
            finally:
                conn.close()

        if not content or len(content.strip()) < 10:
            if project:
                new_type = _slugify(project)
                self._register_task_type(new_type)
                return new_type
            return None

        self._ensure_task_type_index()
        if self._task_type_index is not None and self._task_type_index.count > 0:
            vec = self._embedder.encode(content)
            results = self._task_type_index.search(vec, top=1)
            if results and results[0][1] >= _TASK_TYPE_SIMILARITY_THRESHOLD:
                return results[0][0]

        if project:
            new_type = _slugify(project)
            self._register_task_type(new_type)
            return new_type

        return None

    # ── 节点操作 ──────────────────────────────────────────

    def add_node(self, content: str, node_type: str = "experience",
                 task_type: Optional[str] = None, project: Optional[str] = None,
                 tags: Optional[list] = None, principle: Optional[str] = None,
                 precondition: Optional[str] = None,
                 predicted_outcome: Optional[str] = None,
                 context_tags: Optional[list] = None,
                 metadata: Optional[dict] = None,
                 **kwargs) -> str:
        task_type = self._resolve_task_type(content, task_type, project)
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        context_tags_json = build_context_tags(context_tags, task_type, project)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._connect()
        try:
            cur = conn.cursor()

            # 第一优先：principle 精确归类
            # 同 principle = 同一类经验，人脑的"抽象归类"
            if principle and node_type == "experience":
                cur.execute("""
                    SELECT id, base_score, access_count FROM nodes
                    WHERE principle = ? AND type = 'experience'
                    ORDER BY base_score DESC LIMIT 1
                """, (principle,))
                match = cur.fetchone()
                if match:
                    matched_id, old_base, old_access = match
                    new_base = min(1.5, old_base + 0.1)
                    new_access = old_access + 1
                    cur.execute("""
                        UPDATE nodes SET base_score=?, decay_score=?,
                                          access_count=?, last_access=?, updated_at=?
                        WHERE id=?
                    """, (new_base, min(2.0, new_base * 1.2), new_access,
                          _now_iso(), _now_iso(), matched_id))
                    self._merge_node_fields(cur, matched_id, task_type, project, tags_json,
                                            metadata_json, context_tags_json,
                                            precondition, predicted_outcome)

                    cur.execute(
                        "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                        "WHERE key='total_nodes'"
                    )
                    conn.commit()
                    # v6.1: auto-associate even on principle merge
                    self._ensure_vector_index()
                    if self._vector_index.count > 0:
                        vec = self._embedder.encode(content)
                        related = self._vector_index.search(vec, top=4)
                        for related_id, sim in related:
                            if related_id != matched_id and sim > 0.7:
                                self.add_edge(matched_id, related_id, "similar_to",
                                              weight=round(sim, 3), source="auto")
                    return matched_id

            # 第二优先：向量兜底（无 principle 时按语义相似度合并）
            if node_type == "experience":
                vector = self._embedder.encode(content)
                vector_blob = vector.astype(np.float32).tobytes()

                # v6.1: Use VectorIndex fast routing instead of full-table scan
                self._ensure_vector_index()
                if self._vector_index.count > 0:
                    candidates = self._vector_index.search(vector, top=1)
                    if candidates and candidates[0][1] > 0.92:
                        best_id = candidates[0][0]
                        cur.execute("SELECT base_score, access_count FROM nodes WHERE id=?", (best_id,))
                        row = cur.fetchone()
                        old_base = row[0] if row else 0.8
                        old_access = row[1] if row else 0
                        new_base = min(1.5, old_base + 0.1)
                        cur.execute("""
                            UPDATE nodes SET base_score=?, decay_score=?,
                                              access_count=access_count+1,
                                              last_access=?, updated_at=?
                            WHERE id=?
                        """, (new_base, min(2.0, new_base * 1.2), _now_iso(), _now_iso(), best_id))
                        self._merge_node_fields(cur, best_id, task_type, project, tags_json,
                                                metadata_json, context_tags_json,
                                                precondition, predicted_outcome)

                        cur.execute(
                            "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                            "WHERE key='total_nodes'"
                        )
                        conn.commit()
                        return best_id
            else:
                vector = self._embedder.encode(content)
                vector_blob = vector.astype(np.float32).tobytes()

            if 'vector_blob' not in dir():
                vector = self._embedder.encode(content)
                vector_blob = vector.astype(np.float32).tobytes()

            node_id = str(uuid.uuid4())
            created = _now_iso()
            abstract = self._make_abstract(content, principle)
            overview = self._make_overview(content, principle, tags_json)

            # Phase 3: new field defaults
            half_life = HALF_LIFE_BY_TYPE.get(node_type, 30.0)

            # Phase 3: precondition vector encoding
            precondition_vec = None
            if precondition:
                precondition_vec = self._embedder.encode(precondition).astype(np.float32).tobytes()

            cur.execute("""
                INSERT INTO nodes(id, type, content, principle, vector, tier,
                                  decay_score, base_score, access_count, last_access,
                                  created_at, updated_at, task_type, project, tags, metadata,
                                  abstract, overview,
                                  confidence, verified_count, half_life_days, context_tags,
                                  precondition, predicted_outcome, precondition_vec)
                VALUES (?, ?, ?, ?, ?, 'hot', 0.8, 0.8, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        1.0, 0, ?, ?, ?, ?, ?)
            """, (node_id, node_type, content, principle, vector_blob,
                   created, created, created, task_type, project, tags_json,
                   metadata_json,
                   abstract, overview,
                   half_life, context_tags_json,
                   precondition, predicted_outcome, precondition_vec))

            if principle:
                cur.execute("""
                    SELECT id FROM nodes
                    WHERE principle = ? AND id != ? AND type != 'experience'
                    LIMIT 1
                """, (principle, node_id))
                match = cur.fetchone()
                if match:
                    self._write_edge_inner(cur, node_id, match[0], "is_a",
                                           weight=0.8, source="auto")

            cur.execute(
                "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                "WHERE key='total_nodes'"
            )
            conn.commit()

            # Incremental vector index update
            if self._vector_index is not None:
                self._vector_index.add(node_id, np.frombuffer(vector_blob, dtype=np.float32))

            # Phase 3: Update precondition index with new vector
            if precondition and precondition_vec:
                self._ensure_precondition_index()
                if self._precondition_index is not None:
                    self._precondition_index.add(node_id, np.frombuffer(precondition_vec, dtype=np.float32))

            # Phase 3: Predictive validation (only top-1 match to limit embed calls)
            if precondition:
                self._ensure_precondition_index()
                if self._precondition_index and self._precondition_index.count > 0:
                    pre_vec = np.frombuffer(precondition_vec, dtype=np.float32)
                    matches = self._precondition_index.search(pre_vec, top=2)  # v6.1: top=2 to find non-self match
                    for match_id, sim in matches:
                        if match_id == node_id:
                            continue
                        old = self.get_node(match_id)
                        if old and old.get("predicted_outcome"):
                            old_pred_vec = self._embedder.encode(old["predicted_outcome"])
                            new_content_vec = vector  # v6.1: reuse already-encoded content vector
                            contradiction_sim = float(np.dot(old_pred_vec, new_content_vec))
                            if contradiction_sim < 0.3:
                                self.add_edge(node_id, match_id, "contradicts", weight=0.8, source="auto")
                                conn2 = self._connect()
                                try:
                                    conn2.execute("UPDATE nodes SET confidence = MAX(0.0, confidence - 0.2) WHERE id=?", (match_id,))
                                    conn2.commit()
                                finally:
                                    conn2.close()
                            else:
                                self.verify_node(match_id)

            # v6.1: Real-time auto-association — find top-3 similar nodes and create weak edges
            self._ensure_vector_index()
            if self._vector_index.count > 0:
                related = self._vector_index.search(vector, top=4)
                for related_id, sim in related:
                    if related_id == node_id:
                        continue
                    if sim > 0.7:
                        self.add_edge(node_id, related_id, "similar_to",
                                      weight=round(sim, 3), source="auto")

            return node_id
        finally:
            conn.close()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取节点，返回字段字典或 None"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, type, content, principle, tier, decay_score, base_score,
                       access_count, last_access, created_at, updated_at,
                       task_type, project, tags, metadata, abstract, overview,
                       confidence, verified_at, verified_count, half_life_days,
                       precondition, predicted_outcome, context_tags, precondition_vec
                FROM nodes WHERE id = ?
            """, (node_id,))
            row = cur.fetchone()
            if row is None:
                return None
            keys = ["id", "type", "content", "principle", "tier", "decay_score",
                    "base_score", "access_count", "last_access", "created_at",
                    "updated_at", "task_type", "project", "tags", "metadata",
                    "abstract", "overview",
                    "confidence", "verified_at", "verified_count", "half_life_days",
                    "precondition", "predicted_outcome", "context_tags", "precondition_vec"]
            result = dict(zip(keys, row))
            # 反序列化 tags
            if result.get("tags"):
                try:
                    result["tags"] = json.loads(result["tags"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result["metadata"] = _json_loads(result.get("metadata"), {})
            result["context_tags"] = _json_loads(result.get("context_tags"), [])
            return result
        finally:
            conn.close()

    # ── 边操作 ────────────────────────────────────────────

    def add_edge(self, from_id: str, to_id: str, relation_type: str,
                 weight: float = 0.5, source: str = "auto",
                 **kwargs) -> str:
        """写入一条边，返回 edge_id（已存在则返回空串）

        逻辑迁自 graph_write.write_edge：
        INSERT OR IGNORE 防重复 + 更新 meta.total_edges。
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            edge_id = str(uuid.uuid4())
            created = _now_iso()
            graph_dim = kwargs.get("graph_dim", self._default_graph_dim(relation_type))
            strength = kwargs.get("strength", self._default_strength(weight))
            cur.execute("""
                INSERT OR IGNORE INTO edges(id, from_id, to_id, relation_type,
                                            weight, source, status, created_at,
                                            graph_dim, strength)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """, (edge_id, from_id, to_id, relation_type, weight, source, created,
                  graph_dim, strength))

            if cur.rowcount > 0:
                cur.execute(
                    "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                    "WHERE key='total_edges'"
                )
                conn.commit()
                return edge_id
            else:
                conn.commit()
                return ""  # 边已存在
        finally:
            conn.close()

    # ── Skill artifacts (v7.0 M1) ─────────────────────────

    def _make_skill_content(self, name: str, trigger_patterns: list = None,
                            procedure: list = None, verification: str = None) -> str:
        parts = [f"Skill: {name}"]
        if trigger_patterns:
            parts.append("Trigger: " + "; ".join(str(t) for t in trigger_patterns))
        if procedure:
            parts.append("Procedure: " + "; ".join(str(p) for p in procedure))
        if verification:
            parts.append("Verification: " + str(verification))
        return "\n".join(parts)

    def _has_active_edge(self, node_id: str, relation_type: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.cursor()
            row = cur.execute("""
                SELECT 1 FROM edges
                WHERE from_id=? AND relation_type=? AND status='active'
                LIMIT 1
            """, (node_id, relation_type)).fetchone()
            return row is not None
        finally:
            conn.close()

    def _count_active_edges(self, node_id: str, relation_type: str) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            row = cur.execute("""
                SELECT COUNT(*) FROM edges
                WHERE from_id=? AND relation_type=? AND status='active'
            """, (node_id, relation_type)).fetchone()
            return int(row[0] if row else 0)
        finally:
            conn.close()

    def _unique_skill_slug(self, base_slug: str) -> str:
        conn = self._connect()
        try:
            cur = conn.cursor()
            slug = base_slug
            suffix = 2
            while cur.execute("SELECT 1 FROM skill_artifacts WHERE slug=?", (slug,)).fetchone():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            return slug
        finally:
            conn.close()

    def create_skill_artifact(self, name: str, source_node_ids: List[str],
                              content: str = None, status: str = "draft",
                              trigger_patterns: List[str] = None,
                              preconditions: List[str] = None,
                              procedure: List[str] = None,
                              verification: str = None,
                              failure_modes: List[str] = None,
                              risk_level: str = "medium",
                              metadata: Dict[str, Any] = None,
                              slug: str = None) -> str:
        """Create a skill node, its artifact row, and crystallized_from edges."""
        if status not in SKILL_STATUSES:
            raise ValueError(f"invalid skill status: {status}")
        if risk_level not in RISK_LEVELS:
            raise ValueError(f"invalid risk_level: {risk_level}")
        if not source_node_ids:
            raise ValueError("source_node_ids is required")

        trigger_patterns = trigger_patterns or []
        preconditions = preconditions or []
        procedure = procedure or []
        failure_modes = failure_modes or []
        metadata = metadata or {}
        content = content or self._make_skill_content(name, trigger_patterns, procedure, verification)
        slug = self._unique_skill_slug(slug or _slugify(name))

        node_id = self.add_node(
            content=content,
            node_type="skill",
            task_type="skill_memory",
            tags=["skill", status, risk_level],
            principle=name,
        )
        created = _now_iso()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO skill_artifacts(
                    node_id, name, slug, status, version,
                    trigger_patterns, preconditions, procedure, verification, failure_modes,
                    risk_level, review_status, inject_enabled, trial_enabled, requires_feedback,
                    source_node_ids, evidence_node_ids, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, '0.1.0', ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, '[]', ?, ?, ?)
            """, (
                node_id, name, slug, status,
                _json_dumps(trigger_patterns), _json_dumps(preconditions),
                _json_dumps(procedure), verification, _json_dumps(failure_modes),
                risk_level, status, _json_dumps(source_node_ids), created, created,
                json.dumps(metadata, ensure_ascii=False),
            ))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.close()
            raise ValueError(f"skill artifact insert failed: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

        for source_id in source_node_ids:
            self.add_edge(node_id, source_id, "crystallized_from", weight=0.9, source="skill_crystallize")
        return node_id

    def get_skill_artifact(self, node_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM skill_artifacts WHERE node_id=?", (node_id,))
            row = cur.fetchone()
            if not row:
                return None
            keys = [d[0] for d in cur.description]
            artifact = dict(zip(keys, row))
            for key in ("trigger_patterns", "preconditions", "procedure", "failure_modes", "source_node_ids", "evidence_node_ids"):
                artifact[key] = _json_loads(artifact.get(key), [])
            artifact["metadata"] = _json_loads(artifact.get("metadata"), {})
            return artifact
        finally:
            conn.close()

    def update_skill_artifact(self, node_id: str, **fields) -> bool:
        if not fields:
            return False
        allowed = {
            "name", "slug", "status", "version", "trigger_patterns", "preconditions",
            "procedure", "verification", "failure_modes", "risk_level", "review_status",
            "approval_mode", "inject_enabled", "trial_enabled", "requires_feedback",
            "mnemosyne_score", "darwin_score", "final_score", "source_node_ids",
            "evidence_node_ids", "trial_count", "trial_success_count", "trial_failure_count",
            "last_trial_at", "promotion_candidate", "needs_revision", "file_path",
            "file_hash", "file_synced_at", "approved_at", "deprecated_at", "metadata",
            "latest_darwin_score", "latest_mnemosyne_score", "latest_live_test_delta",
            "latest_eval_mode", "latest_decision", "latest_decision_reason",
        }
        json_fields = {"trigger_patterns", "preconditions", "procedure", "failure_modes", "source_node_ids", "evidence_node_ids", "metadata"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = _now_iso()
        for key in list(updates):
            if key in json_fields and not isinstance(updates[key], str):
                updates[key] = json.dumps(updates[key], ensure_ascii=False)
        sets = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [node_id]
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE skill_artifacts SET {sets} WHERE node_id=?", values)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_skill_artifacts(self, statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            sql = "SELECT node_id FROM skill_artifacts"
            params = []
            if statuses:
                placeholders = ", ".join("?" for _ in statuses)
                sql += f" WHERE status IN ({placeholders})"
                params.extend(statuses)
            cur.execute(sql, params)
            return [self.get_skill_artifact(row[0]) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取边，返回字段字典或 None"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, from_id, to_id, relation_type, weight, source,
                       status, created_at, graph_dim, strength
                FROM edges WHERE id = ?
            """, (edge_id,))
            row = cur.fetchone()
            if row is None:
                return None
            keys = ["id", "from_id", "to_id", "relation_type", "weight",
                    "source", "status", "created_at", "graph_dim", "strength"]
            return dict(zip(keys, row))
        finally:
            conn.close()

    # ── 查询 ──────────────────────────────────────────────

    def traverse(self, node_id: str, depth: int = 2,
                 max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """从给定节点 BFS 遍历关联节点，返回关系列表

        逻辑迁自 graph_query.traverse：
        双向遍历（正向 + 反向边），访问激活（access_count++）。
        """
        conn = self._connect()
        try:
            cur = conn.cursor()

            visited = set()
            results = []
            frontier = [node_id]
            touched_ids = []

            for _ in range(depth):
                next_frontier = []
                for nid in frontier:
                    if nid in visited:
                        continue
                    visited.add(nid)

                    # 正向边：from_id = nid
                    cur.execute("""
                        SELECT e.relation_type, e.weight, e.source, e.graph_dim, e.strength,
                               n.id, n.content, n.tier, n.principle
                        FROM edges e
                        JOIN nodes n ON e.to_id = n.id
                        WHERE e.from_id = ? AND e.status = 'active'
                    """, (nid,))
                    for row in cur.fetchall():
                        rel, weight, source, graph_dim, strength, to_id, content, tier, principle = row
                        results.append({
                            "direction": "outgoing",
                            "from": nid, "to": to_id,
                            "relation": rel, "weight": weight,
                            "source": source, "graph_dim": graph_dim, "strength": strength,
                            "content": content, "tier": tier,
                            "principle": principle
                        })
                        if to_id not in visited:
                            next_frontier.append(to_id)
                        touched_ids.append(to_id)

                    # 反向边：to_id = nid
                    cur.execute("""
                        SELECT e.relation_type, e.weight, e.source, e.graph_dim, e.strength,
                               n.id, n.content, n.tier, n.principle
                        FROM edges e
                        JOIN nodes n ON e.from_id = n.id
                        WHERE e.to_id = ? AND e.status = 'active'
                    """, (nid,))
                    for row in cur.fetchall():
                        rel, weight, source, graph_dim, strength, from_id, content, tier, principle = row
                        results.append({
                            "direction": "incoming",
                            "from": from_id, "to": nid,
                            "relation": rel, "weight": weight,
                            "source": source, "graph_dim": graph_dim, "strength": strength,
                            "content": content, "tier": tier,
                            "principle": principle
                        })
                        if from_id not in visited:
                            next_frontier.append(from_id)
                        touched_ids.append(from_id)

                frontier = next_frontier

            # 访问激活
            if touched_ids:
                self._touch_nodes(touched_ids, conn)

            conn.commit()
            return results[:max_results]
        finally:
            conn.close()

    def search_by_vector(self, query: str, top: int = 5,
                         _touch: bool = True, layer: str = "L2",
                         **kwargs) -> List[Dict[str, Any]]:
        q_vec = self._embedder.encode(query)

        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, content, principle, vector, tier,
                       decay_score, task_type, project, abstract, overview
                FROM nodes
            """)
            rows = cur.fetchall()

            scored = []
            for row in rows:
                node_id, content, principle, vec_blob, tier, decay, task_type, project, abstract, overview = row
                if vec_blob is None or not self._matches_node_filters(task_type, project, None, kwargs):
                    continue
                vec = np.frombuffer(vec_blob, dtype=np.float32)
                sim = float(np.dot(q_vec, vec))
                scored.append((sim, node_id, content, principle, tier, decay,
                                task_type, project, abstract, overview))

            scored.sort(key=lambda x: x[0], reverse=True)

            if not scored:
                return []

            best_sim = scored[0][0]
            cutoff = best_sim * 0.55

            filtered = [s for s in scored if s[0] >= cutoff]

            seed_ids = [s[1] for s in filtered[:5]]

            chain_ids = set()
            chain_edges = []
            if seed_ids:
                placeholders = ",".join(["?"] * len(seed_ids))
                cur.execute(f"""
                    SELECT e.from_id, e.to_id, e.relation_type, e.weight
                    FROM edges e
                    WHERE (e.from_id IN ({placeholders}) OR e.to_id IN ({placeholders}))
                      AND e.status = 'active'
                      AND e.relation_type IN ('similar_to', 'is_a', 'caused', 'solves', 'evolved_from')
                """, seed_ids + seed_ids)
                for eid_from, eid_to, rel, w in cur.fetchall():
                    chain_edges.append((eid_from, eid_to, rel, w))
                    if eid_from not in seed_ids:
                        chain_ids.add(eid_from)
                    if eid_to not in seed_ids:
                        chain_ids.add(eid_to)

            chain_scored = []
            for nid in chain_ids:
                cur.execute("SELECT content, principle, vector, tier, decay_score, task_type, project, abstract, overview, context_tags FROM nodes WHERE id=?", (nid,))
                row = cur.fetchone()
                if not row or row[2] is None:
                    continue
                if not self._matches_node_filters(row[5], row[6], row[9], kwargs):
                    continue
                vec = np.frombuffer(row[2], dtype=np.float32)
                sim = float(np.dot(q_vec, vec))
                if sim >= cutoff:
                    chain_scored.append((sim, nid, row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8]))

            seen = {s[1] for s in filtered}
            for cs in chain_scored:
                if cs[1] not in seen:
                    filtered.append(cs)
                    seen.add(cs[1])

            filtered.sort(key=lambda x: x[0], reverse=True)

            results = []
            for sim, node_id, content, principle, tier, decay, task_type, project, abstract, overview in filtered[:top]:
                score = sim * max(0.1, decay)
                base = {"id": node_id, "similarity": round(sim, 3), "score": round(score, 3), "tier": tier}
                if layer == "L0":
                    base["abstract"] = abstract or content[:150]
                elif layer == "L1":
                    base["abstract"] = abstract or content[:150]
                    base["overview"] = overview or content[:600]
                    base["principle"] = principle
                else:
                    base["content"] = content
                    base["principle"] = principle
                    base["decay_score"] = round(decay, 3)
                    base["task_type"] = task_type
                    base["project"] = project
                results.append(base)

            if _touch and results:
                self._touch_nodes([r["id"] for r in results], conn)

            conn.commit()
            return results
        finally:
            conn.close()

    def search_by_keyword(self, query: str, top: int = 5,
                          _touch: bool = True, layer: str = "L2",
                          **kwargs) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT n.id, n.content, n.principle, n.tier, n.decay_score,
                       n.task_type, n.project, n.abstract, n.overview, n.context_tags
                FROM fts_nodes
                JOIN nodes n ON fts_nodes.id = n.id
                WHERE fts_nodes MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, top))
            rows = cur.fetchall()

            results = []
            for r in rows:
                if not self._matches_node_filters(r[5], r[6], r[9], kwargs):
                    continue
                base = {"id": r[0], "tier": r[3], "decay_score": round(r[4], 3)}
                if layer == "L0":
                    base["abstract"] = r[7] or r[1][:150]
                elif layer == "L1":
                    base["abstract"] = r[7] or r[1][:150]
                    base["overview"] = r[8] or r[1][:600]
                    base["principle"] = r[2]
                else:
                    base["content"] = r[1]
                    base["principle"] = r[2]
                    base["task_type"] = r[5]
                    base["project"] = r[6]
                results.append(base)

            if _touch and results:
                self._touch_nodes([r["id"] for r in results], conn)

            conn.commit()
            return results
        finally:
            conn.close()

    def search_hybrid(self, query: str, top: int = 5,
                      vector_weight: float = 0.7,
                      keyword_weight: float = 0.3,
                      layer: str = "L2",
                      **kwargs) -> List[Dict[str, Any]]:
        vec_results = self.search_by_vector(query, top=top * 2, _touch=False, layer=layer, **kwargs)
        try:
            kw_results = self.search_by_keyword(query, top=top * 2, _touch=False, layer=layer, **kwargs)
        except sqlite3.OperationalError:
            # FTS5 MATCH is picky about punctuation/operators. Keep hybrid search usable
            # by falling back to vector-only results when the keyword query is invalid.
            kw_results = []

        merged = {}
        for r in vec_results:
            nid = r['id']
            merged[nid] = dict(r)
            merged[nid]['vector_score'] = r.get('score', 0)
            merged[nid]['keyword_score'] = 0
            merged[nid]['in_vector'] = True
            merged[nid]['in_keyword'] = False
        for r in kw_results:
            nid = r['id']
            if nid in merged:
                merged[nid]['keyword_score'] = 1.0
                merged[nid]['in_keyword'] = True
            else:
                merged[nid] = dict(r)
                merged[nid]['vector_score'] = 0
                merged[nid]['keyword_score'] = 1.0
                merged[nid]['in_vector'] = False
                merged[nid]['in_keyword'] = True

        for item in merged.values():
            item['score'] = round(
                item['vector_score'] * vector_weight +
                item['keyword_score'] * keyword_weight, 3
            )

        results = sorted(merged.values(), key=lambda x: x['score'], reverse=True)
        top_results = results[:top]

        # 只对最终结果 touch 一次
        if top_results:
            conn = self._connect()
            try:
                self._touch_nodes([r['id'] for r in top_results], conn)
                conn.commit()
            finally:
                conn.close()

        return top_results

    def search_skills(self, query: str, top: int = 5,
                      min_similarity: float = 0.45,
                      statuses: Optional[List[str]] = None,
                      include_deprecated: bool = False) -> List[Dict[str, Any]]:
        """Search reusable skill nodes only.

        Skill nodes are sparse, so filtering generic search results can miss them.
        This searches within type='skill' directly and returns compact metadata for
        injection/use by agents.
        """
        q_vec = self._embedder.encode(query)
        conn = self._connect()
        try:
            cur = conn.cursor()
            conditions = ["n.type='skill'", "n.vector IS NOT NULL"]
            params = []
            if statuses:
                placeholders = ", ".join("?" for _ in statuses)
                conditions.append(f"sa.status IN ({placeholders})")
                params.extend(statuses)
            elif not include_deprecated:
                conditions.append("sa.status != 'deprecated'")
            where = " AND ".join(conditions)
            cur.execute(f"""
                SELECT n.id, n.content, n.principle, n.vector, n.tier, n.decay_score,
                       n.task_type, n.project, n.tags, n.abstract, n.overview,
                       n.confidence, n.verified_count,
                       sa.name, sa.slug, sa.status, sa.version,
                       sa.trigger_patterns, sa.preconditions, sa.procedure,
                       sa.verification, sa.failure_modes, sa.risk_level,
                       sa.review_status, sa.approval_mode, sa.inject_enabled,
                       sa.trial_enabled, sa.requires_feedback,
                       sa.mnemosyne_score, sa.darwin_score, sa.final_score,
                       sa.source_node_ids, sa.evidence_node_ids, sa.file_path,
                       sa.metadata
                FROM nodes n
                JOIN skill_artifacts sa ON sa.node_id = n.id
                WHERE {where}
            """, params)
            rows = cur.fetchall()

            scored = []
            for row in rows:
                vec = np.frombuffer(row[3], dtype=np.float32)
                sim = float(np.dot(q_vec, vec))
                if sim < min_similarity:
                    continue
                decay = row[5] or 0.8
                confidence = row[11] if row[11] is not None else 1.0
                score = sim * max(0.1, decay) * max(0.1, confidence)
                scored.append((score, sim, row))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, sim, row in scored[:top]:
                tags = _json_loads(row[8], [])
                metadata = _json_loads(row[34], {})

                cur.execute("""
                    SELECT relation_type, to_id, weight, source
                    FROM edges
                    WHERE from_id=? AND status='active'
                      AND relation_type IN ('crystallized_from', 'verified_by', 'supersedes')
                """, (row[0],))
                edges = [
                    {"relation_type": e[0], "to_id": e[1], "weight": e[2], "source": e[3]}
                    for e in cur.fetchall()
                ]

                results.append({
                    "id": row[0],
                    "type": "skill",
                    "similarity": round(sim, 3),
                    "score": round(score, 3),
                    "tier": row[4],
                    "abstract": row[9] or row[1][:150],
                    "overview": row[10] or row[1][:600],
                    "principle": row[2],
                    "task_type": row[6],
                    "project": row[7],
                    "tags": tags,
                    "metadata": metadata,
                    "confidence": row[11],
                    "verified_count": row[12],
                    "name": row[13],
                    "slug": row[14],
                    "status": row[15],
                    "version": row[16],
                    "trigger_patterns": _json_loads(row[17], []),
                    "preconditions": _json_loads(row[18], []),
                    "procedure": _json_loads(row[19], []),
                    "verification": row[20],
                    "failure_modes": _json_loads(row[21], []),
                    "risk_level": row[22],
                    "review_status": row[23],
                    "approval_mode": row[24],
                    "inject_enabled": bool(row[25]),
                    "trial_enabled": bool(row[26]),
                    "requires_feedback": bool(row[27]),
                    "mnemosyne_score": row[28],
                    "darwin_score": row[29],
                    "final_score": row[30],
                    "source_node_ids": _json_loads(row[31], []),
                    "evidence_node_ids": _json_loads(row[32], []),
                    "file_path": row[33],
                    "edges": edges,
                })

            if results:
                self._touch_nodes([r["id"] for r in results], conn)
                conn.commit()
            return results
        finally:
            conn.close()

    @staticmethod
    def _skill_trigger_matches_context(skill: Dict[str, Any], context: str) -> bool:
        """Conservative lexical gate for default/trial injection.

        Vector similarity finds candidates, but approved skills still need a
        visible trigger/precondition cue in the task context to avoid generic
        context pollution.
        """
        cues = (skill.get("trigger_patterns") or []) + (skill.get("preconditions") or [])
        cues = [str(cue).strip().lower() for cue in cues if str(cue).strip()]
        if not cues:
            return True
        text = (context or "").lower()
        stopwords = {
            "skill", "task", "test", "testing", "check", "use", "using", "with",
            "when", "then", "this", "that", "memory", "mcp", "opencode", "feedback",
            "context", "current", "generic", "behavior", "formal", "content", "data",
            "text", "display", "displays", "incorrectly", "corrupted", "mistaken",
            "terminal", "request", "body", "parse", "parsing", "json",
        }
        for cue in cues:
            if cue in text and not SQLiteStore._context_term_is_negated(text, cue):
                return True
            terms = re.findall(r"[a-z0-9_+#.-]{3,}|[\u4e00-\u9fff]{2,}", cue)
            terms = [term for term in terms if term not in stopwords]
            if any(term in text and not SQLiteStore._context_term_is_negated(text, term) for term in terms):
                return True
        return False

    @staticmethod
    def _context_term_is_negated(text: str, term: str) -> bool:
        idx = text.find(term)
        if idx < 0:
            return False
        prefix = text[max(0, idx - 24):idx]
        negators = (
            "not ", "no ", "without ", "unrelated to ", "not about ",
            "不涉及", "不包含", "不是", "无关", "非", "没有",
        )
        return any(neg in prefix for neg in negators)

    def inject_skills(self, context: str, max_chars: int = 800, top: int = 3,
                      min_similarity: float = 0.45, mode: str = "default") -> str:
        """Return a compact skill pointer block for the current context."""
        if mode == "experimental":
            statuses = ["draft", "evolved", "approved"]
        elif mode == "trial":
            statuses = ["approved", "evolved"]
        else:
            statuses = ["approved"]
        skills = self.search_skills(context, top=top * 3, min_similarity=min_similarity,
                                    statuses=statuses)
        gated = []
        for skill in skills:
            status = skill.get("status")
            if mode in {"default", "trial"} and not self._skill_trigger_matches_context(skill, context):
                continue
            if status == "approved":
                if skill.get("inject_enabled") and self._has_active_edge(skill["id"], "verified_by"):
                    skill["used_as"] = "approved"
                    gated.append(skill)
            elif mode == "trial" and status == "evolved":
                if (skill.get("risk_level") == "low" and skill.get("trial_enabled")
                        and skill.get("requires_feedback")):
                    skill["used_as"] = "trial"
                    skill["feedback_required"] = True
                    gated.append(skill)
            elif mode == "experimental" and status in ("draft", "evolved"):
                skill["used_as"] = "experimental"
                gated.append(skill)
            if len(gated) >= top:
                break
        skills = gated
        if not skills:
            return ""

        lines = ["[Skills]"]
        for skill in skills:
            triggers = skill.get("trigger_patterns") or []
            verification = skill.get("verification") or ""
            evidence = skill.get("source_node_ids") or []
            title = skill.get("name") or (skill.get("abstract") or "").split("\n", 1)[0]
            if title.lower().startswith("skill:"):
                title = title.split(":", 1)[1].strip()
            line = f"- {title or skill['id'][:8]} ({skill['id'][:8]}, status={skill.get('status')}, used_as={skill.get('used_as')}, score={skill['score']})"
            if triggers:
                line += f" trigger={'; '.join(str(t) for t in triggers[:2])}"
            if verification:
                line += f" verify={str(verification)[:80]}"
            if evidence:
                line += f" evidence={', '.join(str(e)[:8] for e in evidence[:3])}"
            if skill.get("feedback_required"):
                line += " feedback_required=true"
            lines.append(line)

        output = "\n".join(lines)
        return output[:max_chars]

    def sync_skill_node_content(self, node_id: str, name: str,
                                trigger_patterns: List[str] = None,
                                procedure: List[str] = None,
                                verification: str = None) -> bool:
        content = self._make_skill_content(name, trigger_patterns or [], procedure or [], verification)
        vector = self._embedder.encode(content).astype(np.float32).tobytes()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE nodes
                SET content=?, principle=?, vector=?, abstract=?, overview=?, updated_at=?
                WHERE id=? AND type='skill'
            """, (
                content, name, vector, content[:self._MAX_ABSTRACT], content[:self._MAX_OVERVIEW],
                _now_iso(), node_id,
            ))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _markdown_list(items: list, numbered: bool = False) -> str:
        if not items:
            return "- None"
        lines = []
        for idx, item in enumerate(items, 1):
            prefix = f"{idx}." if numbered else "-"
            text = re.sub(r"^\s*\d+[.)]\s+", "", str(item)) if numbered else str(item)
            lines.append(f"{prefix} {text}")
        return "\n".join(lines)

    def render_skill_markdown(self, artifact: Dict[str, Any]) -> str:
        status = artifact.get("status") or "draft"
        lines = [f"# {artifact.get('name') or artifact.get('node_id')}", ""]
        if status == "deprecated":
            lines.extend([
                "> Status: deprecated",
                f"> Deprecated at: {artifact.get('deprecated_at') or 'unknown'}",
                "",
            ])
        lines.extend([
            f"> Status: {status}",
            f"> Version: {artifact.get('version') or '0.1.0'}",
            f"> Risk: {artifact.get('risk_level') or 'medium'}",
            f"> Node: {artifact.get('node_id')}",
            "",
            "## Triggers",
            self._markdown_list(artifact.get("trigger_patterns") or []),
            "",
            "## Preconditions",
            self._markdown_list(artifact.get("preconditions") or []),
            "",
            "## Procedure",
            self._markdown_list(artifact.get("procedure") or [], numbered=True),
            "",
            "## Verification",
            artifact.get("verification") or "None",
            "",
            "## Failure Modes",
            self._markdown_list(artifact.get("failure_modes") or []),
            "",
            "## Evidence",
            "### Source Nodes",
            self._markdown_list(artifact.get("source_node_ids") or []),
            "",
            "### Verification Nodes",
            self._markdown_list(artifact.get("evidence_node_ids") or []),
            "",
        ])
        metadata = artifact.get("metadata") or {}
        if metadata:
            lines.extend([
                "## Metadata",
                "```json",
                json.dumps(metadata, ensure_ascii=False, indent=2),
                "```",
                "",
            ])
        return "\n".join(lines)

    def sync_skill_file(self, node_id: str) -> Dict[str, Any]:
        artifact = self.get_skill_artifact(node_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {node_id}")
        slug = artifact.get("slug") or self._unique_skill_slug(_slugify(artifact.get("name") or node_id))
        if not artifact.get("slug"):
            self.update_skill_artifact(node_id, slug=slug)
            artifact["slug"] = slug
        rel_path = Path("skills") / slug / "SKILL.md"
        abs_path = _SKILLS_DIR / slug / "SKILL.md"
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = self.render_skill_markdown(artifact)
        abs_path.write_text(markdown, encoding="utf-8", newline="\n")
        file_hash = self._hash_text(markdown)
        synced_at = _now_iso()
        self.update_skill_artifact(
            node_id,
            file_path=str(rel_path).replace("\\", "/"),
            file_hash=file_hash,
            file_synced_at=synced_at,
        )
        return {
            "node_id": node_id,
            "file_path": str(rel_path).replace("\\", "/"),
            "absolute_path": str(abs_path),
            "file_hash": file_hash,
            "file_synced_at": synced_at,
        }

    def sync_skill_files(self, statuses: Optional[List[str]] = None) -> Dict[str, Any]:
        statuses = statuses or ["draft", "evolved", "approved"]
        artifacts = self.list_skill_artifacts(statuses=statuses)
        synced = []
        for artifact in artifacts:
            synced.append(self.sync_skill_file(artifact["node_id"]))
        return {"synced": len(synced), "files": synced}

    def score_skill_dry_run(self, artifact: Dict[str, Any], markdown: str = None) -> Dict[str, Any]:
        markdown = markdown if markdown is not None else self.render_skill_markdown(artifact)
        trigger_count = len(artifact.get("trigger_patterns") or [])
        procedure_count = len(artifact.get("procedure") or [])
        failure_count = len(artifact.get("failure_modes") or [])
        source_count = len(artifact.get("source_node_ids") or [])
        evidence_count = len(artifact.get("evidence_node_ids") or [])

        procedure_text = "\n".join(str(step) for step in artifact.get("procedure") or [])
        frontmatter = 8 if artifact.get("name") and trigger_count else 6 if artifact.get("name") else 3
        workflow = 9 if procedure_count >= 5 else 8 if procedure_count >= 3 else 6 if procedure_count >= 2 else 3
        boundary = 8 if failure_count >= 2 else 6 if failure_count == 1 else 3
        checkpoint = 7 if "ask" in markdown.lower() or "确认" in markdown else 5 if artifact.get("preconditions") else 3
        specificity = 9 if len(procedure_text) >= 280 and artifact.get("verification") else 7 if procedure_count >= 3 else 4
        resources = 9 if source_count >= 3 and evidence_count >= 1 else 7 if source_count >= 2 else 4 if source_count else 2
        architecture = 8 if markdown.count("## ") >= 5 and artifact.get("verification") else 7 if markdown.count("## ") >= 4 else 5

        # Darwin's rubric is intentionally conservative: static structure can
        # never prove functional value. Dimension 8 stays neutral until live
        # baseline-vs-skill evaluation supplies real evidence.
        measured_effect = 5.0
        structure_points = (
            frontmatter * 8 + workflow * 15 + boundary * 10 + checkpoint * 7 +
            specificity * 15 + resources * 5 + architecture * 15
        ) / 10
        effect_points = measured_effect * 25 / 10
        darwin_score = round(min(100, structure_points + effect_points), 1)
        mnemosyne_score = round(min(100, (
            min(100, source_count * 25 + evidence_count * 20) * 0.35 +
            (80 if 1 <= trigger_count <= 6 else 40) * 0.20 +
            (80 if artifact.get("verification") else 40) * 0.20 +
            (75 if artifact.get("risk_level") in RISK_LEVELS else 40) * 0.10 +
            measured_effect * 10 * 0.15
        )), 1)
        final_score = round(0.5 * mnemosyne_score + 0.5 * darwin_score, 1)
        return {
            "mnemosyne_score": mnemosyne_score,
            "darwin_score": darwin_score,
            "final_score": final_score,
            "breakdown": {
                "frontmatter": frontmatter,
                "workflow": workflow,
                "boundary": boundary,
                "checkpoint": checkpoint,
                "specificity": specificity,
                "resources": resources,
                "architecture": architecture,
                "measured_effect": measured_effect,
                "structure_points": round(structure_points, 1),
                "effect_points": round(effect_points, 1),
                "trigger_count": trigger_count,
                "procedure_count": procedure_count,
                "failure_count": failure_count,
                "source_count": source_count,
                "evidence_count": evidence_count,
                "markdown_chars": len(markdown),
            },
        }

    def record_skill_verification_evidence(self, skill_id: str, darwin_result: Dict[str, Any],
                                           prompt_results: List[Dict[str, Any]] = None) -> Optional[str]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        if not darwin_result.get("passed"):
            return None
        if darwin_result.get("eval_mode") in {"dry_run", "replay_smoke"}:
            return None
        if (darwin_result.get("live_test_delta") or 0) <= 0:
            return None
        if darwin_result.get("regression_count"):
            return None

        prompt_results = prompt_results or darwin_result.get("prompt_results") or []
        prompt_ids = {str(item.get("prompt_id") or "") for item in prompt_results}
        real_prompts = self.list_real_skill_test_prompts(skill_id)
        prompt_metadata_by_id = {str(item.get("prompt_id") or ""): item.get("metadata") or {} for item in real_prompts}
        real_prompt_ids = set(prompt_metadata_by_id)
        if not prompt_ids or not prompt_ids.intersection(real_prompt_ids):
            return None
        grounded_prompt_results = []
        for item in prompt_results:
            merged = dict(item)
            prompt_id = str(item.get("prompt_id") or "")
            if prompt_id in prompt_metadata_by_id:
                merged["prompt_metadata"] = prompt_metadata_by_id[prompt_id]
            grounded_prompt_results.append(merged)
        content = (
            f"Darwin full-test verification for skill {skill_id}\n"
            f"Skill: {artifact.get('name') or skill_id}\n"
            f"Darwin score: {darwin_result.get('darwin_score')}\n"
            f"Average baseline score: {darwin_result.get('baseline_score')}\n"
            f"Average with-skill score: {darwin_result.get('with_skill_score')}\n"
            f"Average live delta: {darwin_result.get('live_test_delta')}\n"
            f"Regression count: {darwin_result.get('regression_count')}\n"
            f"Prompt count: {len(prompt_results)}"
        )
        evidence_id = self.add_node(
            content=content,
            node_type="skill_feedback",
            task_type="skill_memory",
            tags=["skill_verification", "darwin_full_test", "verified_by"],
            principle="Darwin full-test evidence should count as skill verification",
            context_tags=["skill_memory", "darwin", "full_test", skill_id],
            metadata={
                "skill_id": skill_id,
                "eval_mode": darwin_result.get("eval_mode"),
                "darwin_score": darwin_result.get("darwin_score"),
                "baseline_score": darwin_result.get("baseline_score"),
                "with_skill_score": darwin_result.get("with_skill_score"),
                "live_test_delta": darwin_result.get("live_test_delta"),
                "regression_count": darwin_result.get("regression_count"),
                "prompt_results": grounded_prompt_results,
            },
        )
        self.add_edge(skill_id, evidence_id, "verified_by", weight=0.85, source="darwin_full_test")
        evidence_ids = list(artifact.get("evidence_node_ids") or [])
        if evidence_id not in evidence_ids:
            evidence_ids.append(evidence_id)
            self.update_skill_artifact(skill_id, evidence_node_ids=evidence_ids)
        return evidence_id

    def record_skill_evolution_run(self, skill_node_id: str, old_score: float = None,
                                   new_score: float = None, mnemosyne_score: float = None,
                                   darwin_score: float = None, status: str = "dry_run",
                                   dimension: str = "m4", note: str = "",
                                   eval_mode: str = "dry_run",
                                   metadata: Dict[str, Any] = None) -> str:
        run_id = str(uuid.uuid4())
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO skill_evolution_runs(
                    id, skill_node_id, old_score, new_score, mnemosyne_score,
                    darwin_score, status, dimension, note, eval_mode, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, skill_node_id, old_score, new_score, mnemosyne_score,
                darwin_score, status, dimension, note, eval_mode, _now_iso(),
                json.dumps(metadata or {}, ensure_ascii=False),
            ))
            conn.commit()
            return run_id
        finally:
            conn.close()

    def add_skill_test_prompt(self, skill_id: str, prompt_id: str, prompt: str,
                              expected: str = "", tags: List[str] = None,
                              status: str = "active", approved_by: str = None,
                              metadata: Dict[str, Any] = None) -> str:
        if not self.get_skill_artifact(skill_id):
            raise ValueError(f"skill artifact not found: {skill_id}")
        self._ensure_skill_test_prompt_metadata_column()
        row_id = str(uuid.uuid4())
        now = _now_iso()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO skill_test_prompts(
                    id, skill_id, prompt_id, prompt, expected, tags, metadata, status,
                    approved_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_id, prompt_id) DO UPDATE SET
                    prompt=excluded.prompt,
                    expected=excluded.expected,
                    tags=excluded.tags,
                    metadata=excluded.metadata,
                    status=excluded.status,
                    approved_by=excluded.approved_by,
                    updated_at=excluded.updated_at
            """, (
                row_id, skill_id, prompt_id, prompt, expected,
                _json_dumps(tags or []), json.dumps(metadata or {}, ensure_ascii=False),
                status, approved_by, now, now,
            ))
            conn.commit()
            row = cur.execute(
                "SELECT id FROM skill_test_prompts WHERE skill_id=? AND prompt_id=?",
                (skill_id, prompt_id),
            ).fetchone()
            return row[0]
        finally:
            conn.close()

    def _ensure_skill_test_prompt_metadata_column(self) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cols = {row[1] for row in cur.execute("PRAGMA table_info(skill_test_prompts)").fetchall()}
            if "metadata" not in cols:
                cur.execute("ALTER TABLE skill_test_prompts ADD COLUMN metadata TEXT DEFAULT '{}'")
                conn.commit()
        finally:
            conn.close()

    def list_skill_test_prompts(self, skill_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        self._ensure_skill_test_prompt_metadata_column()
        conn = self._connect()
        try:
            cur = conn.cursor()
            sql = "SELECT * FROM skill_test_prompts WHERE skill_id=?"
            params = [skill_id]
            if active_only:
                sql += " AND status='active'"
            sql += " ORDER BY created_at, prompt_id"
            cur.execute(sql, params)
            keys = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                item = dict(zip(keys, row))
                item["tags"] = _json_loads(item.get("tags"), [])
                item["metadata"] = _json_loads(item.get("metadata"), {})
                rows.append(item)
            return rows
        finally:
            conn.close()

    @staticmethod
    def is_real_skill_test_prompt(prompt: Dict[str, Any]) -> bool:
        tags = prompt.get("tags") or []
        if isinstance(tags, str):
            tags = _json_loads(tags, [])
        if prompt.get("prompt_id") == "auto-smoke" or "auto" in tags or "smoke" in tags:
            return False
        if (prompt.get("status") or "active") != "active":
            return False
        text = (prompt.get("prompt") or "").strip()
        expected = (prompt.get("expected") or "").strip()
        if not text or not expected:
            return False
        metadata = prompt.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = _json_loads(metadata, {})
        if "llm_generated" in tags and not metadata.get("grounding_node_ids"):
            return False
        generic = "use the skill" in text.lower() and "matching task" in text.lower()
        return not generic

    def list_real_skill_test_prompts(self, skill_id: str) -> List[Dict[str, Any]]:
        return [item for item in self.list_skill_test_prompts(skill_id) if self.is_real_skill_test_prompt(item)]

    def sync_skill_test_prompts_file(self, skill_id: str) -> Dict[str, Any]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        prompts = self.list_skill_test_prompts(skill_id, active_only=False)
        slug = artifact.get("slug") or _slugify(artifact.get("name") or skill_id)
        rel_path = Path("skills") / slug / "test-prompts.json"
        abs_path = _SKILLS_DIR / slug / "test-prompts.json"
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": item.get("prompt_id"),
                "prompt": item.get("prompt"),
                "expected": item.get("expected") or "",
                "tags": item.get("tags") or [],
                "metadata": item.get("metadata") or {},
                "status": item.get("status") or "active",
            }
            for item in prompts
        ]
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        abs_path.write_text(text, encoding="utf-8", newline="\n")
        return {
            "skill_id": skill_id,
            "file_path": str(rel_path).replace("\\", "/"),
            "absolute_path": str(abs_path),
            "count": len(payload),
            "file_hash": self._hash_text(text),
        }

    def record_skill_eval_run(self, skill_id: str, prompt_id: str = None,
                              round: int = 0, eval_mode: str = "dry_run",
                              baseline_output: str = None,
                              with_skill_output: str = None,
                              judge_output: Dict[str, Any] = None,
                              baseline_score: float = None,
                              with_skill_score: float = None,
                              live_test_delta: float = None,
                              regression: bool = False,
                              darwin_score: float = None,
                              mnemosyne_score: float = None,
                              decision: str = None,
                              decision_reason: str = None,
                              file_hash_before: str = None,
                              file_hash_after: str = None,
                              kept: bool = False,
                              reverted: bool = False) -> str:
        if not self.get_skill_artifact(skill_id):
            raise ValueError(f"skill artifact not found: {skill_id}")
        run_id = str(uuid.uuid4())
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO skill_eval_runs(
                    id, skill_id, prompt_id, round, eval_mode, baseline_output,
                    with_skill_output, judge_output, baseline_score, with_skill_score,
                    live_test_delta, regression, darwin_score, mnemosyne_score,
                    decision, decision_reason, file_hash_before, file_hash_after,
                    kept, reverted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, skill_id, prompt_id, round, eval_mode, baseline_output,
                with_skill_output, json.dumps(judge_output or {}, ensure_ascii=False),
                baseline_score, with_skill_score, live_test_delta, int(bool(regression)),
                darwin_score, mnemosyne_score, decision, decision_reason,
                file_hash_before, file_hash_after, int(bool(kept)), int(bool(reverted)), _now_iso(),
            ))
            conn.commit()
            return run_id
        finally:
            conn.close()

    def run_skill_darwin_evaluation(self, skill_id: str, runner: Any, judge: Any,
                                    round_no: int = 0, eval_mode: str = "full_test") -> Dict[str, Any]:
        from .skill_evolution import SkillEvolutionRunner
        return SkillEvolutionRunner(self, runner, judge).run(skill_id, round_no=round_no, eval_mode=eval_mode)

    def list_skill_eval_runs(self, skill_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM skill_eval_runs WHERE skill_id=? ORDER BY created_at", (skill_id,))
            keys = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                item = dict(zip(keys, row))
                item["judge_output"] = _json_loads(item.get("judge_output"), {})
                rows.append(item)
            return rows
        finally:
            conn.close()

    def update_skill_eval_run(self, run_id: str, **fields) -> bool:
        allowed = {
            "darwin_score", "mnemosyne_score", "decision", "decision_reason",
            "file_hash_before", "file_hash_after", "kept", "reverted",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [run_id]
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE skill_eval_runs SET {sets} WHERE id=?", values)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def score_skill_mnemosyne(self, skill_id: str, persist: bool = False) -> Dict[str, Any]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")

        source_ids = artifact.get("source_node_ids") or []
        evidence_ids = artifact.get("evidence_node_ids") or []
        trigger_count = len(artifact.get("trigger_patterns") or [])
        verified_edges = self._count_active_edges(skill_id, "verified_by")
        fails_edges = self._count_active_edges(skill_id, "fails_on")
        revision_edges = self._count_active_edges(skill_id, "needs_revision")
        trial_count = artifact.get("trial_count") or 0
        success_count = artifact.get("trial_success_count") or 0
        failure_count = artifact.get("trial_failure_count") or 0
        risk_level = artifact.get("risk_level") or "medium"

        evidence = min(100, len(source_ids) * 30 + len(evidence_ids) * 20)
        cluster_quality = min(100, len(source_ids) * 25)
        verification = min(100, verified_edges * 60 + success_count * 15)
        trigger_precision = 80 if 1 <= trigger_count <= 3 else 65 if 4 <= trigger_count <= 6 else 0
        if trial_count == 0 and verified_edges:
            feedback = 75
        else:
            feedback = 50 if trial_count == 0 else max(0, min(100, 50 + success_count * 20 - failure_count * 35))
        safety = {"low": 100, "medium": 75, "high": 35}.get(risk_level, 40)

        score = round(
            evidence * 0.25 + cluster_quality * 0.20 + verification * 0.20 +
            trigger_precision * 0.15 + feedback * 0.10 + safety * 0.10,
            1,
        )
        hard_failures = []
        if not source_ids:
            hard_failures.append("missing_source_evidence")
            score = min(score, 40)
        if not evidence_ids:
            hard_failures.append("missing_evidence_nodes")
            score = min(score, 60)
        if risk_level == "high" and artifact.get("approval_mode") != "manual_override":
            hard_failures.append("high_risk_requires_manual_override")
        if trigger_count == 0 or trigger_count > 8:
            hard_failures.append("unsafe_trigger_precision")
        if fails_edges:
            hard_failures.append("unresolved_fails_on")
        if revision_edges or artifact.get("needs_revision"):
            score = min(score, 75)

        passed = score >= 80 and not hard_failures
        result = {
            "mnemosyne_score": round(score, 1),
            "passed": passed,
            "hard_failures": hard_failures,
            "breakdown": {
                "evidence": evidence,
                "cluster_quality": cluster_quality,
                "verification": verification,
                "trigger_precision": trigger_precision,
                "feedback": feedback,
                "safety": safety,
                "source_count": len(source_ids),
                "evidence_count": len(evidence_ids),
                "verified_edges": verified_edges,
                "fails_edges": fails_edges,
                "revision_edges": revision_edges,
            },
        }
        if persist:
            self.update_skill_artifact(skill_id, mnemosyne_score=result["mnemosyne_score"])
        return result

    def decide_skill_evolution(self, skill_id: str, darwin_result: Dict[str, Any] = None,
                               mnemosyne_result: Dict[str, Any] = None) -> Dict[str, Any]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        darwin_result = darwin_result or {}
        mnemosyne_result = mnemosyne_result or self.score_skill_mnemosyne(skill_id)
        darwin_score = darwin_result.get("darwin_score") or artifact.get("latest_darwin_score") or artifact.get("darwin_score") or 0
        mnemosyne_score = mnemosyne_result.get("mnemosyne_score") or 0
        live_delta = darwin_result.get("live_test_delta")
        regression_count = darwin_result.get("regression_count", 0)
        eval_mode = darwin_result.get("eval_mode", "unknown")
        prompt_results = darwin_result.get("prompt_results") or []
        prompt_ids = {str(item.get("prompt_id") or "") for item in prompt_results}
        real_prompt_ids = {str(item.get("prompt_id") or "") for item in self.list_real_skill_test_prompts(skill_id)}
        has_real_prompt_evidence = bool(prompt_ids.intersection(real_prompt_ids))
        reasons = []

        darwin_passed = bool(darwin_result.get("passed"))
        if eval_mode in {"dry_run", "replay_smoke"}:
            darwin_passed = False
            reasons.append(f"{eval_mode}_cannot_evolve")
        if eval_mode == "full_test" and not has_real_prompt_evidence:
            darwin_passed = False
            reasons.append("missing_real_test_prompt")
        if live_delta is None or live_delta <= 0:
            darwin_passed = False
            reasons.append("missing_positive_live_test_delta")
        if regression_count:
            darwin_passed = False
            reasons.append("regression_detected")
        if float(darwin_score) < 80:
            darwin_passed = False
            reasons.append("darwin_score_below_threshold")

        mnemosyne_passed = bool(mnemosyne_result.get("passed"))
        if not mnemosyne_passed:
            reasons.extend(mnemosyne_result.get("hard_failures") or ["mnemosyne_score_below_threshold"])

        if darwin_passed and mnemosyne_passed:
            decision = "evolved"
            decision_reason = "Darwin live tests improved behavior and Mnemosyne graph governance passed."
        elif artifact.get("status") == "deprecated":
            decision = "deprecated"
            decision_reason = "; ".join(dict.fromkeys(reasons)) or "deprecated skill cannot re-evolve automatically"
        else:
            decision = "needs_revision"
            decision_reason = "; ".join(dict.fromkeys(reasons)) or "bilateral pass incomplete"

        if eval_mode == "full_test" and has_real_prompt_evidence:
            updates = {
                "status": decision if decision in SKILL_STATUSES else artifact.get("status"),
                "review_status": decision,
                "latest_eval_mode": eval_mode,
                "latest_decision": decision,
                "latest_decision_reason": decision_reason,
                "darwin_score": darwin_score,
                "mnemosyne_score": mnemosyne_score,
                "final_score": round(0.5 * float(darwin_score) + 0.5 * float(mnemosyne_score), 1),
                "latest_darwin_score": darwin_score,
                "latest_mnemosyne_score": mnemosyne_score,
                "latest_live_test_delta": live_delta,
            }
        else:
            metadata = artifact.get("metadata") or {}
            metadata["latest_non_governing_eval"] = {
                "eval_mode": eval_mode,
                "decision": decision,
                "decision_reason": decision_reason,
                "darwin_score": darwin_score,
                "mnemosyne_score": mnemosyne_score,
                "live_test_delta": live_delta,
                "recorded_at": _now_iso(),
            }
            updates = {"metadata": metadata}
        self.update_skill_artifact(skill_id, **updates)
        return {
            "skill_id": skill_id,
            "decision": decision,
            "decision_reason": decision_reason,
            "darwin_passed": darwin_passed,
            "mnemosyne_passed": mnemosyne_passed,
            "darwin_score": darwin_score,
            "mnemosyne_score": mnemosyne_score,
            "live_test_delta": live_delta,
        }

    def approve_skill(self, node_id: str, approval_mode: str = "manual") -> Dict[str, Any]:
        artifact = self.get_skill_artifact(node_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {node_id}")
        if artifact.get("status") == "deprecated":
            raise ValueError("deprecated skill cannot be approved")
        if artifact.get("status") != "evolved" and approval_mode != "manual_override":
            raise ValueError("skill must be evolved before approval unless approval_mode='manual_override'")
        if not self._has_active_edge(node_id, "verified_by"):
            raise ValueError("skill must have at least one verified_by edge before approval")
        file_path = artifact.get("file_path")
        file_hash = artifact.get("file_hash")
        if not file_path or not file_hash:
            raise ValueError("skill must have a synced SKILL.md mirror before approval")
        abs_path = _PROJECT_ROOT / file_path
        if not abs_path.exists():
            raise ValueError("synced SKILL.md mirror is missing")
        actual_hash = self._hash_text(abs_path.read_text(encoding="utf-8"))
        if actual_hash != file_hash:
            raise ValueError("SKILL.md file hash does not match DB record")
        if approval_mode != "manual_override":
            if (artifact.get("latest_eval_mode") or "") == "dry_run":
                raise ValueError("dry-run evaluation cannot be approved")
            if (artifact.get("latest_live_test_delta") or 0) <= 0:
                raise ValueError("skill needs positive live_test_delta before approval")
            if (artifact.get("latest_darwin_score") or artifact.get("darwin_score") or 0) < 80:
                raise ValueError("skill needs passing Darwin score before approval")
            if (artifact.get("latest_mnemosyne_score") or artifact.get("mnemosyne_score") or 0) < 80:
                raise ValueError("skill needs passing Mnemosyne score before approval")
        inject_enabled = 0 if approval_mode == "auto_experimental" else 1
        self.update_skill_artifact(
            node_id,
            status="approved",
            review_status="approved",
            approval_mode=approval_mode,
            inject_enabled=inject_enabled,
            trial_enabled=0,
            requires_feedback=0,
            approved_at=_now_iso(),
        )
        sync_info = self.sync_skill_file(node_id)
        return {"skill_id": node_id, "status": "approved", "inject_enabled": bool(inject_enabled), "file": sync_info}

    @staticmethod
    def _normalize_skill_feedback_outcome(rating: str = None, outcome: str = None) -> tuple:
        rating_to_outcome = {
            "helpful": "success",
            "partially_useful": "partial",
            "not_helpful": "miss",
            "misleading": "misleading",
        }
        outcome_to_rating = {
            "success": "helpful",
            "partial": "partially_useful",
            "miss": "not_helpful",
            "misleading": "misleading",
            "trigger_mismatch": "not_helpful",
        }
        valid_outcomes = {"success", "partial", "miss", "misleading", "trigger_mismatch"}
        if outcome is not None:
            if outcome not in valid_outcomes:
                raise ValueError(f"invalid outcome: {outcome}")
            return outcome, rating if rating is not None else outcome_to_rating.get(outcome)
        if rating not in rating_to_outcome:
            raise ValueError(f"invalid rating: {rating}")
        return rating_to_outcome[rating], rating

    @staticmethod
    def _skill_feedback_relation_and_weight(outcome: str) -> tuple:
        if outcome == "success":
            return "verified_by", 0.7
        if outcome == "partial":
            return "needs_revision", 0.7
        if outcome == "miss":
            return "fails_on", 0.7
        if outcome == "misleading":
            return "fails_on", 0.9
        if outcome == "trigger_mismatch":
            return "needs_revision", 0.8
        raise ValueError(f"invalid outcome: {outcome}")

    def skill_feedback(self, skill_id: str, rating: str = None, note: str = "",
                       task_context: str = "", used_as: str = "trial",
                       verification_result: str = "", outcome: str = None,
                       create_test_prompt: bool = False, expected: str = "",
                       prompt_tags: List[str] = None) -> Dict[str, Any]:
        if used_as not in {"approved", "trial", "experimental"}:
            raise ValueError(f"invalid used_as: {used_as}")
        outcome, rating = self._normalize_skill_feedback_outcome(rating=rating, outcome=outcome)
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        if create_test_prompt and not task_context:
            create_test_prompt = False

        content = (
            f"Skill feedback for {skill_id}\n"
            f"Rating: {rating}\n"
            f"Outcome: {outcome}\n"
            f"Used as: {used_as}\n"
            f"Task context: {task_context}\n"
            f"Verification result: {verification_result}\n"
            f"Note: {note}"
        )
        feedback_id = self.add_node(
            content=content,
            node_type="skill_feedback",
            task_type="skill_feedback",
            tags=["skill_feedback", rating, used_as],
            principle=f"Skill feedback: {outcome}",
            context_tags=["skill_feedback", skill_id, outcome, used_as],
            metadata={
                "skill_id": skill_id,
                "rating": rating,
                "outcome": outcome,
                "used_as": used_as,
                "task_context": task_context,
                "verification_result": verification_result,
                "note": note,
            },
        )
        relation, weight = self._skill_feedback_relation_and_weight(outcome)
        self.add_edge(skill_id, feedback_id, relation, weight=weight, source="skill_feedback")

        usage_id = str(uuid.uuid4())
        created_at = _now_iso()
        should_count_trial = used_as == "trial"
        audit_required = int(outcome != "success")
        created_prompt_id = None
        if create_test_prompt:
            prompt_id = f"usage-{feedback_id[:8]}"
            prompt_tags = list(prompt_tags or [])
            base_tags = ["usage_feedback", f"outcome:{outcome}"]
            if outcome in {"miss", "misleading", "trigger_mismatch"}:
                base_tags.append("regression")
            tags = base_tags + [tag for tag in prompt_tags if tag not in base_tags]
            created_prompt_id = self.add_skill_test_prompt(
                skill_id,
                prompt_id,
                task_context,
                expected=expected or verification_result,
                tags=tags,
            )
            self.sync_skill_test_prompts_file(skill_id)

        metadata = artifact.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = _json_loads(metadata, {})
        usage_loop = metadata.get("usage_loop") or {}
        if not isinstance(usage_loop, dict):
            usage_loop = {}
        usage_loop.setdefault("audit_failures", 0)
        usage_loop.setdefault("trigger_mismatch_count", 0)
        usage_loop["last_audit_at"] = created_at
        if outcome == "trigger_mismatch":
            usage_loop["trigger_mismatch_count"] = int(usage_loop.get("trigger_mismatch_count") or 0) + 1
        if outcome in {"miss", "misleading", "trigger_mismatch"}:
            usage_loop["audit_failures"] = int(usage_loop.get("audit_failures") or 0) + 1
            if created_prompt_id:
                usage_loop["last_failure_prompt_id"] = created_prompt_id
        metadata["usage_loop"] = usage_loop

        trial_count = artifact.get("trial_count") or 0
        trial_success = artifact.get("trial_success_count") or 0
        trial_failure = artifact.get("trial_failure_count") or 0
        updates = {"metadata": metadata}
        if should_count_trial:
            trial_count += 1
            updates["trial_count"] = trial_count
            updates["last_trial_at"] = created_at
            if outcome == "success":
                trial_success += 1
                updates["trial_success_count"] = trial_success
                if trial_success >= 3 and trial_failure == 0:
                    updates["promotion_candidate"] = 1
            elif outcome in {"miss", "misleading", "trigger_mismatch"}:
                trial_failure += 1
                updates["trial_failure_count"] = trial_failure
                updates["needs_revision"] = 1
                if outcome == "misleading":
                    updates["trial_enabled"] = 0
            else:
                updates["needs_revision"] = 1
        else:
            if outcome != "success":
                updates["needs_revision"] = 1
            if outcome == "misleading":
                updates["trial_enabled"] = 0

        self.update_skill_artifact(skill_id, **updates)

        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO skill_usage_feedback(
                    id, skill_id, feedback_node_id, task_context, used_as, outcome,
                    rating, verification_result, note, created_prompt_id, audit_required, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage_id, skill_id, feedback_id, task_context, used_as, outcome,
                rating, verification_result, note, created_prompt_id, audit_required, created_at,
            ))
            conn.commit()
        finally:
            conn.close()

        return {
            "skill_id": skill_id,
            "feedback_id": feedback_id,
            "usage_feedback_id": usage_id,
            "rating": rating,
            "outcome": outcome,
            "relation": relation,
            "weight": weight,
            "created_prompt_id": created_prompt_id,
            "updates": updates,
        }

    def should_audit_skill(self, skill_id: str, trigger: str = "sampling") -> Dict[str, Any]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        metadata = artifact.get("metadata") or {}
        usage_loop = metadata.get("usage_loop") or {}
        status = artifact.get("status")
        risk_level = artifact.get("risk_level") or "medium"
        audit_failures = int(usage_loop.get("audit_failures") or 0)
        trigger_mismatches = int(usage_loop.get("trigger_mismatch_count") or 0)
        trial_failures = int(artifact.get("trial_failure_count") or 0)
        reasons = []

        if status not in {"approved", "evolved"}:
            return {"audit_required": False, "reason": "status_not_auditable", "priority": "none", "reasons": []}
        if trigger == "failure":
            reasons.append("failure_triggered")
        if risk_level == "high":
            reasons.append("high_risk")
        if audit_failures:
            reasons.append("usage_failures_present")
        if trigger_mismatches:
            reasons.append("trigger_mismatch_present")
        if trial_failures and status == "evolved":
            reasons.append("trial_failures_present")
        if (artifact.get("latest_live_test_delta") or 0) < 0:
            reasons.append("negative_live_test_delta")
        if artifact.get("latest_decision") == "needs_revision" or artifact.get("needs_revision"):
            reasons.append("needs_revision_flagged")

        if not reasons and trigger == "sampling" and status == "approved" and risk_level == "medium":
            reasons.append("medium_risk_sampling")

        priority = "none"
        if reasons:
            priority = "high" if any(r in reasons for r in ("failure_triggered", "high_risk", "negative_live_test_delta", "needs_revision_flagged")) else "medium"
        return {
            "audit_required": bool(reasons),
            "reason": reasons[0] if reasons else "no_audit_needed",
            "priority": priority,
            "reasons": reasons,
            "skill_id": skill_id,
            "trigger": trigger,
        }

    def record_skill_audit(self, skill_id: str, eval_result: Dict[str, Any], trigger: str = "sampling") -> Dict[str, Any]:
        artifact = self.get_skill_artifact(skill_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {skill_id}")
        metadata = artifact.get("metadata") or {}
        usage_loop = metadata.get("usage_loop") or {}
        usage_loop["last_audit_at"] = _now_iso()
        usage_loop["last_audit_trigger"] = trigger
        usage_loop["last_audit_passed"] = bool(eval_result.get("passed"))
        usage_loop["last_audit_reason"] = eval_result.get("reason") or eval_result.get("decision_reason") or ""

        current_status = artifact.get("status")
        decision = "kept"
        updates = {"metadata": metadata, "latest_decision_reason": usage_loop["last_audit_reason"]}
        if eval_result.get("passed"):
            updates["latest_decision"] = "audit_passed"
        else:
            usage_loop["audit_failures"] = int(usage_loop.get("audit_failures") or 0) + 1
            unsafe = bool(eval_result.get("unsafe") or eval_result.get("misleading"))
            if unsafe:
                decision = "deprecated"
                updates.update({
                    "status": "deprecated",
                    "review_status": "deprecated",
                    "inject_enabled": 0,
                    "trial_enabled": 0,
                    "requires_feedback": 0,
                    "deprecated_at": _now_iso(),
                    "latest_decision": "deprecated",
                })
            elif current_status == "approved":
                decision = "needs_revision"
                updates.update({
                    "status": "needs_revision",
                    "review_status": "needs_revision",
                    "inject_enabled": 0,
                    "trial_enabled": 1,
                    "requires_feedback": 1,
                    "needs_revision": 1,
                    "latest_decision": "needs_revision",
                })
            else:
                decision = "needs_revision"
                updates.update({
                    "status": "needs_revision",
                    "review_status": "needs_revision",
                    "trial_enabled": 1,
                    "requires_feedback": 1,
                    "needs_revision": 1,
                    "latest_decision": "needs_revision",
                })
        metadata["usage_loop"] = usage_loop
        self.update_skill_artifact(skill_id, **updates)
        return {"skill_id": skill_id, "decision": decision, "updates": updates}

    def deprecate_skill(self, node_id: str, reason: str = "") -> Dict[str, Any]:
        artifact = self.get_skill_artifact(node_id)
        if not artifact:
            raise ValueError(f"skill artifact not found: {node_id}")
        metadata = artifact.get("metadata") or {}
        if reason:
            metadata["deprecated_reason"] = reason
        self.update_skill_artifact(
            node_id,
            status="deprecated",
            review_status="deprecated",
            inject_enabled=0,
            trial_enabled=0,
            requires_feedback=0,
            deprecated_at=_now_iso(),
            metadata=metadata,
        )
        sync_info = self.sync_skill_file(node_id)
        return {"skill_id": node_id, "status": "deprecated", "file": sync_info}

    # ── 批量操作（Dream Phase 使用）────────────────────────

    def bulk_get_vectors(self) -> list:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, vector, content, task_type, principle FROM nodes WHERE vector IS NOT NULL")
            keys = ["id", "vector", "content", "task_type", "principle"]
            return [dict(zip(keys, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def bulk_get_nodes_by_task(self) -> dict:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, type, task_type, created_at, metadata
                FROM nodes WHERE task_type IS NOT NULL
                ORDER BY task_type, created_at
            """)
            by_task: Dict[str, list] = {}
            for nid, ntype, task, ts, meta_str in cur.fetchall():
                result_val = None
                if meta_str and meta_str != '{}':
                    try:
                        result_val = json.loads(meta_str).get("result")
                    except (json.JSONDecodeError, TypeError):
                        pass
                by_task.setdefault(task, []).append({
                    "id": nid, "type": ntype, "result": result_val, "ts": ts
                })
            return by_task
        finally:
            conn.close()

    def bulk_add_edges(self, edges: list) -> int:
        if not edges:
            return 0
        conn = self._connect()
        try:
            cur = conn.cursor()
            added = 0
            for e in edges:
                edge_id = str(uuid.uuid4())
                weight = e.get("weight", 0.5)
                relation_type = e["relation_type"]
                graph_dim = e.get("graph_dim", self._default_graph_dim(relation_type))
                strength = e.get("strength", self._default_strength(weight))
                cur.execute("""
                    INSERT OR IGNORE INTO edges(id, from_id, to_id, relation_type,
                                                weight, source, status, created_at,
                                                graph_dim, strength)
                    VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """, (edge_id, e["from_id"], e["to_id"], relation_type,
                      weight, e.get("source", "dream"), _now_iso(), graph_dim, strength))
                if cur.rowcount > 0:
                    added += 1
            conn.commit()
            return added
        finally:
            conn.close()

    def bulk_update_decay(self, updates: list) -> int:
        if not updates:
            return 0
        conn = self._connect()
        try:
            cur = conn.cursor()
            for u in updates:
                cur.execute("UPDATE nodes SET decay_score=?, tier=?, updated_at=? WHERE id=?",
                            (u["decay_score"], u["tier"], _now_iso(), u["id"]))
            conn.commit()
            return len(updates)
        finally:
            conn.close()

    def bulk_get_edge_pairs(self, relation_type: str) -> set:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT from_id, to_id FROM edges WHERE relation_type=?",
                        (relation_type,))
            pairs = set()
            for r in cur.fetchall():
                pairs.add((r[0], r[1]))
                pairs.add((r[1], r[0]))
            return pairs
        finally:
            conn.close()

    def get_top_hot_nodes(self, limit: int = 50) -> list:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                    SELECT content, principle, decay_score, type, task_type
                FROM nodes WHERE tier = 'hot'
                ORDER BY decay_score DESC LIMIT ?
            """, (limit,))
            keys = ["content", "principle", "decay_score", "type", "task_type"]
            return [dict(zip(keys, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def query_edges(self, where_clause: str = "",
                    params: tuple = ()) -> list:
        conn = self._connect()
        try:
            cur = conn.cursor()
            sql = ("SELECT id, from_id, to_id, relation_type, weight, source, "
                   "status, created_at, graph_dim, strength FROM edges")
            if where_clause:
                sql += " WHERE " + where_clause
            cur.execute(sql, params)
            keys = ["id", "from_id", "to_id", "relation_type", "weight",
                    "source", "status", "created_at", "graph_dim", "strength"]
            return [dict(zip(keys, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def query_nodes(self, where_clause: str = "",
                    params: tuple = ()) -> list:
        conn = self._connect()
        try:
            cur = conn.cursor()
            sql = ("SELECT id, type, content, principle, vector, tier, "
                   "decay_score, base_score, access_count, last_access, "
                   "created_at, updated_at, task_type, project, tags, metadata, "
                   "confidence, verified_count, half_life_days "
                   "FROM nodes")
            if where_clause:
                sql += " WHERE " + where_clause
            cur.execute(sql, params)
            keys = ["id", "type", "content", "principle", "vector", "tier",
                    "decay_score", "base_score", "access_count", "last_access",
                    "created_at", "updated_at", "task_type", "project",
                    "tags", "metadata",
                    "confidence", "verified_count", "half_life_days"]
            return [dict(zip(keys, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def add_raw_node(self, **fields) -> str:
        node_id = fields.pop("id", str(uuid.uuid4()))
        fields.setdefault("created_at", _now_iso())
        fields.setdefault("updated_at", _now_iso())
        fields.setdefault("tier", "hot")
        fields.setdefault("decay_score", 0.8)
        fields.setdefault("base_score", 0.8)
        fields.setdefault("access_count", 0)
        fields.setdefault("metadata", "{}")
        cols = ", ".join(fields.keys())
        cols = "id, " + cols
        placeholders = ", ".join(["?"] * (len(fields) + 1))
        vals = [node_id] + list(fields.values())
        conn = self._connect()
        try:
            conn.execute(f"INSERT INTO nodes({cols}) VALUES({placeholders})", vals)
            conn.commit()
            return node_id
        finally:
            conn.close()

    def veto_edges(self, edge_ids: list) -> int:
        if not edge_ids:
            return 0
        conn = self._connect()
        try:
            cur = conn.cursor()
            for eid in edge_ids:
                cur.execute("UPDATE edges SET status='vetoed' WHERE id=?", (eid,))
            conn.commit()
            return len(edge_ids)
        finally:
            conn.close()

    def update_meta(self, key: str, value: str):
        conn = self._connect()
        try:
            conn.execute("UPDATE meta SET value=? WHERE key=?", (value, key))
            conn.commit()
        finally:
            conn.close()

    def count_edges_where(self, where_clause: str = "",
                          params: tuple = ()) -> int:
        conn = self._connect()
        try:
            sql = "SELECT COUNT(*) FROM edges"
            if where_clause:
                sql += " WHERE " + where_clause
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    def count_nodes_where(self, where_clause: str = "",
                          params: tuple = ()) -> int:
        conn = self._connect()
        try:
            sql = "SELECT COUNT(*) FROM nodes"
            if where_clause:
                sql += " WHERE " + where_clause
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    # ── 统计 ──────────────────────────────────────────────

    def count_nodes(self) -> int:
        """返回节点总数"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM nodes")
            return cur.fetchone()[0]
        finally:
            conn.close()

    def count_edges(self) -> int:
        """返回边总数"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM edges")
            return cur.fetchone()[0]
        finally:
            conn.close()

    # ── Phase 2 新方法 ─────────────────────────────────────

    def update_node(self, node_id: str, **fields) -> bool:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM nodes WHERE id=?", (node_id,))
            if not cur.fetchone():
                return False

            allowed = NODE_UPDATE_FIELDS
            updates = {}
            for k, v in fields.items():
                if k in allowed:
                    updates[k] = v

            if not updates:
                return True

            if "task_type" in updates:
                updates["task_type"] = _normalize_task_type(updates["task_type"])
                self._register_task_type(updates["task_type"])
            updates = serialize_node_fields(updates)
            updates["updated_at"] = _now_iso()
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [node_id]
            conn.execute(f"UPDATE nodes SET {set_clause} WHERE id=?", values)

            if "content" in fields:
                cur.execute("SELECT principle FROM nodes WHERE id=?", (node_id,))
                row = cur.fetchone()
                principle = fields.get("principle") or (row[0] if row else None)
                new_abstract = self._make_abstract(fields["content"], principle)
                new_overview = self._make_overview(fields["content"], principle)
                vec = self._embedder.encode(fields["content"])
                vec_blob = vec.astype(np.float32).tobytes()
                conn.execute("UPDATE nodes SET abstract=?, overview=?, vector=? WHERE id=?",
                             (new_abstract, new_overview, vec_blob, node_id))
                if self._vector_index is not None:
                    self._vector_index.add(node_id, vec)

            if "precondition" in fields and fields["precondition"]:
                vec = self._embedder.encode(fields["precondition"])
                vec_blob = vec.astype(np.float32).tobytes()
                conn.execute("UPDATE nodes SET precondition_vec=? WHERE id=?", (vec_blob, node_id))

            conn.commit()
            return True
        finally:
            conn.close()

    def delete_node(self, node_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM nodes WHERE id=?", (node_id,))
            if not cur.fetchone():
                return False
            conn.execute("DELETE FROM edges WHERE from_id=? OR to_id=?", (node_id, node_id))
            conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
            conn.commit()
            # v6.1: Mark deleted in vector indices (synaptic weakening)
            if self._vector_index is not None:
                self._vector_index.mark_deleted(node_id)
            if self._precondition_index is not None:
                self._precondition_index.mark_deleted(node_id)
            return True
        finally:
            conn.close()

    def verify_node(self, node_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, confidence, verified_count FROM nodes WHERE id=?", (node_id,))
            row = cur.fetchone()
            if not row:
                return False
            new_confidence = min(1.5, row[1] + 0.05)
            new_count = row[2] + 1
            now = _now_iso()
            conn.execute(
                "UPDATE nodes SET confidence=?, verified_count=?, verified_at=?, updated_at=? WHERE id=?",
                (new_confidence, new_count, now, now, node_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def match_preconditions(self, context_vector, top: int = 5) -> list:
        self._ensure_precondition_index()
        if self._precondition_index is None or self._precondition_index.count == 0:
            return []

        matches = self._precondition_index.search(context_vector, top)
        results = []
        for node_id, similarity in matches:
            node = self.get_node(node_id)
            if node and node.get("predicted_outcome"):
                results.append({
                    "id": node_id,
                    "precondition": node.get("precondition", ""),
                    "predicted_outcome": node["predicted_outcome"],
                    "confidence": node.get("confidence", 1.0),
                    "similarity": round(similarity, 3),
                })
        return results

    def search_spreading(self, query: str, mode: str = "precise",
                         graph_dims: list = None, tags: list = None,
                         top: int = 5, layer: str = "L0", **kwargs) -> list:
        self._ensure_vector_index()
        q_vec = self._embedder.encode(query)

        # Step 1: Seed nodes via FAISS
        seeds = self._vector_index.search(q_vec, top=3)
        if not seeds:
            return []

        # Step 2: Spreading parameters by mode
        if mode == "precise":
            decay_by_dim = {"semantic": 0.7, "causal": 0.8, "temporal": 0.6, "entity": 0.5}
            min_activation = 0.3
            max_hops = 2
            allowed_strength = ["strong"]
        else:  # creative
            decay_by_dim = {"semantic": 0.8, "causal": 0.9, "temporal": 0.7, "entity": 0.6}
            min_activation = 0.1
            max_hops = 3
            allowed_strength = ["strong", "weak"]

        # Step 3: Initialize activation map
        activation = {node_id: similarity for node_id, similarity in seeds}

        # Step 4: Spread activation
        conn = self._connect()
        try:
            # v6.1: creative mode is_a zero-hop — inject principle parents
            if mode == "creative":
                cur = conn.cursor()
                for node_id in list(activation.keys()):
                    cur.execute(
                        "SELECT to_id FROM edges WHERE from_id=? AND relation_type='is_a' AND status='active'",
                        (node_id,)
                    )
                    for row in cur.fetchall():
                        principle_id = row[0]
                        if principle_id not in activation:
                            activation[principle_id] = 0.5

            frontier = list(activation.keys())
            visited = set()

            for hop in range(max_hops):
                next_frontier = []
                for node_id in frontier:
                    if node_id in visited:
                        continue
                    visited.add(node_id)

                    dim_filter = ""
                    if graph_dims:
                        placeholders = ",".join(["?"] * len(graph_dims))
                        dim_filter = f" AND graph_dim IN ({placeholders})"

                    strength_filter = " AND strength IN (" + ",".join(["?"] * len(allowed_strength)) + ")"

                    sql = (f"SELECT from_id, to_id, graph_dim, weight FROM edges "
                           f"WHERE (from_id=? OR to_id=?) AND status='active'"
                           f"{dim_filter}{strength_filter}")

                    params = [node_id, node_id]
                    if graph_dims:
                        params.extend(graph_dims)
                    params.extend(allowed_strength)

                    cur = conn.cursor()
                    cur.execute(sql, params)

                    for row in cur.fetchall():
                        from_id, to_id, gdim, weight = row
                        target = to_id if from_id == node_id else from_id

                        decay = decay_by_dim.get(gdim, 0.5)
                        new_act = activation[node_id] * weight * decay

                        if new_act > min_activation:
                            if target not in activation or new_act > activation.get(target, 0):
                                activation[target] = new_act
                                next_frontier.append(target)

                frontier = next_frontier

            # Step 5: Lateral inhibition
            cur = conn.cursor()
            activated_ids = list(activation.keys())
            if len(activated_ids) > 1:
                for i in range(len(activated_ids)):
                    for j in range(i + 1, len(activated_ids)):
                        a, b = activated_ids[i], activated_ids[j]
                        cur.execute(
                            "SELECT 1 FROM edges WHERE ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?)) "
                            "AND relation_type='similar_to' AND status='active'",
                            (a, b, b, a))
                        if cur.fetchone():
                            weaker = a if activation[a] < activation[b] else b
                            activation[weaker] *= 0.5

            # Step 6: Tag filtering
            if tags:
                filtered = {}
                for nid, act in activation.items():
                    node = self.get_node(nid)
                    if node:
                        node_tags = node.get("context_tags", "[]")
                        if isinstance(node_tags, str):
                            try:
                                node_tags = json.loads(node_tags)
                            except (json.JSONDecodeError, TypeError):
                                node_tags = []
                        if any(t in node_tags for t in tags):
                            filtered[nid] = act
                activation = filtered

            # Step 7: Return top results with layer
            sorted_results = sorted(activation.items(), key=lambda x: -x[1])[:top]

            results = []
            for nid, act_score in sorted_results:
                node = self.get_node(nid)
                if not node:
                    continue
                if not self._matches_node_filters(node.get("task_type"), node.get("project"), node.get("context_tags"), {"tags": tags, **kwargs}):
                    continue
                base = {"id": nid, "activation": round(act_score, 3), "tier": node.get("tier", "hot")}
                if layer == "L0":
                    base["abstract"] = node.get("abstract") or node.get("content", "")[:150]
                elif layer == "L1":
                    base["abstract"] = node.get("abstract") or node.get("content", "")[:150]
                    base["principle"] = node.get("principle")
                    base["confidence"] = node.get("confidence", 1.0)
                else:
                    base["content"] = node.get("content", "")
                    base["principle"] = node.get("principle")
                    base["confidence"] = node.get("confidence", 1.0)
                    base["decay_score"] = round(node.get("decay_score", 0), 3)
                    base["task_type"] = node.get("task_type")
                    base["project"] = node.get("project")
                results.append(base)

            # Touch visited nodes
            if results:
                self._touch_nodes([r["id"] for r in results], conn)
            conn.commit()

            return results
        finally:
            conn.close()

    # ── 内部方��� ──────────────────────────────────────────

    @staticmethod
    def _matches_node_filters(task_type: Optional[str], project: Optional[str],
                              context_tags, filters: Dict[str, Any]) -> bool:
        filter_task_type = filters.get("task_type")
        filter_project = filters.get("project")
        filter_tags = filters.get("tags") or filters.get("context_tags")
        if filter_task_type and task_type != filter_task_type:
            return False
        if filter_project and project != filter_project:
            return False
        if filter_tags:
            wanted = {str(tag) for tag in parse_json_list(filter_tags)}
            available = {str(tag) for tag in parse_json_list(context_tags)}
            available.update(str(item) for item in (task_type, project) if item)
            if not wanted.issubset(available):
                return False
        return True

    @staticmethod
    def _merge_node_fields(cur, node_id: str, task_type: Optional[str], project: Optional[str],
                           tags_json: str, metadata_json: str, context_tags_json: str,
                           precondition: Optional[str], predicted_outcome: Optional[str]):
        cur.execute(
            "SELECT task_type, project, tags, metadata, context_tags, precondition, predicted_outcome FROM nodes WHERE id=?",
            (node_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        old_task_type, old_project, old_tags, old_metadata, old_context_tags, old_precondition, old_predicted = row
        cur.execute("""
            UPDATE nodes
            SET task_type=?, project=?, tags=?, metadata=?, context_tags=?,
                precondition=?, predicted_outcome=?, updated_at=?
            WHERE id=?
        """, (
            old_task_type or task_type,
            old_project or project,
            merge_json_lists(old_tags, tags_json),
            merge_json_dicts(old_metadata, metadata_json),
            merge_json_lists(old_context_tags, context_tags_json),
            old_precondition or precondition,
            old_predicted or predicted_outcome,
            _now_iso(),
            node_id,
        ))

    @staticmethod
    def _default_graph_dim(relation_type: str) -> str:
        if relation_type in {"caused", "solves", "contradicts"}:
            return "causal"
        if relation_type in {"crystallized_from", "verified_by", "needs_revision"}:
            return "entity"
        return "semantic"

    @staticmethod
    def _default_strength(weight: float) -> str:
        return "strong" if (weight or 0.0) >= 0.6 else "weak"

    @staticmethod
    def _write_edge_inner(cur, from_id: str, to_id: str, relation_type: str,
                          weight: float = 0.5, source: str = "auto"):
        """在已有 cursor 上写边（供事务内调用），INSERT OR IGNORE 防重复

        迁自 graph_write._write_edge_inner。
        """
        edge_id = str(uuid.uuid4())
        created = _now_iso()
        graph_dim = SQLiteStore._default_graph_dim(relation_type)
        strength = SQLiteStore._default_strength(weight)
        cur.execute("""
            INSERT OR IGNORE INTO edges(id, from_id, to_id, relation_type,
                                        weight, source, status, created_at,
                                        graph_dim, strength)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """, (edge_id, from_id, to_id, relation_type, weight, source, created,
              graph_dim, strength))

    @staticmethod
    def _touch_nodes(node_ids: list, conn: sqlite3.Connection):
        """访问激活：批量更新 access_count 和 last_access

        迁自 graph_query._touch_nodes。
        """
        if not node_ids:
            return
        now = _now_iso()
        cur = conn.cursor()
        for nid in node_ids:
            cur.execute("""
                UPDATE nodes SET access_count = access_count + 1,
                                 last_access = ?,
                                 updated_at = ?
                WHERE id = ?
            """, (now, now, nid))

    # ── FAISS 索引延迟构建 ──────────────────────────────────

    def _ensure_vector_index(self):
        if self._vector_index is not None:
            # v6.1: Check if lazy rebuild is needed
            if self._vector_index.rebuild_needed():
                nodes = self.bulk_get_vectors()
                if nodes:
                    vectors = np.array([np.frombuffer(n["vector"], dtype=np.float32) for n in nodes if n.get("vector")])
                    ids = [n["id"] for n in nodes if n.get("vector")]
                    self._vector_index.rebuild_if_needed(vectors, ids)
            return
        from .vector_index import VectorIndex
        self._vector_index = VectorIndex(self._embedder.get_dimension())
        nodes = self.bulk_get_vectors()
        if nodes:
            vectors = np.array([np.frombuffer(n["vector"], dtype=np.float32) for n in nodes if n.get("vector")])
            ids = [n["id"] for n in nodes if n.get("vector")]
            if len(vectors) > 0:
                self._vector_index.build(vectors, ids)

    def _ensure_precondition_index(self):
        if self._precondition_index is not None:
            return
        from .vector_index import VectorIndex
        self._precondition_index = VectorIndex(self._embedder.get_dimension())
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, precondition_vec FROM nodes WHERE precondition_vec IS NOT NULL")
            rows = cur.fetchall()
            if rows:
                vectors = np.array([np.frombuffer(r[1], dtype=np.float32) for r in rows])
                ids = [r[0] for r in rows]
                self._precondition_index.build(vectors, ids)
        finally:
            conn.close()
