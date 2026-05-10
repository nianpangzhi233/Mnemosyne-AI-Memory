# 记忆系统规则（Mnemosyne v7.0）

CRITICAL: 此文件是强制规则，不是建议。每次会话都必须遵循。

## 规则 1：启动注入

每个新会话的**第一条操作**就是调用 memory_inject，没有任何例外：

```
memory_inject(context="当前工作目录或任务描述", max_chars=300)
```

memory_inject 会返回相关历史记忆 + 环境预警（precondition 匹配）。

## 规则 2：写入触发

### 必须写入的 3 个信号

以下信号出现时，**立即写入**，不要犹豫：

| 信号 | 触发词（用户说的话） | 操作 |
|------|---------------------|------|
| 任务完成 | "好了""没问题了""OK""下一步""继续" | `memory_write(content="做了什么+结果", type="experience", principle="规律")` |
| 被纠正 | "不对""不是这样""应该是""错了" | `memory_write(content="正确做法", type="correction", contradicts="被纠正的节点ID")` |
| 新经验 | 你刚解决了一个非显然的技术问题 | `memory_write(content="经验", type="experience", principle="原理")` |

### v7.0 增强写入（Predictive Memory）

如果经验有**触发条件**和**预期结果**，使用 precondition 和 predicted_outcome：

```
memory_write(
  content="torch 2.11.0 DLL crash on Windows, use 2.6.0 instead",
  type="experience",
  principle="torch version DLL crash on Windows",
  precondition="installing torch on Windows",
  predicted_outcome="torch 2.6.0 is the only stable version"
)
```

### v7.1 task_type 分类（必须填）

每次写入记忆时，**必须填写 `task_type` 字段**，将经验归类到技术领域。
已知类型：`api_proxy`、`memory_system`、`cli_tool`、`coding`、`testing`、`debugging`、`visual_design`、`workflow`、`llm_integration`、`electron_dev`、`skill_memory`、`skill_feedback`。
如果没有合适的，自己造一个 snake_case 的新类型名。

```
memory_write(
  content="gzip body must be decompressed before JSON.parse",
  task_type="api_proxy",
  principle="check Content-Encoding first"
)
```

这会启用**预测性记忆**——下次遇到相同 precondition 时，memory_inject 会自动预警。

### 不要写入

- 闲聊、问候、纯问答
- 任务还没做完（等到做完）
- 你不确定是否有价值（宁可先写，做梦时会自动清理）

## 规则 3：先搜再答

遇到技术问题时，**先搜记忆再回答**：

```
memory_search(query="问题关键词", top=5, layer="L0", mode="hybrid")
```

### v7.0 搜索模式

| mode | 说明 | 适用场景 |
|------|------|---------|
| `"hybrid"` | 向量+关键词混合（默认） | 日常问答 |
| `"precise"` | SYNAPSE 精确模式，只沿 strong 边扩散 | 需要精准答案时 |
| `"creative"` | SYNAPSE 创造模式，沿 strong+weak 边 + is_a 概念跳跃 | 需要发散联想时 |
| `"vector"` | 纯向量语义搜索 | 关键词不匹配时 |
| `"keyword"` | FTS5 关键词搜索 | 精确匹配时 |

### v7.0 标签过滤

按 project 或 task_type 过滤：
```
memory_search(query="torch", tags=["cli_tool"], mode="precise")
```

### v7.0 维度过滤

按 graph_dim 过滤：
```
memory_search(query="API issue", graph_dim="causal")
```
维度：semantic / causal / temporal / entity

## 规则 4：纠正是信号放大器

被纠正 = 你犯了错 = 这条经验权重极高。

1. 调用 `memory_write(content="正确做法", type="correction", contradicts="被纠正的节点ID")`
2. contradicts 参数会**自动降低**被纠正节点的 confidence（-0.2）

v7.0 的 Predictive Validation 会在写入时**自动检测**：如果新经验和旧 memory 的 precondition 匹配但内容矛盾 → 自动标记 contradicts 边 + 降低旧 memory 的 confidence。

## 规则 5：Skill Memory 使用规则

v7.1 使用双边 Skill Evolution。Skill 是高权重长期能力，不是普通记忆摘要。

生命周期：

```
embryo -> draft -> tested -> evolved -> approved -> deprecated
```

`evolved` 的含义是双边通过：

```
Darwin live tests improved behavior AND Mnemosyne graph governance passed
```

禁止把 dry-run、字段完整度、单次局部胜利包装成 `evolved`。失败的真实评测必须允许把 Skill 降级为 `needs_revision`。

默认注入只允许：

```
status=approved AND inject_enabled=true AND 存在 verified_by 边
```

使用规则：

- 每次新会话先 `memory_inject(context="当前工作目录或任务描述")`，再视当前任务调用 `memory_skill_inject(context="当前任务")`。
- 需要解决具体任务时，可先 `memory_skill_inject(context="当前任务")` 获取已批准 Skill。
- 想探索未批准 Skill，必须显式用 `mode="experimental"`，并清楚标记其状态。
- 低风险 `evolved` 试用必须走 `mode="trial"`，并在任务结束调用 `memory_skill_feedback`。
- 默认注入后如果结果正确、部分正确、没帮上忙、误导或触发错误，结束任务时都要写反馈；不要只在成功时反馈。
- `memory_skill_feedback` 优先填写 `outcome`，旧 `rating` 只作为兼容字段：`success / partial / miss / misleading / trigger_mismatch`。
- 如果反馈里有可复现失败，优先 `create_test_prompt=true`，并补 `expected`、`prompt_tags`。
- `verified_by` 必须来自真实 full_test、真实任务反馈或明确用户确认，禁止为了过线伪造证据。
- 不要用 `memory_update` 手改 Skill 状态；批准必须走 `memory_skill_approve`，反馈必须走 `memory_skill_feedback`，废弃必须走 `memory_skill_deprecate`。

Skill 工具：

```
memory_crystallize       # 经验节点 -> skill embryo/draft
memory_skill_search      # 搜索所有 Skill，不代表可注入
memory_skill_inject      # 安全注入，默认只给 approved
memory_skill_approve     # 批准，强制 verified_by
memory_skill_feedback    # 反馈闭环，写边和计数，支持 outcome / create_test_prompt
memory_skill_deprecate   # 软废弃，保留证据链
```

OpenCode 行为要求：

- 看到当前任务可能受已有 Skill 影响时，先 `memory_skill_inject`，别凭感觉硬写。
- 任务结束时，如果实际用到了 Skill，必须补 `memory_skill_feedback`，哪怕结果是失败。
- 如果同一个失败模式连续出现，把它转成测试题，而不是只在聊天里口头记住。
- 不要把 `approved` 当成永远正确；approved 也允许被抽测和降级。

## 规则 6：善用 memory_update 和 memory_delete

v7.0 支持在需要时更新或删除已有记忆：

```
// 修正某条记忆的置信度
memory_update(id="xxx", confidence=0.8)

// 更新某条记忆的标签
memory_update(id="xxx", context_tags=["python", "windows"])

// 删除完全错误的记忆
memory_delete(id="xxx")
```

## 规则 7：自检

每隔 10 轮对话，问自己一次：
- 这次会话我完成过任务吗？→ 写入（带 principle 和 precondition，如果适用）
- 我被纠正过吗？→ 写入 correction + contradicts
- 我搜过记忆吗？→ 如果没搜过，至少搜一次当前话题
- 有需要更新/删除的旧记忆吗？→ 调用 memory_update 或 memory_delete

这个自检不需要对用户说，默默执行即可。
