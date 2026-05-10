import streamlit as st
import json
import streamlit.components.v1 as components
from dashboard.store import get_store
from dashboard.style import EDGE_COLORS, TYPE_COLORS, KIMI_DARK, KIMI_GRAY

store = get_store()

TIER_LABELS = {"hot": "热", "warm": "温", "cold": "冷"}
TYPE_LABELS = {
    "experience": "经验",
    "correction": "纠正",
    "strategy": "策略",
    "raw": "原始片段",
    "skill": "技能",
    "skill_feedback": "技能反馈",
}
RELATION_LABELS = {
    "similar_to": "相似",
    "caused": "导致",
    "solves": "解决",
    "contradicts": "纠正/冲突",
    "transfers_to": "迁移",
    "is_a": "归类",
    "evolved_from": "演化自",
    "verified_by": "验证",
    "fails_on": "失败样例",
    "needs_revision": "需修订",
}


def _select_labels(options, label_map, defaults):
    labels = [label_map.get(option, option) for option in options]
    default_labels = [label_map.get(option, option) for option in defaults]
    selected = st.multiselect("", labels, default=default_labels, label_visibility="collapsed")
    reverse = {label_map.get(option, option): option for option in options}
    return [reverse[label] for label in selected]

lang = st.session_state.get("lang", "zh")
T = {
    "zh": {
        "title": "图谱", "filters": "筛选", "focus_node": "聚焦节点 ID",
        "max_nodes": "最大节点数", "tiers": "层级", "types": "类型",
        "legend": "图例", "no_nodes": "无匹配节点，请调整筛选条件。",
        "select_one": "请至少选择一个层级和类型。",
    },
    "en": {
        "title": "Graph", "filters": "Filters", "focus_node": "Focus Node ID",
        "max_nodes": "Max Nodes", "tiers": "Tiers", "types": "Types",
        "legend": "Legend", "no_nodes": "No nodes match the filters.",
        "select_one": "Select at least one tier and one type.",
    },
}[lang]

st.title(T["title"])
st.caption("图谱页偏工具型，主要用来确认记忆之间的关系。")

col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    st.markdown(f"### {T['filters']}")
    focus = st.text_input(T["focus_node"], placeholder="输入节点 ID")
    max_nodes = st.slider(T["max_nodes"], 10, 200, 50)
    st.caption(T["tiers"])
    show_tiers = _select_labels(["hot", "warm", "cold"], TIER_LABELS, ["hot", "warm"])
    st.caption(T["types"])
    show_types = _select_labels(["experience", "correction", "strategy", "raw", "skill", "skill_feedback"], TYPE_LABELS, ["experience", "correction", "strategy"])

if not show_tiers or not show_types:
    st.warning(T["select_one"])
    st.stop()

nodes_data = store.query_nodes()
tier_set = set(show_tiers)
type_set = set(show_types)

filtered = [n for n in nodes_data if n.get("tier") in tier_set and n.get("type") in type_set]

if focus:
    focus_node = store.get_node(focus.strip())
    if focus_node:
        filtered_ids = {focus.strip()}
        traversed = store.traverse(focus.strip(), depth=2, max_results=max_nodes)
        for e in traversed:
            filtered_ids.add(e.get("from", ""))
            filtered_ids.add(e.get("to", ""))
        filtered = [n for n in nodes_data if n["id"] in filtered_ids]

filtered = sorted(filtered, key=lambda x: x.get("decay_score", 0), reverse=True)[:max_nodes]
node_ids = {n["id"] for n in filtered}

all_edges = store.query_edges("status='active'")
graph_edges = [e for e in all_edges if e["from_id"] in node_ids and e["to_id"] in node_ids]

nodes_json = []
for n in filtered:
    nodes_json.append({
        "id": n["id"],
        "label": (n.get("abstract") or n.get("content") or "")[:40],
        "type": n.get("type", "unknown"),
        "typeLabel": TYPE_LABELS.get(n.get("type", "unknown"), n.get("type", "unknown")),
        "tier": n.get("tier", "hot"),
        "tierLabel": TIER_LABELS.get(n.get("tier", "hot"), n.get("tier", "hot")),
        "score": round(n.get("decay_score", 0), 2),
        "principle": n.get("principle", ""),
    })

edges_json = []
for e in graph_edges:
    edges_json.append({
        "source": e["from_id"],
        "target": e["to_id"],
        "type": e["relation_type"],
        "typeLabel": RELATION_LABELS.get(e["relation_type"], e["relation_type"]),
        "weight": e.get("weight", 0.5),
    })

if not nodes_json:
    st.info(T["no_nodes"])
    st.stop()

type_colors_json = json.dumps(TYPE_COLORS)
edge_colors_json = json.dumps(EDGE_COLORS)

html = f"""
<div id="graph-container" style="width:100%; height:640px; background:#fbfbfd; border-radius:16px; border:1px solid #e5e5e7; overflow:hidden; position:relative;"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
(function() {{
    const nodes = {json.dumps(nodes_json)};
    const edges = {json.dumps(edges_json)};
    const typeColors = {type_colors_json};
    const edgeColors = {edge_colors_json};

    const container = document.getElementById("graph-container");
    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select("#graph-container")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }});

    svg.call(zoom);

    const g = svg.append("g");

    g.append("defs").append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "#aaa");

    const sim = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(edges).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(25));

    sim.on("end", () => {{
        const xs = nodes.map(n => n.x);
        const ys = nodes.map(n => n.y);
        const minX = Math.min(...xs), maxX = Math.max(...xs);
        const minY = Math.min(...ys), maxY = Math.max(...ys);
        const gw = maxX - minX + 100;
        const gh = maxY - minY + 100;
        const scale = Math.min(width / gw, height / gh, 1.2) * 0.85;
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        const tx = width / 2 - cx * scale;
        const ty = height / 2 - cy * scale;
        svg.transition().duration(600).call(
            zoom.transform,
            d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
    }});

    const link = g.append("g")
        .selectAll("line")
        .data(edges)
        .enter().append("line")
        .attr("stroke", d => edgeColors[d.type] || "#aaa")
        .attr("stroke-opacity", 0.5)
        .attr("stroke-width", d => Math.max(1, d.weight * 3))
        .attr("marker-end", "url(#arrow)");

    const nodeDrag = d3.drag()
        .on("start", (e, d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
        .on("drag", (e, d) => {{ d.fx=e.x; d.fy=e.y; }})
        .on("end", (e, d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }});

    const node = g.append("g")
        .selectAll("g")
        .data(nodes)
        .enter().append("g")
        .call(nodeDrag);

    node.append("circle")
        .attr("r", d => Math.max(8, Math.min(18, d.score * 10)))
        .attr("fill", d => typeColors[d.type] || "#8e8e93")
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .style("cursor", "pointer")
        .on("mouseover", function(e, d) {{
            d3.select(this).attr("stroke-width", 3).attr("stroke", "#0071e3");
            tooltip.style("opacity", 1).html(
                "<b>" + d.typeLabel + "</b> [" + d.tierLabel + "]<br>" +
                d.label + (d.principle ? "<br><i>" + d.principle + "</i>" : "")
            );
        }})
        .on("mousemove", (e) => {{
            const rect = container.getBoundingClientRect();
            tooltip
                .style("left", (e.clientX - rect.left + 12) + "px")
                .style("top", (e.clientY - rect.top - 12) + "px");
        }})
        .on("mouseout", function() {{
            d3.select(this).attr("stroke-width", 2).attr("stroke", "white");
            tooltip.style("opacity", 0);
        }});

    node.append("text")
        .attr("dy", -14)
        .attr("text-anchor", "middle")
        .attr("font-size", "10px")
        .attr("fill", "#1d1d1f")
        .attr("stroke", "white")
        .attr("stroke-width", 3)
        .attr("paint-order", "stroke")
        .text(d => d.label.substring(0, 18));

    const tooltip = d3.select("#graph-container")
        .append("div")
        .style("position", "absolute")
        .style("background", "white")
        .style("padding", "8px 12px")
        .style("border-radius", "8px")
        .style("box-shadow", "0 2px 12px rgba(0,0,0,0.12)")
        .style("font-size", "12px")
        .style("pointer-events", "none")
        .style("opacity", 0)
        .style("max-width", "240px")
        .style("z-index", "10");

    sim.on("tick", () => {{
        link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
        node.attr("transform", d => "translate(" + d.x + "," + d.y + ")");
    }});
}})();
</script>
"""

with col_f2:
    components.html(html, height=660)

    st.markdown(f"### {T['legend']}")
    cols_l = st.columns(len(EDGE_COLORS))
    for idx, (etype, ecolor) in enumerate(EDGE_COLORS.items()):
        count = sum(1 for e in graph_edges if e["relation_type"] == etype)
        with cols_l[idx]:
            st.markdown(f'<span style="color:{ecolor}; font-weight:600;">● {RELATION_LABELS.get(etype, etype)}</span> <span style="color:#6e6e73;">({count})</span>', unsafe_allow_html=True)
