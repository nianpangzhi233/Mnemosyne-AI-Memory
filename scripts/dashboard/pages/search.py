import streamlit as st
from dashboard.store import get_store
from dashboard.style import KIMI_BLUE, KIMI_DARK, KIMI_GRAY

store = get_store()

TIER_LABELS = {"hot": "热", "warm": "温", "cold": "冷"}

lang = st.session_state.get("lang", "zh")
T = {
    "zh": {
        "title": "搜索", "mode_label": "模式", "layer_label": "层级",
        "results_for": "条结果，关键词：", "enter_query": "输入关键词搜索记忆",
        "supports": "支持语义搜索、关键词搜索、混合搜索",
        "essence": "L0 精华", "summary": "L1 概要", "full_text": "L2 全文",
        "principle": "原理",
    },
    "en": {
        "title": "Search", "mode_label": "Mode", "layer_label": "Layer",
        "results_for": "results for ", "enter_query": "Enter a query to search memory",
        "supports": "Supports semantic, keyword, and hybrid search",
        "essence": "L0 Essence", "summary": "L1 Summary", "full_text": "L2 Full Text",
        "principle": "principle",
    },
}[lang]

st.title(T["title"])
st.caption("查记忆的时候尽量用中文关键词，命中率更稳。")

col_q, col_mode, col_layer, col_top = st.columns([4, 1.2, 1, 0.8])
with col_q:
    query = st.text_input("关键词", placeholder=T["enter_query"], label_visibility="collapsed")
with col_mode:
    mode = st.selectbox("模式", ["混合搜索", "向量搜索", "关键词搜索"], label_visibility="collapsed")
with col_layer:
    display_layer = st.selectbox("层级", ["L0", "L1", "L2"], index=0, label_visibility="collapsed")
with col_top:
    top_k = st.selectbox("数量", [5, 10, 20], label_visibility="collapsed")

if query:
    if mode == "向量搜索":
        results = store.search_by_vector(query, top=top_k, layer="L2")
    elif mode == "关键词搜索":
        results = store.search_by_keyword(query, top=top_k, layer="L2")
    else:
        results = store.search_hybrid(query, top=top_k, layer="L2")

    st.markdown(f"**{len(results)}** {T['results_for']} _{query}_")

    for i, r in enumerate(results):
        node_id = r.get("id", "")
        sim = r.get("similarity", 0)
        tier = r.get("tier", "hot")
        badge_cls = f"badge-{tier}"

        content = r.get("content", "")
        principle = r.get("principle", "")
        abstract = (r.get("abstract") or content[:150])[:150]
        overview = (r.get("overview") or content[:600])[:600]

        st.markdown(f"""
        <div class="kimi-card" style="padding:16px 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-weight:600; color:{KIMI_DARK};">#{i+1}</span>
                    <span class="kimi-badge {badge_cls}">{TIER_LABELS.get(tier, tier)}</span>
                    <span style="font-size:0.75rem; color:{KIMI_GRAY};">相似度={sim:.3f}</span>
                </div>
                <span style="font-size:0.65rem; color:{KIMI_GRAY}; font-family:monospace;">{node_id[:8]}...</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="layer-l0">
                <div style="font-size:0.7rem; color:{KIMI_BLUE}; font-weight:600; margin-bottom:4px;">{T['essence']}</div>
                <div style="font-size:0.85rem;">{abstract}</div>
            </div>
        """, unsafe_allow_html=True)

        with st.expander(T["summary"], expanded=(display_layer in ("L1", "L2"))):
            st.markdown(f"""
            <div class="layer-l1">
                <div style="font-size:0.7rem; color:#af52de; font-weight:600; margin-bottom:4px;">{T['summary']}</div>
                <div style="font-size:0.85rem;">{overview}</div>
                {"<div style='font-size:0.75rem; color:" + KIMI_GRAY + "; margin-top:4px;'>原理：" + principle + "</div>" if principle else ""}
            </div>
            """, unsafe_allow_html=True)

            with st.expander(T["full_text"], expanded=(display_layer == "L2")):
                if content:
                    st.markdown(f"""
                    <div class="layer-l2">
                        <div style="font-size:0.7rem; color:#34c759; font-weight:600; margin-bottom:4px;">{T['full_text']}</div>
                        <div style="font-size:0.85rem; white-space:pre-wrap;">{content}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style="text-align:center; padding:80px 0; color:#6e6e73;">
        <div style="font-size:3rem; margin-bottom:16px;">🔍</div>
        <div style="font-size:1.1rem;">{T['enter_query']}</div>
        <div style="font-size:0.85rem; margin-top:8px;">{T['supports']}</div>
    </div>
    """, unsafe_allow_html=True)
