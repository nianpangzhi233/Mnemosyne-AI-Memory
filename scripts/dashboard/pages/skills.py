import json

import streamlit as st

from dashboard.store import get_store
from dashboard.style import KIMI_GRAY, TYPE_COLORS


store = get_store()

skills = store.list_skill_artifacts() if hasattr(store, "list_skill_artifacts") else []
approved = [skill for skill in skills if skill.get("status") == "approved"]
evolved = [skill for skill in skills if skill.get("status") == "evolved"]
needs_revision = [skill for skill in skills if skill.get("status") == "needs_revision"]
deprecated = [skill for skill in skills if skill.get("status") == "deprecated"]

T = {
    "zh": {
        "title": "技能管理",
        "subtitle": "查看技能证据流、注入状态和审计信号。",
        "search_placeholder": "按名称、slug、触发条件搜索",
        "all": "全部",
        "approved": "已批准",
        "evolved": "已演化",
        "needs_revision": "需修订",
        "deprecated": "已废弃",
        "trigger": "触发条件",
        "precondition": "前提",
        "procedure": "流程",
        "evidence": "证据",
        "status": "状态",
        "risk": "风险",
        "audit": "审计",
        "feedback": "反馈",
        "inject": "默认注入",
        "trial": "试用",
        "no_skills": "还没有技能。先跑 crystallize / evolve 流程。",
    },
    "en": {
        "title": "Skills",
        "subtitle": "Inspect evidence flow, injection status, and audit signals.",
        "search_placeholder": "Search by name / slug / trigger",
        "all": "All",
        "approved": "Approved",
        "evolved": "Evolved",
        "needs_revision": "Needs Revision",
        "deprecated": "Deprecated",
        "trigger": "Trigger",
        "precondition": "Precondition",
        "procedure": "Procedure",
        "evidence": "Evidence",
        "status": "Status",
        "risk": "Risk",
        "audit": "Audit",
        "feedback": "Feedback",
        "inject": "Inject",
        "trial": "Trial",
        "no_skills": "No skills yet. Run crystallize or evolve first.",
    },
}

lang = st.session_state.get("lang", "zh")
L = T.get(lang, T["zh"])


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _pill(text, cls="pill-gray"):
    return f'<span class="mn-pill {cls}">{text}</span>'


def _status_class(status):
    if status == "approved":
        return "pill-green"
    if status == "evolved":
        return "pill-blue"
    if status in {"needs_revision", "rejected"}:
        return "pill-red"
    if status == "deprecated":
        return "pill-gray"
    return "pill-amber"


def _quality_grade(skill):
    decision = skill.get("latest_decision") or skill.get("review_status") or skill.get("status")
    if decision in {"needs_revision", "rejected"} or skill.get("needs_revision"):
        return "D", "需修订"
    if skill.get("status") == "deprecated":
        return "F", "已停用"
    darwin = skill.get("latest_darwin_score")
    mnemosyne = skill.get("latest_mnemosyne_score")
    delta = skill.get("latest_live_test_delta")
    if darwin is None and mnemosyne is None:
        return "?", "尚未实测"
    if (delta or 0) < 0:
        return "D", "实测退步"
    score = min(v for v in (darwin, mnemosyne) if v is not None)
    if score >= 90:
        return "A", "证据强"
    if score >= 80:
        return "B", "可试用"
    if score >= 70:
        return "C", "需补证据"
    return "D", "需修订"


def _next_action(skill, audit_required):
    if skill.get("status") == "deprecated":
        return "已停用，除非有新证据否则不要恢复"
    if skill.get("latest_eval_mode") is None:
        return "先跑 Darwin baseline 对比测试"
    if skill.get("latest_decision") == "needs_revision" or skill.get("needs_revision"):
        return "查看失败原因并修复后复测"
    if audit_required:
        return "暂停默认注入并复审"
    if skill.get("status") == "approved" and skill.get("inject_enabled"):
        return "继续使用，定期抽检"
    if skill.get("latest_decision") == "evolved":
        return "可进入 trial 或人工批准"
    return "补充真实任务证据"


st.title(L["title"])
st.caption(L["subtitle"])

query = st.text_input(L["search_placeholder"], label_visibility="collapsed")
status_filter = st.radio(
    L["status"],
    [L["all"], L["approved"], L["evolved"], L["needs_revision"], L["deprecated"]],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

status_map = {
    L["all"]: None,
    L["approved"]: "approved",
    L["evolved"]: "evolved",
    L["needs_revision"]: "needs_revision",
    L["deprecated"]: "deprecated",
}

filtered = skills
if status_map.get(status_filter):
    filtered = [skill for skill in filtered if skill.get("status") == status_map[status_filter]]
if query:
    q = query.lower()
    filtered = [
        skill for skill in filtered
        if q in _safe_text(skill.get("name")).lower()
        or q in _safe_text(skill.get("slug")).lower()
        or q in _safe_text(skill.get("trigger_patterns")).lower()
        or q in _safe_text(skill.get("preconditions")).lower()
    ]

summary_cols = st.columns(4)
summary_cols[0].markdown(f"<div class='mn-metric'><div class='label'>技能总数</div><div class='value'>{len(skills)}</div><div class='hint'>目录规模</div></div>", unsafe_allow_html=True)
summary_cols[1].markdown(f"<div class='mn-metric'><div class='label'>已批准</div><div class='value'>{len(approved)}</div><div class='hint'>默认可注入</div></div>", unsafe_allow_html=True)
summary_cols[2].markdown(f"<div class='mn-metric'><div class='label'>已演化</div><div class='value'>{len(evolved)}</div><div class='hint'>图谱治理已通过</div></div>", unsafe_allow_html=True)
summary_cols[3].markdown(f"<div class='mn-metric'><div class='label'>需修订</div><div class='value'>{len(needs_revision)}</div><div class='hint'>需要关注</div></div>", unsafe_allow_html=True)

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

if not filtered:
    st.markdown(f"<div class='mn-panel mn-empty'><div class='emoji'>🧩</div>{L['no_skills']}</div>", unsafe_allow_html=True)
else:
    for skill in filtered:
        trigger_patterns = skill.get("trigger_patterns") or []
        preconditions = skill.get("preconditions") or []
        procedure = skill.get("procedure") or []
        failure_modes = skill.get("failure_modes") or []
        metadata = skill.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        usage_loop = metadata.get("usage_loop") if isinstance(metadata, dict) else {}
        usage_loop = usage_loop if isinstance(usage_loop, dict) else {}
        audit_required = bool(
            usage_loop.get("audit_failures")
            or usage_loop.get("trigger_mismatch_count")
            or skill.get("needs_revision")
            or skill.get("status") == "needs_revision"
            or skill.get("review_status") == "needs_revision"
            or skill.get("latest_decision") == "needs_revision"
        )
        grade, grade_hint = _quality_grade(skill)
        grade_class = "pill-green" if grade in {"A", "B"} else "pill-red" if grade in {"D", "F"} else "pill-amber"
        next_action = _next_action(skill, audit_required)
        latest_darwin = skill.get("latest_darwin_score")
        latest_mnemosyne = skill.get("latest_mnemosyne_score")
        latest_delta = skill.get("latest_live_test_delta")
        static_score = skill.get("mnemosyne_score") or skill.get("final_score") or 0

        c1, c2 = st.columns([1.4, 1])
        with c1:
            st.markdown(
                f"""
                <div class="skill-card">
                    <div class="skill-title">
                        <h3>{_safe_text(skill.get('name'))}</h3>
                        <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                            {_pill(_safe_text(skill.get('status')), _status_class(skill.get('status')))}
                            {_pill('质量 ' + grade, grade_class)}
                            {_pill(_safe_text(skill.get('risk_level') or 'medium'), 'pill-amber' if skill.get('risk_level') == 'medium' else 'pill-red' if skill.get('risk_level') == 'high' else 'pill-green')}
                            {_pill('默认注入' if skill.get('inject_enabled') else '暂不注入', 'pill-green' if skill.get('inject_enabled') else 'pill-gray')}
                            {_pill('审计关注' if audit_required else '状态正常', 'pill-red' if audit_required else 'pill-green')}
                        </div>
                    </div>
                    <div style="color:{KIMI_GRAY}; font-size:0.9rem; line-height:1.75;">
                        <div><strong>Slug：</strong> {_safe_text(skill.get('slug'))}</div>
                        <div><strong>{L['trigger']}:</strong> {', '.join(trigger_patterns) if trigger_patterns else '∅'}</div>
                        <div><strong>{L['precondition']}:</strong> {', '.join(preconditions) if preconditions else '∅'}</div>
                        <div><strong>{L['procedure']}：</strong> {len(procedure)} 步</div>
                        <div><strong>{L['evidence']}：</strong> 来源 {len(skill.get('source_node_ids') or [])}，证据 {len(skill.get('evidence_node_ids') or [])}</div>
                        <div><strong>Darwin：</strong> {latest_darwin if latest_darwin is not None else '未实测'} · <strong>Mnemosyne：</strong> {latest_mnemosyne if latest_mnemosyne is not None else '未实测'} · <strong>Δ：</strong> {latest_delta if latest_delta is not None else '∅'}</div>
                        <div><strong>决策：</strong> {_safe_text(skill.get('latest_decision') or '尚无')} · {_safe_text(skill.get('latest_decision_reason') or grade_hint)}</div>
                        <div><strong>下一步：</strong> {_safe_text(next_action)}</div>
                    </div>
                    <div class="skill-meta">
                        <span>{L['feedback']}：{skill.get('trial_success_count') or 0} 成功 / {skill.get('trial_failure_count') or 0} 失败</span>
                        <span>版本 v{_safe_text(skill.get('version') or '0.1.0')}</span>
                        <span>格式预检 {static_score}</span>
                        <span>审核 {skill.get('review_status') or 'draft'}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            with st.expander(f"查看详情 · {_safe_text(skill.get('node_id'))[:10]}", expanded=False):
                st.markdown(
                    f"""
                    <div class="mn-stack">
                        <div><strong>失败模式</strong><br><span style="color:{KIMI_GRAY};">{', '.join(failure_modes) if failure_modes else '∅'}</span></div>
                        <div><strong>审核状态</strong><br><span style="color:{KIMI_GRAY};">{_safe_text(skill.get('review_status') or '草稿')}</span></div>
                        <div><strong>批准模式</strong><br><span style="color:{KIMI_GRAY};">{_safe_text(skill.get('approval_mode') or '无')}</span></div>
                        <div><strong>最近审计</strong><br><span style="color:{KIMI_GRAY};">{_safe_text(usage_loop.get('last_audit_reason') or '无')}</span></div>
                        <div><strong>最新决策原因</strong><br><span style="color:{KIMI_GRAY};">{_safe_text(skill.get('latest_decision_reason') or '无')}</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
