#!/usr/bin/env python3
"""Mnemosyne Dashboard — Streamlit

启动: streamlit run scripts/dashboard/app.py --server.port 8501
"""

import streamlit as st
from pathlib import Path
import sys

scripts_dir = Path(__file__).resolve().parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from dashboard.style import GLOBAL_CSS, KIMI_BLUE, KIMI_DARK

st.set_page_config(
    page_title="Mnemosyne",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

from dashboard.store import get_store

store = get_store()

if "lang" not in st.session_state:
    st.session_state.lang = "zh"

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
        <div style="font-size:0.75rem; color:rgba(255,255,255,0.5); margin-top:4px;">Experience & Memory v5.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    nodes = store.count_nodes()
    edges = store.count_edges()
    st.markdown(f"""
    <div style="padding: 0 8px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">{L['nodes']}</span>
            <span style="color:white; font-weight:600;">{nodes}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
            <span style="color:rgba(255,255,255,0.6); font-size:0.8rem;">{L['edges']}</span>
            <span style="color:white; font-weight:600;">{edges}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🌐 " + L["switch_lang"], use_container_width=True,
                 type="primary"):
        st.session_state.lang = "en" if st.session_state.lang == "zh" else "zh"
        st.rerun()

    st.markdown("---")

pg = st.navigation([
    st.Page("pages/dashboard.py", title=L["dashboard"], icon="📊"),
    st.Page("pages/search.py", title=L["search"], icon="🔍"),
    st.Page("pages/graph.py", title=L["graph"], icon="🔗"),
    st.Page("pages/dream_log.py", title=L["dream_log"], icon="🌙"),
])
pg.run()
