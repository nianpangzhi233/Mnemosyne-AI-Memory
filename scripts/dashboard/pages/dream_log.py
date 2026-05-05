import streamlit as st
import json
import sqlite3
from pathlib import Path
from dashboard.store import get_store
from dashboard.style import KIMI_DARK, KIMI_GRAY

store = get_store()

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

db_path = Path(__file__).resolve().parent.parent.parent / "graph.db"
log_db_path = Path(__file__).resolve().parent.parent.parent / "dream_log.db"

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

logs = get_dream_logs()

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

PHASE_NAMES = [
    "Snapshot", "LogScan", "SimilarTo", "Causal", "Contradicts",
    "Transfers", "Strategy", "Covenant", "Decay", "LLM", "Distill", "Sync", "Audit"
]

PHASE_COLORS = [
    "#0071e3", "#5ac8fa", "#34c759", "#ff3b30", "#ff9500",
    "#af52de", "#ff2d55", "#5856d6", "#8e8e93", "#0071e3", "#5ac8fa", "#34c759", "#ff3b30"
]

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
                <span class="kimi-badge" style="background:{status_color}20; color:{status_color}; margin-left:8px;">{status}</span>
            </div>
            <div style="display:flex; gap:16px; font-size:0.8rem; color:{KIMI_GRAY};">
                <span>Nodes: {nodes_before} → {nodes_after} {delta_n}</span>
                <span>Edges: {edges_before} → {edges_after}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if phases_data:
        cells_html = ""
        for pi, pname in enumerate(PHASE_NAMES):
            phase_info = None
            for p in phases_data:
                if pname.lower() in p.get("name", "").lower() or str(pi + 1) == str(p.get("phase", "")):
                    phase_info = p
                    break

            if phase_info:
                result = phase_info.get("result", {})
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except:
                        result = {}

                added = result.get("added", result.get("updated", result.get("synced", result.get("checked", ""))))
                css_cls = "phase-ok" if added else "phase-skip"
                label = str(added) if added else "0"
            else:
                css_cls = "phase-skip"
                label = "–"

            cells_html += f'<div class="phase-cell {css_cls}" title="{pname}: {label}">{pname[:3]}</div>'

        st.markdown(f'<div class="phase-bar">{cells_html}</div>', unsafe_allow_html=True)

    expand_key = f"dream_expand_{log.get('id', started)}"
    if st.button(T["details"], key=expand_key):
        st.session_state[expand_key] = st.session_state.get(expand_key, 0) + 1

    if st.session_state.get(expand_key, 0) % 2 == 1 and phases_data:
        for p in phases_data:
            name = p.get("name", "?")
            result = p.get("result", {})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    result = {"raw": result}
            st.markdown(f"**{name}**: `{json.dumps(result, ensure_ascii=False)[:120]}`")

    st.markdown("</div>", unsafe_allow_html=True)
