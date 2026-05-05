import streamlit as st
import json
from dashboard.store import get_store
from dashboard.style import KIMI_BLUE, KIMI_DARK, KIMI_GRAY, TIER_COLORS, TYPE_COLORS

store = get_store()

lang = st.session_state.get("lang", "zh")
T = {
    "zh": {
        "title": "仪表盘", "node_types": "节点类型", "edge_types": "边类型",
        "top_memory": "记忆排行", "nodes": "节点", "edges": "边",
    },
    "en": {
        "title": "Dashboard", "node_types": "Node Types", "edge_types": "Edge Types",
        "top_memory": "Top Memory", "nodes": "Nodes", "edges": "Edges",
    },
}[lang]

st.title(T["title"])

all_nodes = store.query_nodes()
all_edges = store.query_edges("status='active'")

total_nodes = len(all_nodes)
total_edges = len(all_edges)
hot = sum(1 for n in all_nodes if n.get("tier") == "hot")
warm = sum(1 for n in all_nodes if n.get("tier") == "warm")
cold = sum(1 for n in all_nodes if n.get("tier") == "cold")

types = {}
for n in all_nodes:
    t = n.get("type", "unknown")
    types[t] = types.get(t, 0) + 1

edge_types = {}
for e in all_edges:
    t = e.get("relation_type", "unknown")
    edge_types[t] = edge_types.get(t, 0) + 1

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="kimi-card kimi-stat">
        <div class="number">{total_nodes}</div>
        <div class="label">{T["nodes"]}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="kimi-card kimi-stat">
        <div class="number">{total_edges}</div>
        <div class="label">{T["edges"]}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="kimi-card kimi-stat">
        <div class="number" style="color:#34c759">{hot}</div>
        <div class="label">Hot</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="kimi-card kimi-stat">
        <div class="number" style="color:#8e8e93">{cold}</div>
        <div class="label">Cold</div>
    </div>
    """, unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(f"### {T['node_types']}")
    for ntype, count in sorted(types.items(), key=lambda x: -x[1]):
        color = TYPE_COLORS.get(ntype, KIMI_GRAY)
        pct = count / total_nodes * 100 if total_nodes else 0
        st.markdown(f"""
        <div class="kimi-card" style="padding:16px 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{color}; margin-right:8px;"></span>
                    <span style="font-weight:500;">{ntype}</span>
                </div>
                <div>
                    <span style="font-weight:600; font-size:1.1rem;">{count}</span>
                    <span style="color:{KIMI_GRAY}; font-size:0.8rem; margin-left:4px;">({pct:.0f}%)</span>
                </div>
            </div>
            <div style="background:{KIMI_GRAY}20; border-radius:4px; height:4px; margin-top:10px; overflow:hidden;">
                <div style="background:{color}; height:100%; width:{pct}%; border-radius:4px; transition:width 0.5s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with col_b:
    st.markdown(f"### {T['edge_types']}")
    for etype, count in sorted(edge_types.items(), key=lambda x: -x[1]):
        from dashboard.style import EDGE_COLORS
        color = EDGE_COLORS.get(etype, KIMI_GRAY)
        pct = count / total_edges * 100 if total_edges else 0
        st.markdown(f"""
        <div class="kimi-card" style="padding:16px 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{color}; margin-right:8px;"></span>
                    <span style="font-weight:500;">{etype}</span>
                </div>
                <div>
                    <span style="font-weight:600; font-size:1.1rem;">{count}</span>
                    <span style="color:{KIMI_GRAY}; font-size:0.8rem; margin-left:4px;">({pct:.0f}%)</span>
                </div>
            </div>
            <div style="background:{KIMI_GRAY}20; border-radius:4px; height:4px; margin-top:10px; overflow:hidden;">
                <div style="background:{color}; height:100%; width:{pct}%; border-radius:4px; transition:width 0.5s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown(f"### {T['top_memory']}")
top_nodes = store.get_top_hot_nodes(limit=10)
for n in top_nodes:
    content = (n.get("content") or "")[:80]
    principle = n.get("principle", "")
    score = n.get("decay_score", 0)
    tier = n.get("tier", "hot")
    badge_cls = f"badge-{tier}"
    st.markdown(f"""
    <div class="kimi-card" style="padding:16px 20px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div style="flex:1;">
                <div style="font-size:0.9rem; color:{KIMI_DARK}; margin-bottom:4px;">{content}</div>
                {"<div style='font-size:0.75rem; color:" + KIMI_GRAY + ";'>原理: " + principle[:60] + "</div>" if principle else ""}
            </div>
            <div style="text-align:right; flex-shrink:0; margin-left:16px;">
                <span class="kimi-badge {badge_cls}">{tier}</span>
                <div style="font-size:0.75rem; color:{KIMI_GRAY}; margin-top:4px;">{score:.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
