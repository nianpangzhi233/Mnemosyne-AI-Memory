#!/usr/bin/env python3
"""Mnemosyne Dashboard — Streamlit

启动: streamlit run scripts/dashboard/app.py --server.port 8501
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime

scripts_dir = Path(__file__).resolve().parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from dashboard.style import GLOBAL_CSS, KIMI_BLUE, KIMI_DARK, KIMI_GRAY

st.set_page_config(
    page_title="Mnemosyne",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

from dashboard.store import get_store

store = get_store()

total_nodes = store.count_nodes()
total_edges = store.count_edges()
skill_total = len(store.list_skill_artifacts()) if hasattr(store, "list_skill_artifacts") else 0
approved_skills = len(store.list_skill_artifacts(statuses=["approved"])) if hasattr(store, "list_skill_artifacts") else 0
evolved_skills = len(store.list_skill_artifacts(statuses=["evolved"])) if hasattr(store, "list_skill_artifacts") else 0

if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "dashboard_refreshed_at" not in st.session_state:
    st.session_state.dashboard_refreshed_at = datetime.now().strftime("%H:%M:%S")

LANG = {
    "zh": {
        "nodes": "节点", "edges": "边",
        "dashboard": "仪表盘", "search": "搜索", "graph": "图谱", "dream_log": "做梦日志",
        "switch_lang": "EN",
    },
    "en": {
        "nodes": "Nodes", "edges": "Edges",
        "dashboard": "Dashboard", "search": "Search", "graph": "Graph", "dream_log": "Dream Log",
        "switch_lang": "中文",
    },
}

L = LANG[st.session_state.lang]

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 20px 0;">
        <div style="font-size:2rem;">🧠</div>
        <div style="font-size:1.25rem; font-weight:700; color:white;">Mnemosyne</div>
        <div style="font-size:0.75rem; color:rgba(255,255,255,0.5); margin-top:4px;">记忆与技能系统 v7.x</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown(f"""
    <div style="padding: 0 8px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">{L['nodes']}</span>
            <span style="color:white; font-weight:600;">{total_nodes}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">{L['edges']}</span>
            <span style="color:white; font-weight:600;">{total_edges}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding: 0 8px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">技能总数</span>
            <span style="color:white; font-weight:600;">{skill_total}</span>
        </div>
        <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">已批准</span>
            <span style="color:white; font-weight:600;">{approved_skills}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">已演化</span>
            <span style="color:white; font-weight:600;">{evolved_skills}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🌐 " + L["switch_lang"], use_container_width=True,
                 type="primary"):
        st.session_state.lang = "en" if st.session_state.lang == "zh" else "zh"
        st.rerun()

    st.markdown("---")

    if st.button("刷新数据", use_container_width=True):
        get_store.clear()
        st.session_state.dashboard_refreshed_at = datetime.now().strftime("%H:%M:%S")
        st.rerun()
    st.caption(f"上次刷新：{st.session_state.dashboard_refreshed_at}")

    st.markdown("---")
    st.caption("快捷跳转")
    quick_pages = [
        ("首页", "pages/dashboard.py", "🏠"),
        ("技能管理", "pages/skills.py", "🧩"),
        ("搜索", "pages/search.py", "🔍"),
        ("图谱", "pages/graph.py", "🔗"),
        ("做梦日志", "pages/dream_log.py", "🌙"),
    ]
    for label, page, icon in quick_pages:
        if st.button(f"{icon} {label}", use_container_width=True, key=f"quick_{page}"):
            st.switch_page(page)

    st.markdown("---")

pg = st.navigation([
    st.Page("pages/dashboard.py", title=L["dashboard"], icon="📊"),
    st.Page("pages/skills.py", title="技能", icon="🧩"),
    st.Page("pages/search.py", title=L["search"], icon="🔍"),
    st.Page("pages/graph.py", title=L["graph"], icon="🔗"),
    st.Page("pages/dream_log.py", title=L["dream_log"], icon="🌙"),
])
pg.run()
