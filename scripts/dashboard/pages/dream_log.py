import streamlit as st
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from dashboard.store import get_store
from dashboard.style import KIMI_DARK, KIMI_GRAY

store = get_store()

STATUS_LABELS = {"PASS": "通过", "WARN": "警告", "FAIL": "失败", "unknown": "未知"}
PHASE_LABELS = {
    "Snapshot": "快照",
    "LogScan": "日志扫描",
    "SimilarTo": "相似关系",
    "Causal": "因果关系",
    "Concept": "概念层",
    "Contradicts": "矛盾检测",
    "Transfers": "迁移关系",
    "SkillEmbryo": "技能胚胎",
    "SkillDevelopment": "技能开发",
    "SkillMirror": "技能镜像",
    "Strategy": "策略提炼",
    "Covenant": "安全约束",
    "Decay": "衰减更新",
    "LLM": "模型复核",
    "Distill": "经验蒸馏",
    "Sync": "同步",
    "Audit": "审计",
}


def phase_display_name(name: str) -> str:
    if not name:
        return "未知阶段"
    for key, label in PHASE_LABELS.items():
        if key.lower() in name.lower():
            return label
    return name


def normalize_result(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"raw": result}
    return {"raw": result}


def result_sentence(name: str, result: dict) -> tuple[str, str, str]:
    label = phase_display_name(name)
    low = (name or "").lower()
    status = "完成"
    tone = "pill-green"
    detail = "这个阶段完成了，但没有额外变化。"

    if "snapshot" in low or "预" in name:
        detail = f"开始整理前，图谱里有 {result.get('nodes_before', '?')} 个节点、{result.get('edges_before', '?')} 条边。"
    elif "logscan" in low or "ɨ" in name or "扫描" in name:
        written = result.get("written", 0)
        scanned = result.get("scanned_fragments", result.get("scanned_sessions", 0))
        added = result.get("added", 0)
        new_nodes = result.get("new_nodes", 0)
        if written or added or new_nodes:
            parts = []
            if written:
                parts.append(f"写入 {written} 条原始记忆")
            if scanned:
                parts.append(f"扫描 {scanned} 个片段")
            if added:
                parts.append(f"新增 {added} 条关系")
            if new_nodes:
                parts.append(f"发现 {new_nodes} 个新节点")
            detail = "扫描日志后" + "，".join(parts) + "。"
            status = f"+{written}"
            tone = "pill-green"
        else:
            detail = "扫描日志完成，没有发现需要新增的记忆。"
            status = "无新增"
            tone = "pill-gray"
    elif "similar" in low:
        added = result.get("added", 0)
        detail = f"为相近记忆补充了 {added} 条相似关系。" if added else "没有发现新的相似关系。"
        if not added:
            status = "无新增"
            tone = "pill-gray"
    elif "decay" in low or "˥" in name:
        updated = result.get("updated", 0)
        detail = f"重新计算了 {updated} 个记忆节点的热度和衰减分数。"
    elif "covenant" in low:
        checked = result.get("checked", 0)
        vetoed = result.get("vetoed", 0)
        detail = f"安全约束检查了 {checked} 条关系，否决了 {vetoed} 条可疑关系。"
        if vetoed:
            status = "有拦截"
            tone = "pill-amber"
    elif "memory.md" in low or "sync" in low or "ͬ" in name:
        synced = result.get("synced", 0)
        detail = f"同步了 {synced} 条热记忆到活跃记忆文件。"
    elif "audit" in low:
        checked = result.get("checked", result.get("audited", 0))
        issues = result.get("issues", result.get("vetoed", 0))
        detail = f"审计了 {checked} 项内容，发现 {issues} 个需要关注的问题。"
        if issues:
            status = "需关注"
            tone = "pill-amber"
    elif "final" in low or "����" in name or "总结" in name:
        status_value = result.get("status", "PASS")
        alerts = result.get("alerts") or []
        detail = f"整理结束后，图谱有 {result.get('nodes_after', '?')} 个节点、{result.get('edges_after', '?')} 条边。"
        if alerts:
            detail += f" 有 {len(alerts)} 条提醒需要查看。"
            tone = "pill-amber"
        status = STATUS_LABELS.get(status_value, status_value)
        if status_value not in {"PASS", "ok", "OK"}:
            tone = "pill-amber"
    else:
        readable = []
        for key, value in result.items():
            if key == "raw":
                continue
            readable.append(f"{key}={value}")
        detail = "，".join(readable) if readable else "这个阶段没有记录额外变化。"

    return label, status, tone, detail


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_report_items(title, items, limit=6):
    if not items:
        return
    st.markdown(f"**{title}**")
    for item in items[:limit]:
        evidence_ids = item.get("evidence_ids") or []
        target_id = item.get("target_id") or ""
        with st.container(border=True):
            st.markdown(f"**{_safe_text(item.get('title') or item.get('type'))}**")
            if item.get("reason"):
                st.caption(_safe_text(item.get("reason")))
            if item.get("suggested_action"):
                st.info(_safe_text(item.get("suggested_action")))
            meta = []
            if target_id:
                meta.append(f"target `{target_id}`")
            if evidence_ids:
                meta.append("evidence " + ", ".join(f"`{eid}`" for eid in evidence_ids[:6]))
            if meta:
                st.caption(" · ".join(meta))

lang = st.session_state.get("lang", "zh")
T = {
    "zh": {
        "title": "做梦日志", "no_logs": "暂无做梦记录。运行 graph_dream.py --full 后自动生成。",
        "quick_stats": "快速统计", "strategies": "策略数", "vetoed": "已否决边", "total_nodes": "总节点",
        "details": "详情",
    },
    "en": {
        "title": "Dream Log", "no_logs": "No dream logs found. Dreams are logged when graph_dream.py --full runs.",
        "quick_stats": "Quick Stats", "strategies": "Strategies", "vetoed": "Vetoed Edges", "total_nodes": "Total Nodes",
        "details": "Details",
    },
}[lang]

st.title(T["title"])
st.caption("这里记录夜间整理过程，出问题时先看这里，不要猜。")

st.markdown(
    """
    <script>
    setTimeout(function(){ window.location.reload(); }, 30000);
    </script>
    """,
    unsafe_allow_html=True,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
db_path = PROJECT_ROOT / "graph.db"
log_db_path = PROJECT_ROOT / "dream_log.db"

def get_dream_logs():
    logs = []
    if not log_db_path.exists():
        return logs
    conn = sqlite3.connect(str(log_db_path))
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM dreams ORDER BY started_at DESC LIMIT 50")
        for row in cur.fetchall():
            logs.append(dict(row))
    except Exception:
        pass
    finally:
        conn.close()
    return logs


def get_latest_report():
    if not log_db_path.exists():
        return None
    conn = sqlite3.connect(str(log_db_path))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM evolution_reports ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["report"] = json.loads(data.get("report") or "{}")
        except (json.JSONDecodeError, TypeError):
            data["report"] = {}
        return data
    except sqlite3.Error:
        return None
    finally:
        conn.close()

logs = get_dream_logs()
latest_report = get_latest_report()

top_cols = st.columns([1, 1, 2])
with top_cols[0]:
    if st.button("刷新日志", use_container_width=True):
        st.rerun()
with top_cols[1]:
    st.caption(f"页面刷新：{datetime.now().strftime('%H:%M:%S')}")
with top_cols[2]:
    if logs:
        latest = logs[0]
        latest_time = (latest.get("started_at") or "")[:19].replace("T", " ")
        st.caption(f"最新做梦：{latest_time} · {STATUS_LABELS.get(latest.get('status'), latest.get('status'))}")

if not logs:
    st.info(T["no_logs"])
    dream_stats = store.query_nodes("type='strategy'")
    vetoed = store.count_edges_where("status='vetoed'")
    st.markdown(f"### {T['quick_stats']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(T["strategies"], len(dream_stats))
    with col2:
        st.metric(T["vetoed"], vetoed)
    with col3:
        st.metric(T["total_nodes"], store.count_nodes())
    st.stop()

if latest_report:
    report = latest_report.get("report") or {}
    warnings = report.get("warnings") or []
    highlights = report.get("highlights") or []
    sections = report.get("sections") or {}
    reviewable_counts = report.get("reviewable_counts") or {}
    with st.expander("最近一次学习报告", expanded=False):
        st.write(report.get("summary") or latest_report.get("summary"))
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("状态", report.get("status", "unknown"))
        c2.metric("节点变化", report.get("node_delta", 0))
        c3.metric("边变化", report.get("edge_delta", 0))
        c4.metric("耗时 ms", int(report.get("duration_ms") or 0))
        c5.metric("待审阅", sum(int(v or 0) for v in reviewable_counts.values()))
        if highlights:
            st.markdown("**Highlights**")
            for item in highlights[:6]:
                st.caption(item)
        if warnings:
            st.markdown("**Warnings**")
            for item in warnings[:6]:
                st.warning(item)
        if sections:
            st.markdown("### 可审阅证据链")
            _render_report_items("推荐动作", sections.get("recommended_actions") or [], limit=8)
            _render_report_items("新记忆", sections.get("new_memories") or [])
            _render_report_items("新概念", sections.get("new_concepts") or [])
            _render_report_items("新技能候选", sections.get("new_skills") or [])
            _render_report_items("技能状态变化", sections.get("skill_changes") or [])
            _render_report_items("矛盾证据", sections.get("contradictions") or [])

for log in logs:
    started = log.get("started_at", "")[:19].replace("T", " ")
    status = log.get("status", "unknown")
    nodes_before = log.get("nodes_before", "?")
    nodes_after = log.get("nodes_after", "?")
    edges_before = log.get("edges_before", "?")
    edges_after = log.get("edges_after", "?")

    delta_n = ""
    if isinstance(nodes_before, int) and isinstance(nodes_after, int):
        d = nodes_after - nodes_before
        delta_n = f"<span style='color:{'#34c759' if d >= 0 else '#ff3b30'}'>{'+' if d >= 0 else ''}{d}</span>"

    status_color = "#34c759" if status == "PASS" else "#ff9500" if status == "WARN" else "#ff3b30"

    phases_data = []
    try:
        phases_data = json.loads(log.get("phases", "[]"))
    except (json.JSONDecodeError, TypeError):
        pass

    st.markdown(f"""
    <div class="kimi-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-weight:600; font-size:1rem;">🌙 {started}</span>
                <span class="kimi-badge" style="background:{status_color}20; color:{status_color}; margin-left:8px;">{STATUS_LABELS.get(status, status)}</span>
            </div>
            <div style="display:flex; gap:16px; font-size:0.8rem; color:{KIMI_GRAY};">
        <span>节点：{nodes_before} → {nodes_after} {delta_n}</span>
        <span>边：{edges_before} → {edges_after}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if phases_data:
        cells_html = ""
        for phase_info in phases_data:
            name = phase_info.get("name", "")
            result = normalize_result(phase_info.get("result", {}))
            status = result.get("status")
            changed = result.get("added", result.get("updated", result.get("synced", result.get("written", result.get("checked", 0)))))
            css_cls = "phase-ok" if changed or status in {"PASS", "done"} else "phase-skip"
            if status in {"WARN", "ERROR", "FAIL"} or result.get("alerts"):
                css_cls = "phase-warn"
            label = str(changed or status or 0)
            phase_label = phase_display_name(name)
            cells_html += f'<div class="phase-cell {css_cls}" title="{phase_label}: {label}">{phase_label[:2]}</div>'

        st.markdown(f'<div class="phase-bar">{cells_html}</div>', unsafe_allow_html=True)

    with st.expander(T["details"], expanded=False):
        if phases_data:
            st.markdown('<div class="dream-diary">', unsafe_allow_html=True)
            for idx, p in enumerate(phases_data, start=1):
                name = p.get("name", "?")
                result = normalize_result(p.get("result", {}))
                phase_name, phase_status, phase_tone, detail = result_sentence(name, result)
                extra_bits = []
                if p.get("phase") is not None:
                    extra_bits.append(f"第 {p.get('phase')} 阶段")
                if p.get("duration_ms"):
                    extra_bits.append(f"耗时 {p.get('duration_ms')} ms")
                if result.get("raw"):
                    extra_bits.append(f"原始信息：{str(result.get('raw'))[:80]}")
                extra_line = " · ".join(extra_bits)
                st.markdown(
                    f"""
                    <div class="dream-diary-item">
                        <div class="dream-diary-index">{idx}</div>
                        <div>
                            <div class="dream-diary-title">
                                <strong>{phase_name}</strong>
                                <span class="mn-pill {phase_tone}">{phase_status}</span>
                            </div>
                            <div class="dream-diary-body">{detail}</div>
                            {f'<div class="dream-diary-muted">{extra_line}</div>' if extra_line else ''}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.caption("没有可展开的阶段详情。")

    st.markdown("</div>", unsafe_allow_html=True)
