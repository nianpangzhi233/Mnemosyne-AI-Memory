---
name: mnemosyne
description: |
  Bionic AI memory system: GraphRAG with vector embeddings + knowledge graph + SQLite.
  Semantic search, association chain injection, dream-based evolution, automatic pattern discovery.
  Your AI remembers, associates, and evolves — like a living brain.
---

**[English](../README.md)**

---

# Mnemosyne

> **让 AI 拥有像人脑一样的记忆——会联想、会遗忘、会做梦。**

---

## 你的 AI 有个问题

它记不住东西。

每次对话都是一张白纸。你教过它的经验、踩过的坑、走过的弯路——全忘了。

你花了 30 分钟跟 AI 解释项目的架构，第二天它全忘了。
你纠正了它 3 次"不要用 var，用 const"，第四次它还在写 var。
你说过"我喜欢函数式风格"，下次照旧给你写 class。

**Mnemosyne 改变了这一切。**

它不是文件存储，不是日记本，不是关键词匹配。
它是**活的记忆图谱**——像人脑一样会联想、会遗忘、会做梦。

---

## 它能做什么？

### 语义联想

你告诉 AI "我喜欢简洁的回复"，下次它写长篇大论时会想起来——不是关键词匹配，而是它*理解*"回复太长"和你的偏好有关。

### 知识图谱

8 种关系类型把零散经验连成网：

| 关系 | 含义 |
|------|------|
| `is_a` | 经验 → 抽象原理 |
| `similar_to` | 语义相似（向量 ≥ 0.85） |
| `caused` | "没做参数校验" → 导致 → "线上 500 报错" |
| `solves` | "加了重试机制" → 解决 → "接口超时" |
| `contradicts` | 新经验推翻旧经验 |
| `transfers_to` | 同原理，不同领域 |
| `evolved_from` | 策略从经验集群提炼而来 |

### 做梦进化

人脑在睡觉时整合记忆——Mnemosyne 也一样。11 个阶段的流水线，自动发现深层关联、生成策略、淘汰过时记忆。

| # | 阶段 | 人脑对应 | 做什么 |
|---|------|---------|--------|
| 1 | 快照 | 前额叶监控 | 记录状态，设安全上限 |
| 2 | 相似度 | 模式匹配 | 发现相似经验，建 similar_to 边 |
| 3 | 因果 | 序列记忆 | 检测 失败→成功 因果链 |
| 4 | 矛盾 | 冲突消解 | 发现矛盾经验 |
| 5 | 迁移 | 跨模态迁移 | 跨领域原理关联 |
| 6 | 策略 | 技能提炼 | 从经验集群提炼抽象策略 |
| 7 | 安全 | 道德审查 | 否决隐私泄露 & 弱边 |
| 8 | 衰减 | 突触修剪 | 重算评分，归档冷记忆 |
| 9 | LLM 审查 | REM 睡眠 | 可选 3 轮自适应审查 |
| 10 | 同步 | 工作记忆 | 导出热节点到 memory.md |
| 11 | 审计 | 元认知 | 做梦后健康检查 |

### 直觉注入

会话启动时，根据工作目录自动注入最相关的经验联想链。
**你不需要记得去查记忆——记忆主动找到你。**

### 安全守卫

所有自动发现的关系经过 Covenant 安全审核。涉及密码、密钥、敏感信息的边会被自动否决。

---

## 快速上手

```bash
git clone https://github.com/nianpangzhi233/Mnemosyne-AI-Memory.git
cd Mnemosyne-AI-Memory
python setup.py
```

一行命令搞定一切：

1. 检查 Python 3.10+
2. 安装依赖（torch、sentence-transformers、numpy、apscheduler）
3. 创建目录结构
4. 初始化 SQLite 数据库
5. 验证安装

### 记录经验

```bash
python scripts/graph_write.py \
  --content "gzip 请求体必须先解压再 JSON.parse()" \
  --type experience \
  --principle "先看 Content-Encoding 请求头，别假设请求体是明文"
```

### 搜索记忆

```bash
# 语义搜索——用自然语言描述问题
python scripts/graph_query.py --vector-search "请求体解析" --top 5

# 关键词搜索——精确匹配
python scripts/graph_query.py --keyword-search "gzip" --top 5

# 混合搜索——两全其美
python scripts/graph_query.py --hybrid-search "API 代理 gzip" --top 5
```

### 做梦（夜间整合）

```bash
# 完整 11 阶段做梦
python scripts/graph_dream.py --full

# 仅看统计
python scripts/graph_dream.py --stats

# 运行单个阶段
python scripts/graph_dream.py --phase 2
```

### 健康检查

```bash
python scripts/graph_audit.py              # 健康报告
python scripts/graph_audit.py --clean       # 预览清洗
python scripts/graph_audit.py --clean --force  # 执行清洗
```

---

## 架构

所有组件通过抽象接口解耦，可独立替换：

- **GraphStore** → SQLite（默认）/ FAISS / Neo4j / 任意图数据库
- **Embedder** → Harrier（默认）/ BGE-M3 / Qwen / 任意向量模型
- **TaskRunner** → APScheduler（默认）/ Celery / 任意调度器

```
mnemosyne/
├── scripts/
│   ├── core/                  # 插件化架构
│   │   ├── graph_store.py     # AbstractGraphStore（12+ 方法）
│   │   ├── sqlite_store.py    # SQLiteStore: 向量 + FTS5 + 图遍历
│   │   ├── embedder.py        # AbstractEmbedder → Harrier / BGE-M3 / Qwen
│   │   ├── dream_pipeline.py  # 11 个做梦阶段插件
│   │   ├── task_runner.py     # AbstractTaskRunner → APScheduler / Celery
│   │   └── utils.py           # Windows 编码 + HF 离线工具
│   ├── graph_write.py         # 写入 CLI
│   ├── graph_query.py         # 查询 CLI（向量/关键词/混合/注入）
│   ├── graph_dream.py         # 做梦 CLI
│   ├── graph_audit.py         # 健康报告 + 清洗
│   ├── graph_init.py          # 数据库初始化
│   ├── llm_judge.py           # 可选 LLM REM 审查层
│   └── re_embed.py            # 全量重新嵌入（换模型用）
├── engine/                    # 旧版规则引擎配置
├── docs/
├── llm_config.json            # LLM 审查配置（默认关闭）
└── setup.py                   # 一键安装
```

---

## 配置

### LLM 审查（可选）

创建 `llm_config.json` 启用 REM 式 LLM 审查：

```json
{
  "enabled": true,
  "endpoint": "http://localhost:8978/v1/chat/completions",
  "model": "你的模型名称",
  "max_tokens": 1024,
  "timeout": 120
}
```

默认关闭时，系统纯规则运行——不需要任何 LLM。

### 定时做梦

```bash
# Linux/Mac: 每天凌晨 3 点
0 3 * * * cd /path/to/mnemosyne && python scripts/graph_dream.py --full

# Windows: 使用 dream.cmd 或任务计划程序
```

---

## 嵌入模型

| 模型 | 维度 | 加载速度 | 质量 | 许可证 |
|------|------|---------|------|--------|
| [Harrier-OSS-v1-0.6b](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) | 1024 | **1.2 秒** | MTEB #1 (2026) | MIT |
| BGE-M3 | 1024 | 11 秒 | 强 | MIT |
| Qwen3-Embedding | 1024 | 中等 | 强 | Apache 2.0 |

默认使用 **Harrier**——加载快 10 倍，MTEB 排名第一，1024 维兼容 BGE-M3。

---

## 设计哲学

Mnemosyne 模仿人脑记忆的三个层次：

| 人脑 | Mnemosyne |
|-----|-----------|
| 海马体快速编码 | `graph_write` — 即时写入经验 |
| 新皮层慢速整合 | `graph_dream` — 夜间 11 阶段流水线 |
| 检索触发重巩固 | 搜索时自动 touch + decay 更新 |
| REM 睡眠抽象化 | 可选 LLM 三轮自适应审查 |
| 突触修剪 | 衰减评分 + 冷归档 |
| 遗忘曲线 | `base_score × e^(-0.03 × 天数) × log₂(访问+2)` |

**直觉** — 走进厨房，自动想到"饿"。环境触发了记忆。启动注入做的就是这个——根据工作环境自动推送相关经验。

**回忆** — 有人问"上次那个菜怎么做"，你主动检索。向量搜索 + 图谱遍历找到经验，沿关系边发现深层关联。

**做梦** — 睡觉时大脑重播经历、整合关联、修剪无用记忆。做梦流水线自动完成同样的事。

---

## 要求

- Python 3.10+
- 约 2GB 磁盘空间（嵌入模型）
- 完全本地运行，无需任何外部服务或 API 密钥
