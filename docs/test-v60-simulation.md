# Mnemosyne v6.0 Simulation Test Plan

> Date: 2026-05-07 | Status: Active
> Goal: 用真实数据模式模拟完整用户场景，验证 v6.0 全链路

---

## 1. Test Strategy

模拟陛下的真实使用场景：日常编码 → 做梦 → 检索 → 矛盾发现 → 记忆进化。

**不测**：LLM 相关 Phase（DistillPhase/LLMReviewPhase/LogScanPhase 需要外部 API）
**重点测**：数据完整性、检索质量、矛盾生命周期、衰减公式、Dream Fast Path

---

## 2. Test Data Design

### 2.1 种子数据（20 条记忆，模拟 2 周使用）

| # | Content | Type | Principle | Precondition | Predicted Outcome | Task Type | Project |
|---|---------|------|-----------|-------------|-------------------|-----------|---------|
| S1 | torch 2.11.0 DLL crash on Windows, use 2.6.0 instead | experience | torch version DLL crash on Windows | installing torch on Windows | torch 2.6.0 is the only stable version | cli_tool | WorkBuddy |
| S2 | pip install faiss-cpu timeout on Windows, use numpy fallback | experience | faiss-cpu install timeout on Windows | installing faiss on Windows | numpy brute-force works as fallback | cli_tool | Mnemosyne |
| S3 | gzip request body needs gunzip before JSON parse | experience | check Content-Encoding before parsing | receiving HTTP request with gzip | need to decompress before parsing | api_proxy | WorkBuddy |
| S4 | DeepSeek API must disable thinking mode with type:disabled | experience | disable thinking mode for DeepSeek | calling DeepSeek API | response returns without reasoning tokens | api_proxy | WorkBuddy |
| S5 | Vue 3 props need defineProps with TypeScript, not Options API | experience | use Composition API for Vue 3 | writing Vue 3 component | props defined via defineProps | frontend | ForestView |
| S6 | PIXI.js v7 uses Application.init() not constructor | experience | PIXI v7 async init pattern | setting up PIXI application | use Application.init() async method | frontend | ForestView |
| S7 | SQLite WAL mode for concurrent read/write | principle | use WAL mode for SQLite concurrency | | | database | Mnemosyne |
| S8 | Harrier embedding model loads 10x faster than BGE-M3 | experience | Harrier faster than BGE-M3 | loading embedding model | Harrier loads in <2 seconds | cli_tool | Mnemosyne |
| S9 | npm run dev on port 5173, FastAPI on 8000 | principle | dev server port conventions | | | config | WorkBuddy |
| S10 | Student praise: name + action + praise word | principle | praise structure for students | | | teaching | Classroom |
| S11 | torch 2.6.0 is stable and working perfectly | experience | torch version DLL crash on Windows | installing torch on Windows | torch 2.6.0 is the only stable version | cli_tool | WorkBuddy |
| S12 | PixiJS loader deprecated in v7, use Assets class | experience | PIXI v7 Assets replaces loader | loading assets in PIXI v7 | use PIXI.Assets.load() instead | frontend | ForestView |
| S13 | SSE streaming needs proper \\n\\n delimiter | experience | SSE delimiter format | implementing SSE stream | use double newline as message delimiter | api_proxy | WorkBuddy |
| S14 | Criticism levels: name only (light) / +action (medium) / +word (heavy) | principle | criticism levels for students | | | teaching | Classroom |
| S15 | BGE-M3 via hf-mirror.com works with HF_ENDPOINT | experience | hf-mirror for Chinese users | downloading huggingface model | set HF_ENDPOINT=https://hf-mirror.com | cli_tool | Mnemosyne |
| S16 | torch 2.5.1 security reject, cannot use | experience | torch version DLL crash on Windows | installing torch on Windows | torch 2.6.0 is the only stable version | cli_tool | WorkBuddy |
| S17 | Correction: torch 2.6.0 also crashes on some AMD GPUs | correction | torch version issue | installing torch on AMD GPU | may need ROCm build instead | cli_tool | WorkBuddy |
| S18 | npm run build fails if TypeScript strict mode enabled | experience | TypeScript strict mode pitfall | building Vue project | disable strict or fix all type errors | frontend | ForestView |
| S19 | 47 students in class, 12 praises per lesson | principle | classroom statistics | | | teaching | Classroom |
| S20 | Dream scheduled at 3:00 and 12:00 with HF_ENDPOINT | principle | dream schedule config | | | config | Mnemosyne |

### 2.2 矛盾对（预期触发 contradicts 边）

| Pair | A | B | Why Contradiction |
|------|---|---|-------------------|
| C1 | S1 (torch 2.11 crash) | S11 (torch 2.6.0 works) | same precondition, different outcomes |
| C2 | S1 (torch 2.11 crash) | S17 (torch 2.6.0 also crashes on AMD) | S17 corrects S11's conclusion |

### 2.3 预期 is_a 边（共享 principle）

| Principle | Nodes |
|-----------|-------|
| torch version DLL crash on Windows | S1, S11, S16 |
| check Content-Encoding before parsing | S3 |
| disable thinking mode for DeepSeek | S4 |

---

## 3. Test Scenarios

### T1: Full Write Lifecycle

**Setup**: 写入 S1-S20
**Verify**:
- [ ] At least 8 unique nodes created from 10 writes (principle merges are expected)
- [ ] Each node has: confidence=1.0, verified_count=0, half_life_days by type, context_tags auto-populated
- [ ] S1/S11/S16 merge (same principle "torch version DLL crash on Windows") → should boost base_score
- [ ] precondition_vec non-null for S1-S6, S8, S12-S13, S15-S17
- [ ] is_a edges auto-created for principle groups

### T2: Predictive Validation

**Steps**:
1. S1 has precondition="installing torch on Windows", predicted_outcome="torch 2.6.0 is the only stable version"
2. S11 has same precondition, content confirms 2.6.0 works → should **verify** S1
3. S17 has correction saying 2.6.0 also crashes → should **contradict** relevant nodes

**Verify**:
- [ ] After S11: S1 (or merged node) verified_count >= 1
- [ ] After S17: contradicts edge created, confidence decreased

### T3: Dual-Channel Search

**Query**: "torch installation problem"
**Precise mode**: expect S1/S11/S16 (torch related, strong edges only)
**Creative mode**: expect S1/S11/S16 + S2 (faiss, also cli_tool) + S8 (embedding model loading)

**Verify**:
- [ ] precise returns fewer results
- [ ] creative returns more diverse results
- [ ] both return torch-related as top results

### T4: Tag Filtered Search

**Query**: "installation guide" with tags=["cli_tool"]
**Expected**: S1, S2, S8, S15 (all cli_tool + installation-related)

**Verify**:
- [ ] Only cli_tool tagged results returned
- [ ] No teaching/config/frontend results

### T5: Precondition Match (Predictive Retrieval)

**Context**: "trying to install faiss on Windows for vector search"
**Expected**: Match S2's precondition="installing faiss on Windows"

**Verify**:
- [ ] match_preconditions returns S2
- [ ] predicted_outcome="numpy brute-force works as fallback" included
- [ ] Similarity > 0.6

### T6: Decay Formula

**Setup**: Write nodes, manually set some as "old" (update last_access to 30/60/90 days ago)
**Formula**: `new_decay = base * exp(-ln2 * days / adjusted_half_life) * log2(access+2) * type_weight * confidence`
- adjusted_half_life = half_life * (1 + log(verified_count + 1))

**Verify**:
- [ ] Hot node (verified 5 times, 10 days old) stays hot
- [ ] Cold node (0 verifications, 90 days old, type=raw) goes cold
- [ ] Principle node decays slower than experience (half_life 90 vs 30)

### T7: Dream Fast Path

**Steps**: Run Dream with --no-slow
**Phases**: Snapshot → SimilarTo → Decay → Covenant → Sync

**Verify**:
- [ ] SimilarTo finds similar_to edges (S1≈S11, S3≈S13, etc.)
- [ ] Decay updates tiers correctly
- [ ] Covenant vetoes no edges (no privacy keywords in test data)
- [ ] Sync generates hot/memory.md
- [ ] Dream log in dream_log.db
- [ ] Completes in < 30 seconds

### T8: Semantic Contradiction Detection (ContradictsPhase)

**Steps**: Run Dream full (with Slow Path, but LLM phases may fail — that's OK)
**Verify**:
- [ ] S1 vs S17 detected as semantic opposition (torch crash vs also crashes)
- [ ] contradicts edge created
- [ ] A-MEM evolution: old node confidence -0.2

### T9: Migration Verification (Already Done)

**Verify**:
- [x] 203→204 nodes preserved (migration +1 from test)
- [x] 387 edges preserved
- [x] All new fields populated
- [x] meta version = 6.0.0
- [x] meta.json version = 6.0.0

### T10: Performance Benchmark

**Metrics** (with 220+ nodes after test data):
- [ ] add_node < 2s
- [ ] search_spreading < 500ms
- [ ] search_hybrid < 500ms
- [ ] match_preconditions < 200ms
- [ ] Dream Fast Path < 30s

---

## 4. Pass/Fail Criteria

| Level | Condition |
|-------|-----------|
| PASS | All T1-T10 checks pass |
| PASS WITH NOTES | Core checks pass, performance slightly over threshold |
| FAIL | Data integrity check fails (wrong node count, missing fields) |
| FAIL | Contradiction lifecycle broken (no contradicts edge when expected) |
| FAIL | Search returns empty when results expected |

---

## 5. Execution Plan

```
1. Write test data (S1-S20) → verify T1 + T2
2. Run search tests (T3 + T4 + T5)
3. Run Dream Fast Path (T6 + T7)
4. Run Dream Slow Path for contradiction (T8)
5. Run performance benchmarks (T10)
6. Generate report
```

---

## 6. Cleanup

After test:
- Delete all test nodes (tagged with project="simtest")
- Run Dream to recalculate
- Verify node count returns to pre-test level
