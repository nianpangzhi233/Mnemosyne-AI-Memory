<div align="center">

# Mnemosyne

**Bionic Memory System for AI Agents**

GraphRAG-based memory inspired by the human brain — powered by
[Harrier](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) embeddings,
knowledge graph, and dream-based consolidation.

[English](#features) · [中文文档](#中文说明)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Embedding: Harrier 0.6b](https://img.shields.io/badge/embedding-Harrier--0.6b-orange?style=flat-square)](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)

</div>

---

## Why Mnemosyne?

AI agents forget everything between sessions. Humans don't — because the brain
has a three-layer memory system (hippocampus → neocortex → basal ganglia),
dream-based consolidation, and reconsolidation during retrieval.

**Mnemosyne brings this to AI agents.**

| Brain | Mnemosyne |
|-------|-----------|
| Hippocampus fast encoding | `graph_write` — instant experience logging |
| Neocortex slow consolidation | `graph_dream` — nightly 11-phase pipeline |
| Retrieval-triggered reconsolidation | `search_by_vector` with touch & decay update |
| REM sleep abstraction | Optional LLM-powered 3-round review |
| Synaptic pruning | Decay scoring + cold archive |
| Forgetting curve | `base_score × e^(-0.03 × days) × log₂(access+2)` |

## Features

- **Vector + Knowledge Graph + FTS5** — triple retrieval with semantic chain expansion
- **11-Phase Dream Pipeline** — mimics NREM+REM sleep for memory consolidation
  - Similarity detection, causal linking, contradiction detection, cross-domain transfer
  - Strategy generation, privacy audit (covenant), decay recalculation
  - Optional LLM REM review with undo log and confidence-based actions
- **Plug-in Architecture** — every component is swappable via abstract interfaces
  - `AbstractGraphStore` → SQLite (default), FAISS, Neo4j, ...
  - `AbstractEmbedder` → Harrier (default), BGE-M3, Qwen, ...
  - `AbstractTaskRunner` → APScheduler (default), Celery, ...
- **Zero Cloud Dependency** — runs fully local, no API keys needed
- **One-command install** — `python setup.py` handles everything

## Quick Start

```bash
git clone https://github.com/yourname/mnemosyne.git
cd mnemosyne
python setup.py
```

That's it. Setup will:
1. Check Python 3.10+
2. Install dependencies (torch, sentence-transformers, numpy, apscheduler)
3. Create directory structure
4. Initialize SQLite database
5. Verify everything works

### Record an Experience

```bash
python scripts/graph_write.py \
  --content "gzip-compressed request bodies must be decompressed before JSON.parse()" \
  --type experience \
  --principle "Always check Content-Encoding header before parsing"
```

### Search Memory

```bash
# Semantic search
python scripts/graph_query.py --vector-search "request body parsing" --top 5

# Keyword search (FTS5)
python scripts/graph_query.py --keyword-search "gzip" --top 5

# Hybrid (vector + keyword)
python scripts/graph_query.py --hybrid-search "API proxy gzip" --top 5
```

### Dream (Nightly Consolidation)

```bash
# Full dream cycle (11 phases)
python scripts/graph_dream.py --full

# Stats only
python scripts/graph_dream.py --stats

# Single phase
python scripts/graph_dream.py --phase 2
```

### Health Check

```bash
python scripts/graph_audit.py
```

## Architecture

```
mnemosyne/
├── scripts/
│   ├── core/                  # Abstract interfaces + implementations
│   │   ├── graph_store.py     # AbstractGraphStore (12+ methods)
│   │   ├── sqlite_store.py    # SQLiteStore with vector + FTS5 + chain expansion
│   │   ├── embedder.py        # AbstractEmbedder → Harrier / BGE-M3 / Qwen
│   │   ├── dream_pipeline.py  # 11 dream phases as plug-in classes
│   │   ├── task_runner.py     # AbstractTaskRunner → APScheduler / Celery
│   │   └── utils.py           # Windows encoding fix + HF offline helper
│   ├── graph_write.py         # Write CLI
│   ├── graph_query.py         # Query CLI (vector / keyword / hybrid / inject)
│   ├── graph_dream.py         # Dream CLI
│   ├── graph_audit.py         # Health report + cleanup
│   ├── graph_init.py          # Database initialization
│   ├── llm_judge.py           # Optional LLM REM review layer
│   └── re_embed.py            # Re-embed all nodes (model swap)
├── engine/                    # Legacy rule engine configs
├── docs/
├── llm_config.json            # LLM review config (disabled by default)
├── meta.json
└── setup.py                   # One-command installer
```

### Dream Pipeline (11 Phases)

| # | Phase | Brain Analog | What It Does |
|---|-------|-------------|--------------|
| 1 | Snapshot | Prefrontal monitor | Record pre-dream state, set caps |
| 2 | SimilarTo | Pattern matching | Scan vector similarity, link ≥0.85 |
| 3 | Causal | Sequential memory | Detect failure→success causal chains |
| 4 | Contradicts | Conflict resolution | Find contradictory experiences |
| 5 | Transfers | Cross-modal transfer | Link experiences sharing principles across domains |
| 6 | Strategy | Skill extraction | Generate abstract strategies from experience hubs |
| 7 | Covenant | Moral compass | Veto self-loops, weak edges, privacy leaks |
| 8 | Decay | Synaptic pruning | Recalculate decay scores, archive cold nodes |
| 9 | LLM Review | REM sleep | Optional 3-round adaptive LLM review (quick→deep→final) |
| 10 | Sync | Working memory | Export top 50 hot nodes to memory.md |
| 11 | Audit | Metacognition | Post-dream health check, detect bloat |

### Edge Types (Knowledge Graph)

| Relation | Meaning |
|----------|---------|
| `is_a` | Experience → Principle abstraction |
| `similar_to` | Semantic similarity (vector ≥ 0.85) |
| `caused` | Causal link (failure → success) |
| `solves` | Inverse of caused (success ← failure) |
| `contradicts` | Conflicting experiences |
| `transfers_to` | Cross-domain principle transfer |
| `evolved_from` | Strategy extracted from experience hub |

## Configuration

### LLM Review (Optional)

Create `llm_config.json` to enable REM-style LLM review:

```json
{
  "enabled": true,
  "endpoint": "http://localhost:8978/v1/chat/completions",
  "model": "your-model-name",
  "max_tokens": 1024,
  "timeout": 120
}
```

When disabled (default), the system runs purely on rules — no LLM needed.

### Scheduled Dreams

Add to crontab or Windows Task Scheduler:

```bash
# Linux/Mac: 3 AM daily
0 3 * * * cd /path/to/mnemosyne && python scripts/graph_dream.py --full

# Windows: use dream.cmd or Task Scheduler
```

## Embedding Models

| Model | Dimensions | Speed | Quality | License |
|-------|-----------|-------|---------|---------|
| [Harrier-OSS-v1-0.6b](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) | 1024 | Fast (1.2s load) | MTEB #1 (2026) | MIT |
| BGE-M3 | 1024 | Slow (11s load) | Strong | MIT |
| Qwen3-Embedding | 1024 | Medium | Strong | Apache 2.0 |

Default: **Harrier** — 10x faster load, MTEB #1, 1024-dim compatible with BGE-M3.

## Requirements

- Python 3.10+
- torch ≥ 2.6 (CPU OK)
- sentence-transformers
- numpy
- apscheduler

## 中文说明

**Mnemosyne** 是一个仿生 AI 记忆系统，模仿人脑的三层记忆架构（海马体→新皮层→基底神经节），
为 AI Agent 提供持久化、可检索、自动整理的经验记忆。

### 核心设计理念

| 人脑机制 | Mnemosyne 对应 |
|---------|---------------|
| 海马体快速编码 | 即时写入经验节点 |
| 新皮层慢速整合 | 夜间做梦流水线（11阶段） |
| 检索触发重巩固 | 搜索时自动 touch + decay 更新 |
| REM 睡眠抽象化 | 可选 LLM 三轮自适应审查 |
| 突触修剪 | 衰减评分 + 冷归档 |
| 艾宾浩斯遗忘曲线 | 指数衰减 + 间隔重复强化 |

### 快速上手

```bash
# 安装
python setup.py

# 写入经验
python scripts/graph_write.py --content "经验内容" --type experience --principle "抽象原理"

# 搜索
python scripts/graph_query.py --vector-search "关键词" --top 5

# 做梦（夜间整理）
python scripts/graph_dream.py --full

# 健康报告
python scripts/graph_audit.py
```

### 插件化架构

所有组件通过抽象接口解耦，可独立替换：

- **GraphStore** → SQLite（默认）/ FAISS / Neo4j / 任意图数据库
- **Embedder** → Harrier（默认）/ BGE-M3 / Qwen / 任意向量模型
- **TaskRunner** → APScheduler（默认）/ Celery / 任意调度器

### 特性

- **三路检索**：向量语义 + FTS5 关键词 + 知识图谱遍历
- **语义链搜索**：55% 最佳相似度截止 + 图遍历扩展，结果连贯无噪声
- **原则精确分类**：相同 principle 的经验自动强化（base_score +0.1）
- **隐私守护（Covenant）**：自动检测并否决含密码/密钥等敏感信息的边
- **完全本地运行**：无需云端 API，无需密钥
- **LLM 可选**：默认纯规则模式，可配置 LLM 增强 REM 审查

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE) — use it however you want.

## Acknowledgments

Brain science foundations:
- **CLS Theory** (Complementary Learning Systems) — fast/slow dual memory
- **Reconsolidation** — retrieval as re-encoding window
- **NREM replay + REM abstraction** — two-stage memory consolidation
- **Ebbinghaus Forgetting Curve** — exponential decay with spaced repetition

Built with [Harrier](https://huggingface.co/microsoft/harrier-oss-v1-0.6b),
[sentence-transformers](https://www.sbert.net/),
[SQLite FTS5](https://www.sqlite.org/fts5.html).
