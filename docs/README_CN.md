<div align="center">

# Mnemosyne

**给 AI 装一颗会忘、会想、会做梦的脑。**

仿生经验与记忆系统 — 知识图谱 + 向量搜索 + 预测式记忆 + MCP 集成

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-purple?style=flat-square)](https://modelcontextprotocol.io/)
[![Version](https://img.shields.io/badge/version-6.1.0-black?style=flat-square)](../CHANGELOG.md)
[![Search](https://img.shields.io/badge/search-hybrid%20%7C%20precise%20%7C%20creative-orange?style=flat-square)](#知识图谱--多维检索)
[![Memory](https://img.shields.io/badge/memory-predictive%20%2B%20dreaming-8A2BE2?style=flat-square)](#预测式记忆)

[English](../README.md) · [Releases](https://github.com/nianpangzhi233/Mnemosyne-AI-Memory/releases)

</div>

---

## 你的 AI 有个问题

AI 助手有个致命缺陷：**它记不住事。**

你花了半小时解释项目架构，第二天它全忘了。你纠正了 3 次"用 const 不要用 var"，第 4 次它还是写 var。你说"我喜欢简洁的回复"，下个会话又开始写小作文。

这不是 bug，是设计——每次对话都是一张白纸。

**Mnemosyne 解决这个问题。** 不是文件存储，不是日记本，不是关键词匹配。是一张**活的知识图谱**——像人脑一样，会联想、会遗忘、会做梦。

---

## 5 分钟上手

```bash
git clone https://github.com/nianpangzhi233/Mnemosyne-AI-Memory.git
cd Mnemosyne-AI-Memory
python setup.py
```

```python
# 写入一条经验
memory_write(content="gzip 请求体必须先解压再解析 JSON",
             principle="先检查 Content-Encoding 再解析")

# 搜索记忆
memory_search(query="请求体解析失败", layer="L0")
# → 返回: "先检查 Content-Encoding 再解析"（只花 ~100 token）

# 启动时自动注入相关记忆（不用你搜，记忆找你）
memory_inject(context="API 代理项目")

# 预测式记忆：记住一条经验适用在什么条件下
memory_write(
    content="torch 2.11.0 在这个 Windows 环境会崩，改用 torch 2.6.0",
    precondition="在 Windows 上安装 torch",
    predicted_outcome="torch 2.6.0 是稳定选择"
)
```

---

## 核心能力

### 三层记忆（L0/L1/L2）

灵感来自字节跳动的 OpenViking 项目。不要把 5 万 token 的上下文全塞进去：

| 层 | 大小 | 用途 |
|---|------|------|
| **L0** 摘要 | ~100 token | 快速判断相不相关，启动时注入 |
| **L1** 概要 | ~500 token | 多数查询到这里就够了 |
| **L2** 全文 | 不限 | 真正需要细节时才展开 |

效果：**token 成本降低 83%**，检索质量不降。

### 知识图谱 + 多维检索

记忆先通过关系类型连成图，再进入正交图维度（`semantic`、`causal`、`temporal`、`entity`）做更精确的检索：

| 关系 | 含义 | 例子 |
|------|------|------|
| `is_a` | 归类到抽象原理 | "gzip 解压失败" → 是一条 → "先检查编码" |
| `similar_to` | 语义相似（向量 ≥ 0.85） | "响应乱码" ≈ "JSON 解析报错" |
| `caused` | 因果链 | "没做参数校验" → 导致 → "线上 500" |
| `solves` | 解决方案 | "加了 retry 逻辑" → 解决了 → "API 超时" |
| `contradicts` | 新经验覆盖旧经验 | "用 A 方案" ✗ "其实该用 B 方案" |
| `transfers_to` | 跨域迁移 | "Node.js 的错误处理思路" → 可迁移到 → "Python 项目" |
| `evolved_from` | 策略提炼 | 从多条经验中总结出通用策略 |

v6.1 加入 SYNAPSE 风格的扩散激活，支持 5 种搜索模式：

| 模式 | 适用场景 |
|------|----------|
| `hybrid` | 默认模式，向量 + 关键词 + 图检索融合 |
| `precise` | 保守检索，只走强连接 |
| `creative` | 发散联想，允许弱连接和 `is_a` 概念跳跃 |
| `vector` | 纯语义向量搜索 |
| `keyword` | FTS5 关键词搜索 |

### 预测式记忆

Mnemosyne 不再只是追加记录。每条经验可以声明：

| 字段 | 含义 |
|------|------|
| `precondition` | 这条经验在什么条件下适用 |
| `predicted_outcome` | 在该条件下预期会发生什么 |
| `confidence` | 可靠性分数，被验证会升高，被反例推翻会降低 |

当新经验命中旧经验的 precondition，Mnemosyne 会自动验证旧预测。新证据如果确认旧经验，就增强 confidence；如果冲突，就创建 `contradicts` 边并降低旧记忆置信度。

### 做梦（自动整合）

人脑在睡眠中整理记忆。Mnemosyne 也一样，v6.1 使用 Fast/Slow 双流做梦流水线：

| 流程 | 作用 |
|------|------|
| Fast Path | 确定性维护：衰减、同步、增量关联、索引安全清理 |
| Slow Path | 深层整合：矛盾发现、因果连接、策略提炼、可选 LLM 审查 |

v6.1 的 Dream 围绕三层仿生架构优化：

| 层 | Mnemosyne 对应组件 |
|----|-------------------|
| 海马体 | 写入时预测验证 + 自动关联 |
| REM 睡眠 | 增量发现 `similar_to` 和 `contradicts` |
| 前额叶 | 可选 LLM 辅助矛盾判断和审查 |

每天凌晨 3 点和中午 12 点自动运行。也可以手动触发：

```bash
python scripts/graph_dream.py --full
```

### 对话日志自动学习

自动扫描 opencode 对话记录，过滤噪音（闲聊、套话、系统警告），用 LLM 从有价值片段中提炼 principle 和摘要，写入记忆图谱。

你正常使用 AI，记忆自动积累。不需要手动记录。

### 隐私保护

所有自动发现的关系都经过安全审查。涉及密码、密钥、身份证等敏感信息的边会被自动否决。

---

## 接入方式

### MCP（推荐）

任何支持 MCP（Model Context Protocol，模型上下文协议）的 AI 工具都能用：

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "python",
      "args": ["scripts/mcp_server/start_mcp.py"]
    }
  }
}
```

6 个工具：`memory_write`（写入）、`memory_search`（搜索）、`memory_inject`（注入）、`memory_detail`（详情）、`memory_update`（更新）、`memory_delete`（删除）

`memory_search` 支持 `hybrid`、`precise`、`creative`、`vector`、`keyword` 五种模式，也支持 graph dimension 和标签过滤。

### REST API

```bash
python scripts/api/start_api.py --port 8979
# Swagger 文档: http://localhost:8979/docs

curl http://localhost:8979/api/health
# → {"status":"ok","nodes":0,"edges":0}

curl "http://localhost:8979/api/search?q=gzip&layer=L0&top=5"
```

### CLI

```bash
# 写入
python scripts/graph_write.py --content "经验内容" --principle "抽象原理"

# 搜索（支持语义/关键词/混合）
python scripts/graph_query.py --vector-search "关键词" --layer L0 --top 5

# 健康检查
python scripts/graph_audit.py
```

---

## 可视化面板

```bash
streamlit run scripts/dashboard/app.py --server.port 8501
```

| 页面 | 功能 |
|------|------|
| Dashboard | 节点/边统计、类型分布、记忆排行 |
| Search | 搜索 + L0→L1→L2 逐层展开 |
| Graph | D3.js 力导向图（缩放、拖拽、类型着色） |
| Dream Log | Fast/Slow 做梦记录、阶段耗时、点击展开详情 |

---

## 项目结构

```
scripts/
├── core/                # 抽象层（可替换组件）
│   ├── graph_store.py   # 图存储接口
│   ├── sqlite_store.py  # SQLite 实现（向量 + FTS5 + 图遍历）
│   ├── embedder.py      # 嵌入模型接口（Harrier/BGE-M3/Qwen）
│   └── dream_pipeline.py # Fast/Slow 做梦流水线
├── api/                 # FastAPI REST API + Swagger
├── mcp_server/          # MCP Server（6 个工具，stdio）
├── dashboard/           # Streamlit 可视化面板
├── log_scanner/         # 对话日志扫描 + 过滤 + 蒸馏
├── graph_write.py       # 写入 CLI
├── graph_query.py       # 查询 CLI
├── graph_dream.py       # 做梦 CLI
└── graph_audit.py       # 健康报告 + 清理
```

每个组件通过抽象接口可替换：
- **存储层**（GraphStore）→ SQLite / FAISS / Neo4j
- **嵌入模型**（Embedder）→ Harrier / BGE-M3 / Qwen
- **调度器**（TaskRunner）→ APScheduler / Celery

---

## 设计思路

Mnemosyne 模拟人脑的几种关键记忆机制：

**预测** — 进入相似场景时，大脑会预期接下来应该发生什么。预测式记忆用 `precondition` + `predicted_outcome` 做同样的事。

**直觉** — 走进厨房就想到"吃的"，环境自动触发记忆。启动注入做的就是这件事。

**回忆** — 别人问"上次那道菜怎么做"，你主动搜索记忆。向量搜索 + 图遍历找到经验，还能发现更深层的关联。

**做梦** — 睡眠时大脑重播事件、整合连接、修剪不用的记忆。做梦流水线做同样的事——自动的。

| 人脑 | Mnemosyne |
|------|-----------|
| 海马体快速编码 | `memory_write` 即时写入 |
| 预测编码 | `precondition` + `predicted_outcome` 验证 |
| 新皮层慢速整合 | `graph_dream` Fast/Slow 双流做梦流水线 |
| 提取时重编码 | 搜索时 touch + decay 更新 |
| REM 睡眠抽象 | 可选 LLM 三轮审查 |
| 突触修剪 | 衰减评分 + 冷归档 |
| 遗忘曲线 | `base_score × e^(-0.03 × days) × log₂(access+2)` |

---

## 配置

### LLM 审查（可选）

默认纯规则运行，不需要任何 LLM。如果想要更智能的审查，复制 `llm_config.example.json` 为 `llm_config.json`，再填入自己的 key：

```json
{
  "enabled": true,
  "endpoint": "https://api.deepseek.com/chat/completions",
  "model": "deepseek-v4-flash",
  "api_key": "your-key"
}
```

### 嵌入模型

| 模型 | 维度 | 加载速度 | 质量 | 许可证 |
|------|------|---------|------|--------|
| [Harrier 0.6b](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)（默认） | 1024 | **1.2 秒** | MTEB #1 (2026) | MIT |
| BGE-M3 | 1024 | 11 秒 | 强 | MIT |
| Qwen3-Embedding | 1024 | 中等 | 强 | Apache 2.0 |

---

## 系统要求

- Python 3.10+
- ~2GB 磁盘空间（嵌入模型）
- 可选：安装 `faiss-cpu` 获得更快的向量搜索；未安装时自动使用 numpy fallback
- 纯本地运行，不依赖外部服务

## 许可证

[MIT](LICENSE)

## 致谢

脑科学基础：
- **CLS 理论**（Complementary Learning Systems，互补学习系统）— 快/慢双记忆
- **Reconsolidation**（再巩固）— 提取时重编码
- **NREM + REM**（非快速眼动 + 快速眼动睡眠）— 两阶段记忆整合
- **Ebbinghaus 遗忘曲线** — 指数衰减 + 间隔重复

灵感来源：[OpenViking](https://github.com/bytedance/OpenViking)（L0/L1/L2 分层上下文）

---

<div align="center">

**[v6.1 Release Notes →](v6.1-release-notes.md)**

</div>
