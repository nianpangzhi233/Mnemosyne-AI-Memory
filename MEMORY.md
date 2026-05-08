# 记忆系统规则（Mnemosyne v6.1）

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

### v6.1 增强写入（Predictive Memory）

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

### v6.1 搜索模式

| mode | 说明 | 适用场景 |
|------|------|---------|
| `"hybrid"` | 向量+关键词混合（默认） | 日常问答 |
| `"precise"` | SYNAPSE 精确模式，只沿 strong 边扩散 | 需要精准答案时 |
| `"creative"` | SYNAPSE 创造模式，沿 strong+weak 边 + is_a 概念跳跃 | 需要发散联想时 |
| `"vector"` | 纯向量语义搜索 | 关键词不匹配时 |
| `"keyword"` | FTS5 关键词搜索 | 精确匹配时 |

### v6.1 标签过滤

按 project 或 task_type 过滤：
```
memory_search(query="torch", tags=["cli_tool"], mode="precise")
```

### v6.1 维度过滤

按 graph_dim 过滤：
```
memory_search(query="API issue", graph_dim="causal")
```
维度：semantic / causal / temporal / entity

## 规则 4：纠正是信号放大器

被纠正 = 你犯了错 = 这条经验权重极高。

1. 调用 `memory_write(content="正确做法", type="correction", contradicts="被纠正的节点ID")`
2. contradicts 参数会**自动降低**被纠正节点的 confidence（-0.2）

v6.1 的 Predictive Validation 会在写入时**自动检测**：如果新经验和旧 memory 的 precondition 匹配但内容矛盾 → 自动标记 contradicts 边 + 降低旧 memory 的 confidence。

## 规则 5：善用 memory_update 和 memory_delete

v6.1 支持在需要时更新或删除已有记忆：

```
// 修正某条记忆的置信度
memory_update(id="xxx", confidence=0.8)

// 更新某条记忆的标签
memory_update(id="xxx", context_tags=["python", "windows"])

// 删除完全错误的记忆
memory_delete(id="xxx")
```

## 规则 6：自检

每隔 10 轮对话，问自己一次：
- 这次会话我完成过任务吗？→ 写入（带 principle 和 precondition，如果适用）
- 我被纠正过吗？→ 写入 correction + contradicts
- 我搜过记忆吗？→ 如果没搜过，至少搜一次当前话题
- 有需要更新/删除的旧记忆吗？→ 调用 memory_update 或 memory_delete

这个自检不需要对用户说，默默执行即可。
