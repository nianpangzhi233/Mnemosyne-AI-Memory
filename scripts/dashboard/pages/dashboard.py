import json
import sqlite3
from html import escape
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from dashboard.store import get_store
from dashboard.style import EDGE_COLORS, KIMI_GRAY, TYPE_COLORS


store = get_store()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DREAM_LOG_DB = PROJECT_ROOT / "dream_log.db"

if "dashboard_search" not in st.session_state:
    st.session_state.dashboard_search = ""


def _safe_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _time_ago(iso_value: str) -> str:
    if not iso_value:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
    except ValueError:
        return iso_value[:19].replace("T", " ")
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "刚刚"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小时前"
    days = hours // 24
    return f"{days} 天前"


def _time_full(iso_value: str) -> str:
    if not iso_value:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso_value[:19].replace("T", " ")


def _latest_dream():
    if not DREAM_LOG_DB.exists():
        return None
    conn = sqlite3.connect(str(DREAM_LOG_DB))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM dreams ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _meta_value(key: str):
    conn = sqlite3.connect(str(Path(__file__).resolve().parent.parent.parent.parent / "graph.db"))
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _metric(label, value, hint="", tone=""):
    st.markdown(
        f"""
        <div class="mn-metric">
            <div class="label">{label}</div>
            <div class="value" style="{tone}">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _pill(text, cls="pill-gray"):
    return f'<span class="mn-pill {cls}">{text}</span>'


def _html(value: str) -> str:
    return escape(value or "", quote=True)


def _label(value: str) -> str:
    labels = {
        "approved": "已批准",
        "evolved": "已演化",
        "draft": "草稿",
        "tested": "已测试",
        "embryo": "胚胎",
        "needs_revision": "需修订",
        "deprecated": "已废弃",
        "hot": "热",
        "warm": "温",
        "cold": "冷",
        "none": "无记录",
        "unknown": "未知",
        "PASS": "通过",
        "WARN": "警告",
        "FAIL": "失败",
        "high": "高",
        "medium": "中",
        "low": "低",
    }
    return labels.get(value or "", value or "未知")


nodes = store.query_nodes()
edges = store.query_edges("status='active'")
skills = store.list_skill_artifacts() if hasattr(store, "list_skill_artifacts") else []
latest_dream = _latest_dream()
latest_skill_auto_loop_raw = _meta_value("last_skill_auto_loop")
latest_skill_auto_loop = _safe_json(latest_skill_auto_loop_raw, {}) if latest_skill_auto_loop_raw else {}

node_total = len(nodes)
edge_total = len(edges)
hot_total = sum(1 for node in nodes if node.get("tier") == "hot")
correction_total = sum(1 for node in nodes if node.get("type") == "correction")
approved_skills = [skill for skill in skills if skill.get("status") == "approved"]
audit_skills = []
for skill in skills:
    if skill.get("status") in {"approved", "evolved"}:
        audit = store.should_audit_skill(skill["node_id"])
        if audit.get("audit_required"):
            audit_skills.append((skill, audit))

types = {}
for node in nodes:
    node_type = node.get("type") or "unknown"
    types[node_type] = types.get(node_type, 0) + 1

edge_types = {}
for edge in edges:
    relation = edge.get("relation_type") or "unknown"
    edge_types[relation] = edge_types.get(relation, 0) + 1

recent_nodes = sorted(
    nodes,
    key=lambda node: node.get("created_at") or node.get("updated_at") or "",
    reverse=True,
)[:6]
top_nodes = store.get_top_hot_nodes(limit=6)

dream_status = latest_dream.get("status") if latest_dream else "none"
dream_started = latest_dream.get("started_at") if latest_dream else ""
dream_hint = _time_ago(dream_started) if dream_started else "暂无做梦记录"
dream_cls = "pill-green" if dream_status == "PASS" else "pill-amber" if dream_status in {"WARN", "none"} else "pill-red"

st.markdown(
    f"""
    <div class="mn-hero">
        <div class="mn-row" style="align-items:flex-start;">
            <div>
                <div style="margin-bottom:12px;">
                    {_pill('记忆系统', 'pill-blue')}
                    {_pill(f'做梦 {_label(dream_status)}', dream_cls)}
                    {_pill(f'{len(approved_skills)} 个已批准技能', 'pill-green')}
                </div>
                <h1>Mnemosyne 控制台</h1>
                <p style="max-width:760px; margin-top:12px;">
                    这里不是炫技看板，是每天真正要用的驾驶舱：看系统健康、查记忆、盯技能证据流、确认做梦是否正常。
                </p>
            </div>
            <div style="text-align:right; min-width:180px; color:{KIMI_GRAY}; font-size:0.85rem; line-height:1.7;">
                <div>项目根目录</div>
                <strong style="color:#17181c;">{PROJECT_ROOT.name}</strong>
                <div style="margin-top:10px;">最近一次做梦</div>
                <strong style="color:#17181c;">{dream_hint}</strong>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="mn-panel" style="margin-bottom:16px;">
        <div class="mn-row">
            <div>
                <div style="font-size:0.82rem; color:#6e6e73; margin-bottom:6px;">今日工作台</div>
                <div style="font-size:1.15rem; font-weight:700; color:#17181c;">先看状态，再查记忆，最后看技能和做梦</div>
            </div>
            <div style="text-align:right; color:#6e6e73; font-size:0.82rem; line-height:1.6;">
                <div>默认动作：搜索、跳转、展开</div>
                <div>尽量不让用户猜下一步该点什么</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("dashboard_search_form", clear_on_submit=False):
    search_query = st.text_input(
        "搜索记忆",
        placeholder="按关键词、原理或内容片段搜索...",
        label_visibility="collapsed",
        value=st.session_state.dashboard_search,
    )
    search_cols = st.columns([1, 1, 2])
    submitted = search_cols[0].form_submit_button("搜索", use_container_width=True)
    cleared = search_cols[1].form_submit_button("清空", use_container_width=True)
    search_cols[2].markdown("<div style='padding-top:0.45rem; color:#6e6e73; font-size:0.8rem;'>支持全文、原理和混合搜索</div>", unsafe_allow_html=True)

if cleared:
    st.session_state.dashboard_search = ""
    st.rerun()

if submitted:
    st.session_state.dashboard_search = search_query

active_query = st.session_state.dashboard_search.strip()
if active_query:
    hits = store.search_hybrid(active_query, top=5, layer="L1") if hasattr(store, "search_hybrid") else []
    st.markdown(
        """
        <div class="mn-panel">
            <div class="mn-section-title">
                <h2>快速搜索</h2><span>前 5 条结果</span>
            </div>
            <div class="mn-list">
        """,
        unsafe_allow_html=True,
    )
    if hits:
        for hit in hits:
            content = (hit.get("abstract") or hit.get("content") or "").replace("<", "&lt;").replace(">", "&gt;")
            principle = (hit.get("principle") or "").replace("<", "&lt;").replace(">", "&gt;")
            st.markdown(
                f"""
                <div class="mn-list-item">
                    <div>
                        <strong>{_label(hit.get('tier') or 'hot')} · {hit.get('id', '')[:8]}</strong>
                        <small>{content[:200]}{'...' if len(content) > 200 else ''}</small>
                        {f'<small>原理：{principle[:120]}</small>' if principle else ''}
                    </div>
                    <div style="text-align:right; flex-shrink:0;">
                        {_pill(f'相似度 {hit.get("similarity", 0):.3f}', 'pill-blue')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="mn-empty"><div class="emoji">∅</div>没有命中记忆。</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

metric_cols = st.columns(5)
with metric_cols[0]:
    _metric("记忆节点", node_total, f"{hot_total} 个热节点")
with metric_cols[1]:
    _metric("活跃边", edge_total, "知识图谱关系")
with metric_cols[2]:
    _metric("纠正节点", correction_total, "高信号覆盖", "color:#c96a00;")
with metric_cols[3]:
    _metric("技能", len(skills), f"默认可注入 {len(approved_skills)} 个")
with metric_cols[4]:
    _metric("审计", len(audit_skills), "需要关注的技能", "color:#cc322b;" if audit_skills else "color:#1f8b4c;")

if latest_skill_auto_loop:
    evolved_items = latest_skill_auto_loop.get("evolved") or []
    feedback_items = latest_skill_auto_loop.get("feedback") or []
    promotion_items = latest_skill_auto_loop.get("promotions") or []
    error_items = latest_skill_auto_loop.get("errors") or []
    detail_lines = []
    for item in evolved_items:
        detail_lines.append(
            f"<div class='mn-list-item'><div><strong>{_html(str(item.get('skill_id') or 'unknown'))[:12]}</strong>"
            f"<small>round {item.get('round')} · decision: {_html(str(item.get('decision') or 'unknown'))}</small></div>"
            f"<div>{_pill('进化检查', 'pill-blue')}</div></div>"
        )
    for item in feedback_items:
        detail_lines.append(
            f"<div class='mn-list-item'><div><strong>{_html(str(item.get('skill_id') or 'unknown'))[:12]}</strong>"
            f"<small>feedback outcome: {_html(str(item.get('outcome') or 'unknown'))}</small></div>"
            f"<div>{_pill('反馈', 'pill-green')}</div></div>"
        )
    for item in promotion_items:
        detail_lines.append(
            f"<div class='mn-list-item'><div><strong>{_html(str(item.get('skill_id') or 'unknown'))[:12]}</strong>"
            f"<small>promotion decision: {_html(str(item.get('decision') or 'unknown'))}</small></div>"
            f"<div>{_pill('入池门控', 'pill-amber')}</div></div>"
        )
    for item in error_items:
        detail_lines.append(
            f"<div class='mn-list-item'><div><strong>{_html(str(item.get('skill_id') or 'unknown'))[:12]}</strong>"
            f"<small>{_html(str(item.get('error') or 'unknown error'))}</small></div>"
            f"<div>{_pill('错误', 'pill-red')}</div></div>"
        )
    details_html = "".join(detail_lines) or '<div class="mn-empty"><div class="emoji">∅</div>本轮没有明细。</div>'
    st.markdown(
        f"""
        <div class="mn-panel" style="margin-top:12px; margin-bottom:0;">
            <div class="mn-section-title">
                <h2>最近一次技能后处理</h2><span>daemon 自动闭环</span>
            </div>
            <div class="mn-row" style="align-items:flex-start; gap:24px; flex-wrap:wrap;">
                <div><strong>候选</strong><br>{latest_skill_auto_loop.get('candidates', 0)}</div>
                <div><strong>处理</strong><br>{latest_skill_auto_loop.get('processed', 0)}</div>
                <div><strong>运行模式</strong><br>{_html(str(latest_skill_auto_loop.get('runner_mode') or 'unknown'))}</div>
                <div><strong>进化轮次</strong><br>{len(latest_skill_auto_loop.get('evolved') or [])}</div>
                <div><strong>反馈</strong><br>{len(latest_skill_auto_loop.get('feedback') or [])}</div>
                <div><strong>入池结果</strong><br>{len(latest_skill_auto_loop.get('promotions') or [])}</div>
            </div>
            <details style="margin-top:14px;">
                <summary style="cursor:pointer; color:#3b6df6; font-weight:700;">展开候选明细</summary>
                <div class="mn-list" style="margin-top:12px;">{details_html}</div>
            </details>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

left, right = st.columns([1.45, 1])

with left:
    st.markdown(
        """
        <div class="mn-panel">
            <div class="mn-section-title">
                <h2>最近写入</h2><span>最新节点更新</span>
            </div>
            <div class="mn-list">
        """,
        unsafe_allow_html=True,
    )
    if recent_nodes:
        for node in recent_nodes:
            node_type = node.get("type") or "unknown"
            tier = node.get("tier") or "hot"
            content = _html(node.get("content") or "")
            content = content[:180] + ("..." if len(content) > 180 else "")
            principle = _html(node.get("principle") or "")
            created_at = node.get("created_at") or ""
            created_label = _time_ago(created_at) if created_at else "未知"
            created_full = _time_full(created_at)
            color = TYPE_COLORS.get(node_type, KIMI_GRAY)
            st.markdown(
                f"""
                <div class="mn-memory-card">
                    <div class="mn-memory-top">
                        <div class="mn-memory-kind">
                            <span style="color:{color};">●</span>
                            <span>{_label(node_type)}</span>
                            {_pill(_label(tier), 'pill-green' if tier == 'hot' else 'pill-amber' if tier == 'warm' else 'pill-gray')}
                        </div>
                        <div class="mn-memory-time">
                            <span>写入：{created_label}</span>
                            <span>{created_full}</span>
                        </div>
                    </div>
                    <div class="mn-memory-body">{content}</div>
                    {f'<div class="mn-memory-principle">原理：{principle[:120]}</div>' if principle else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="mn-empty"><div class="emoji">∅</div>暂无记忆节点。</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with right:
    st.markdown(
        """
        <div class="mn-panel">
            <div class="mn-section-title">
                <h2>技能证据流</h2><span>治理状态</span>
            </div>
            <div class="mn-list">
        """,
        unsafe_allow_html=True,
    )
    if audit_skills:
        for skill, audit in audit_skills[:5]:
            reasons = ", ".join(audit.get("reasons") or [audit.get("reason", "audit_required")])
            st.markdown(
                f"""
                <div class="mn-list-item">
                    <div>
                        <strong>{skill.get('name') or skill.get('slug')}</strong>
                        <small>{reasons}</small>
                    </div>
                    <div style="text-align:right; flex-shrink:0;">
                        {_pill('审计关注' if audit.get('priority') == 'high' else '待查看', 'pill-red' if audit.get('priority') == 'high' else 'pill-amber')}
                        <small>{_label(skill.get('status'))}</small>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    elif skills:
        st.markdown('<div class="mn-empty"><div class="emoji">✓</div>没有紧急技能审计。</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="mn-empty"><div class="emoji">🧩</div>暂无已结晶技能。</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="mn-panel">
        <div class="mn-section-title">
            <h2>记忆结构</h2><span>节点 / 边分布</span>
        </div>
            <div class="mn-stack">
        """,
        unsafe_allow_html=True,
    )
    for node_type, count in sorted(types.items(), key=lambda item: -item[1])[:5]:
        pct = count / node_total * 100 if node_total else 0
        color = TYPE_COLORS.get(node_type, KIMI_GRAY)
        st.markdown(
            f"""
            <div>
                <div class="mn-row" style="font-size:0.84rem;"><span><span style="color:{color};">●</span> {_label(node_type)}</span><strong>{count}</strong></div>
                <div style="height:6px; background:rgba(0,0,0,0.06); border-radius:999px; margin-top:6px; overflow:hidden;">
                    <div style="width:{pct:.1f}%; height:100%; background:{color}; border-radius:999px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<div class='mn-divider'></div>", unsafe_allow_html=True)
    for edge_type, count in sorted(edge_types.items(), key=lambda item: -item[1])[:5]:
        color = EDGE_COLORS.get(edge_type, KIMI_GRAY)
        st.markdown(
            f"<div class='mn-row' style='font-size:0.84rem;'><span><span style='color:{color};'>●</span> {_label(edge_type)}</span><strong>{count}</strong></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div></div>", unsafe_allow_html=True)

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div class="mn-panel">
        <div class="mn-section-title">
            <h2>最热记忆</h2><span>衰减分数最高</span>
        </div>
        <div class="mn-list">
    """,
    unsafe_allow_html=True,
)
if top_nodes:
    for node in top_nodes:
        content = (node.get("content") or "").replace("<", "&lt;").replace(">", "&gt;")
        principle = (node.get("principle") or "").replace("<", "&lt;").replace(">", "&gt;")
        score = node.get("decay_score") or 0
        st.markdown(
            f"""
            <div class="mn-list-item">
                <div>
                    <strong>{node.get('type') or 'memory'}</strong>
                    <small>{content[:220]}{'...' if len(content) > 220 else ''}</small>
                    {f'<small>Principle: {principle[:140]}</small>' if principle else ''}
                </div>
                <div style="text-align:right; flex-shrink:0;">
                    {_pill(f'{score:.2f}', 'pill-blue')}
                    <small>{node.get('task_type') or ''}</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.markdown('<div class="mn-empty"><div class="emoji">∅</div>暂无最热记忆。</div>', unsafe_allow_html=True)
st.markdown("</div></div>", unsafe_allow_html=True)
