# Mnemosyne 升级规划 v4.1

> 设计原则：解耦设计，像组装手机一样。AI 日新月异，固定绑定就是挖坑。

## 抽象层架构

```
┌───────────────────────────────────────────────┐
│              上层应用（不改）                    │
│   graph_write / graph_query / covenant        │
├───────────────┬───────────────────────────────┤
│  GraphStore   │         Embedder              │
│  (接口)        │         (接口)                │
├───────────────┼───────────────────────────────┤
│ SQLiteStore   │  BgeM3Embedder (当前)          │
│ (默认实现)     │  HarrierEmbedder (待验证)      │
│               │  QwenEmbedder (备选)           │
├───────────────┴───────────────────────────────┤
│          Retriever (混合检索)                   │
│  VectorSearch + FTS5Search → FusionMerge      │
│  预留 CrossEncoderReranker 接口                │
├───────────────────────────────────────────────┤
│          TaskRunner (异步任务)                  │
│  APScheduler (定时调度)                        │
│  concurrent.futures (后台异步)                 │
│  预留 Celery 接口                              │
├───────────────────────────────────────────────┤
│          Dream Pipeline (插件化)                │
│  Phase 1: similar_to    ← 可替换               │
│  Phase 2: causal        ← 可替换               │
│  Phase 3: contradicts   ← 可替换               │
│  Phase 4: transfers     ← 可替换               │
│  Phase 5: strategy      ← 可替换               │
│  Phase 6: covenant      ← 可替换               │
│  Phase 7: decay         ← 可替换               │
│  Phase 8: sync          ← 可替换               │
│  Phase 9: llm_reflect   ← 未来可插拔           │
└───────────────────────────────────────────────┘
```

## v4.1 — 夯实地基（近期）

| # | 任务 | 内容 | 依赖 |
|---|------|------|------|
| 1 | **GraphStore 接口** | 抽象 add_node、add_edge、get_node、traverse、search 等方法 | 无 |
| 2 | **SQLiteStore 实现** | 把现有 graph_write/query/dream 的 SQL 逻辑迁入 | #1 |
| 3 | **Embedder 接口** | 抽象 encode、encode_batch、get_dimension 方法 | 无 |
| 4 | **BgeM3Embedder 实现** | 把现有 BGE-M3 加载和推理逻辑迁入 | #3 |
| 5 | **Harrier 调研+验证** | 验证 harrier-oss-v1-0.6b 是否可下载、CPU 速度、中文质量 | 无 |
| 6 | **TaskRunner 接口** | 抽象 submit、schedule、cancel。默认 APScheduler + concurrent.futures，预留 Celery 接口 | 无 |
| 7 | **混合检索** | 合并 vector_search + keyword_search，加权融合去重 | #2, #4 |
| 8 | **Dream Pipeline 插件化** | 8 个 Phase 各自独立成类，注册到 Pipeline | #1, #3, #6 |
| 9 | **一键安装脚本** | setup.py：检测环境→安装依赖→创建目录→初始化数据库→验证 | #1-6 |

**交付物：** 所有脚本重构完成，功能不变但架构解耦，一键安装可用。

## v4.2 — 体验升级（v4.1 稳定后）

| # | 任务 | 内容 |
|---|------|------|
| 1 | **可视化仪表板** | Streamlit + pyvis：节点统计、图谱网络图、搜索功能。预留手动编辑空间 |
| 2 | **LLM 可选梦境** | `--llm-endpoint` 参数，接入 LLM 做策略反思和矛盾检测。默认关闭，纯本地 |
| 3 | **近似最近邻** | 用 FAISS 或 HNSW 替代全量向量扫描，加速做梦 Phase 1 |
| 4 | **基准测试** | 跑 LoCoMo 或自建评测，建立技术信任 |
| 5 | **Cross-Encoder 评估** | 测重排序效果和性能 |

## 长期展望（v5.0+）

- 多模态记忆（图片/音频向量化，参考 Qwen3-VL-Embeddings-2B）
- 时空记忆标签
- 团队共享记忆
- Celery 分布式任务队列（当 APScheduler 不够用时）

---

## 调研结论

### Harrier-OSS-v1 调研结论

Microsoft 2026年4月发布，MTEB 多语言排行榜 **#1**（0.6b 版本 69.0 分，BGE-M3 为 63.2 分）。

| 模型 | 参数 | 维度 | MTEB 分数 | 适用场景 |
|------|------|--------|-----------|---------|
| harrier-oss-v1-0.6b | 0.6B | **1024** | **69.0** | **我们的最佳选择** |
| harrier-oss-v1-270m | 270M | 640 | 66.5 | 边缘设备 |
| harrier-oss-v1-27b | 27B | 5376 | 74.3 | 服务器 |

关键：**0.6b 版本跟 BGE-M3 同维度（1024），MTEB 分数高 5.8 分，且支持 32K 上下文（BGE-M3 只有 8K）。** 可通过 sentence-transformers 直接加载（HuggingFace 有）。

### Embedder 接口设计

```python
class Embedder:
    """嵌入模型接口"""
    def encode(self, texts, **kwargs) -> np.ndarray: ...
    def encode_batch(self, texts, **kwargs) -> List[np.ndarray]: ...
    def get_dimension(self) -> int: ...

class BgeM3Embedder(Embedder): ...
class HarrierEmbedder(Embedder): ...   # 待验证
class QwenEmbedder(Embedder): ...    # 备选
```

### TaskRunner 接口设计

```python
class TaskRunner:
    """异步任务运行器接口"""
    def submit(self, func, *args, **kwargs): ...
    def schedule(self, cron_expr, func, *args): ...
    def cancel(self, job_id): ...

class APSchedulerRunner(TaskRunner):
    """默认实现：APScheduler + concurrent.futures"""
    # 零外部依赖，适合单用户本地系统

class CeleryRunner(TaskRunner):
    """未来实现：Celery + Redis"""
    # 生产级，支持分布式，需要 Redis 服务
```

### GraphStore 接口设计

```python
class GraphStore:
    """图存储接口"""
    def add_node(self, content, node_type, **kwargs): ...
    def add_edge(self, from_id, to_id, relation_type): ...
    def traverse(self, node_id, depth): ...
    def search(self, query, top): ...   # FTS5 + vector 混合

class SQLiteStore(GraphStore): ...   # 当前实现
class Neo4jStore(GraphStore): ...   # 未来实现
```

---

## 实施节奏

| 阶段 | 核心目标 | 关键任务 | 预计周期 |
|------|-----------|----------|----------|
| Phase 1 (v4.1) | 抽象层 + 接口 | #1 GraphStore 接口 + #3 Embedder 接口 + #6 TaskRunner 接口 | 2-3周 |
| Phase 2 (v4.1) | 实现层 | #2 SQLiteStore + #4 BgeM3Embedder + #5 Harrier 验证 | 2-3周 |
| Phase 3 (v4.1) | 检索 + 管线 | #7 混合检索 + #8 Dream Pipeline 插件化 | 2-3周 |
| Phase 4 (v4.1) | 交付 | #9 一键安装脚本 + 全量回归测试 | 1-2周 |
| Phase 5 (v4.2) | 体验升级 | 可视化仪表板 + LLM 可选梦境 + 近似最近邻 + 基准测试 | 2-3个月 |
| Phase 6 (v5.0) | 生态完善 | 多模态记忆 + 时空标签 + 团队共享 + Celery | 3-4个月 |

---

## 陛下批注

- ✅ 解耦设计：GraphStore + Embedder + TaskRunner 三接口
- ✅ SQLite 默认实现，Neo4j/Celery 预留接口
- ✅ Harrier 0.6b 调研通过后可替换（1024维兼容 BGE-M3，无缝迁移）
- ✅ APScheduler + concurrent.futures 作为默认 TaskRunner
- ✅ Celery 接口预留，当 APScheduler 不够用时升级
- ✅ LLM 梦境作为可选（--llm-endpoint 参数）
