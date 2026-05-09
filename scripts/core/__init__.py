#!/usr/bin/env python3
"""Mnemosyne 核心模块 — v5.0 抽象层

导出三个核心接口及其默认实现：
- GraphStore: 图存储（节点/边/检索）
- Embedder: 嵌入模型（向量编码）
- TaskRunner: 异步任务（定时调度）
"""

from .graph_store import AbstractGraphStore
from .sqlite_store import SQLiteStore
from .vector_index import VectorIndex
from .embedder import AbstractEmbedder, BgeM3Embedder, HarrierEmbedder, QwenEmbedder
from .task_runner import AbstractTaskRunner, APSchedulerRunner, CeleryRunner
from .dream_pipeline import (
    DreamPhase, DreamPipeline, run_dream,
    SnapshotPhase, AuditPhase, LLMReviewPhase,
    LogScanPhase, DistillPhase, SimilarToPhase, CausalPhase, ContradictsPhase, TransfersPhase,
    SkillEmbryoPhase, SkillDevelopmentPhase, SkillMirrorEvolutionPhase,
    StrategyPhase, CovenantPhase, DecayPhase, SyncPhase,
)

__all__ = [
    "AbstractGraphStore",
    "SQLiteStore",
    "VectorIndex",
    "AbstractEmbedder",
    "BgeM3Embedder",
    "HarrierEmbedder",
    "QwenEmbedder",
    "AbstractTaskRunner",
    "APSchedulerRunner",
    "CeleryRunner",
    "DreamPhase",
    "DreamPipeline",
    "run_dream",
    "SnapshotPhase",
    "AuditPhase",
    "LLMReviewPhase",
    "LogScanPhase",
    "DistillPhase",
    "SimilarToPhase",
    "CausalPhase",
    "ContradictsPhase",
    "TransfersPhase",
    "SkillEmbryoPhase",
    "SkillDevelopmentPhase",
    "SkillMirrorEvolutionPhase",
    "StrategyPhase",
    "CovenantPhase",
    "DecayPhase",
    "SyncPhase",
]
