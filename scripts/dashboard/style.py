KIMI_BLUE = "#0071e3"
KIMI_DARK = "#17181c"
KIMI_GRAY = "#6e6e73"
KIMI_LIGHT = "#f5f5f7"
KIMI_WHITE = "#ffffff"
KIMI_CARD_BG = "rgba(255,255,255,0.82)"
KIMI_BORDER = "rgba(23,24,28,0.08)"

TIER_COLORS = {"hot": "#34c759", "warm": "#ff9500", "cold": "#8e8e93"}
EDGE_COLORS = {
    "similar_to": "#0071e3",
    "caused": "#ff3b30",
    "solves": "#34c759",
    "contradicts": "#ff9500",
    "transfers_to": "#af52de",
    "is_a": "#5ac8fa",
    "evolved_from": "#ff2d55",
}
TYPE_COLORS = {
    "experience": "#0071e3",
    "correction": "#ff9500",
    "principle": "#af52de",
    "strategy": "#34c759",
    "raw": "#8e8e93",
}

GLOBAL_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {{
        --mn-bg: linear-gradient(180deg, #f7f4ee 0%, #fafafa 48%, #eef7f2 100%);
        --mn-surface: rgba(255, 255, 255, 0.82);
        --mn-surface-strong: rgba(255, 255, 255, 0.94);
        --mn-border: rgba(23, 24, 28, 0.08);
        --mn-shadow: 0 18px 60px rgba(17, 24, 39, 0.08);
        --mn-shadow-soft: 0 8px 30px rgba(17, 24, 39, 0.05);
    }}

    .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background: var(--mn-bg);
        color: {KIMI_DARK};
    }}

    .stApp::before {{
        content: '';
        position: fixed;
        inset: 0;
        pointer-events: none;
        background:
            radial-gradient(circle at top left, rgba(0,113,227,0.09), transparent 32%),
            radial-gradient(circle at 85% 15%, rgba(76,175,80,0.08), transparent 26%),
            radial-gradient(circle at 50% 100%, rgba(175,82,222,0.05), transparent 25%);
        z-index: 0;
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}

    [data-testid="stToolbar"] {{
        visibility: hidden;
    }}

    .block-container {{
        position: relative;
        z-index: 1;
        padding-top: 1.6rem !important;
        padding-bottom: 2.4rem !important;
        max-width: 1320px !important;
    }}

    .main .block-container {{
        padding-inline: 1.25rem;
    }}

    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #17181c 0%, #1e2026 100%) !important;
        color: {KIMI_LIGHT} !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }}

    section[data-testid="stSidebar"] .stMarkdown, 
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {{
        color: {KIMI_LIGHT} !important;
    }}

    section[data-testid="stSidebar"] nav a {{
        color: rgba(255,255,255,0.7) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
        padding: 10px 16px !important;
    }}

    section[data-testid="stSidebar"] nav a:hover {{
        background: rgba(255,255,255,0.08) !important;
        color: white !important;
    }}

    section[data-testid="stSidebar"] nav a.active {{
        background: {KIMI_BLUE} !important;
        color: white !important;
        box-shadow: 0 2px 12px rgba(0,113,227,0.3) !important;
    }}

    .mn-hero {{
        background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(255,255,255,0.72));
        border: 1px solid var(--mn-border);
        border-radius: 28px;
        padding: 28px;
        box-shadow: var(--mn-shadow);
        backdrop-filter: blur(18px);
        margin-bottom: 20px;
    }}

    .mn-hero h1 {{
        margin: 0;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.08;
        font-weight: 800;
        color: {KIMI_DARK} !important;
    }}

    .mn-hero p {{
        margin: 0;
        color: {KIMI_GRAY};
        line-height: 1.7;
    }}

    .mn-shell {{
        display: grid;
        gap: 18px;
    }}

    .mn-grid {{
        display: grid;
        gap: 16px;
    }}

    .mn-grid.metrics {{
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }}

    .mn-grid.two-col {{
        grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr);
    }}

    .mn-grid.three-col {{
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}

    .mn-panel {{
        background: var(--mn-surface);
        border-radius: 24px;
        border: 1px solid var(--mn-border);
        box-shadow: var(--mn-shadow-soft);
        backdrop-filter: blur(16px);
        padding: 20px;
    }}

    .mn-panel.strong {{
        background: var(--mn-surface-strong);
        box-shadow: var(--mn-shadow);
    }}

    .mn-panel:hover {{
        transform: translateY(-1px);
        transition: transform 160ms ease, box-shadow 160ms ease;
    }}

    .mn-section-title {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 14px;
    }}

    .mn-section-title h2 {{
        margin: 0;
        font-size: 1.05rem;
        font-weight: 700;
        color: {KIMI_DARK};
    }}

    .mn-section-title span {{
        color: {KIMI_GRAY};
        font-size: 0.82rem;
    }}

    .mn-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.01em;
    }}

    .pill-blue {{ background: rgba(0,113,227,0.10); color: {KIMI_BLUE}; }}
    .pill-green {{ background: rgba(52,199,89,0.12); color: #1f8b4c; }}
    .pill-amber {{ background: rgba(255,149,0,0.12); color: #c96a00; }}
    .pill-red {{ background: rgba(255,59,48,0.12); color: #cc322b; }}
    .pill-gray {{ background: rgba(110,110,115,0.12); color: {KIMI_GRAY}; }}

    .mn-metric {{
        border-radius: 22px;
        padding: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(255,255,255,0.72));
        border: 1px solid var(--mn-border);
        box-shadow: 0 10px 28px rgba(17,24,39,0.04);
    }}

    .mn-metric .label {{
        font-size: 0.8rem;
        color: {KIMI_GRAY};
        margin-bottom: 10px;
    }}

    .mn-metric .value {{
        font-size: 2rem;
        font-weight: 800;
        line-height: 1;
        color: {KIMI_DARK};
    }}

    .mn-metric .hint {{
        margin-top: 8px;
        color: {KIMI_GRAY};
        font-size: 0.78rem;
    }}

    .mn-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }}

    .mn-stack {{
        display: grid;
        gap: 12px;
    }}

    .mn-list {{
        display: grid;
        gap: 10px;
    }}

    .mn-list-item {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 14px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(23,24,28,0.06);
    }}

    .mn-list-item strong {{
        color: {KIMI_DARK};
        font-weight: 600;
    }}

    .mn-list-item small {{
        color: {KIMI_GRAY};
        display: block;
        margin-top: 4px;
        line-height: 1.55;
    }}

    .mn-memory-card {{
        display: grid;
        gap: 10px;
        padding: 15px 16px;
        border-radius: 20px;
        background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(255,255,255,0.72));
        border: 1px solid rgba(23,24,28,0.07);
        box-shadow: 0 10px 24px rgba(17,24,39,0.035);
    }}

    .mn-memory-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }}

    .mn-memory-kind {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.82rem;
        font-weight: 700;
        color: {KIMI_DARK};
        min-width: 0;
    }}

    .mn-memory-time {{
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-end;
        color: {KIMI_GRAY};
        font-size: 0.76rem;
        white-space: nowrap;
    }}

    .mn-memory-body {{
        color: #2b2d33;
        font-size: 0.88rem;
        line-height: 1.72;
        overflow-wrap: anywhere;
        word-break: break-word;
    }}

    .mn-memory-principle {{
        color: {KIMI_GRAY};
        font-size: 0.78rem;
        line-height: 1.55;
        border-left: 2px solid rgba(0,113,227,0.20);
        padding-left: 10px;
    }}

    .mn-actions {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
    }}

    .mn-action-card {{
        padding: 16px;
        border-radius: 20px;
        background: rgba(255,255,255,0.82);
        border: 1px solid var(--mn-border);
        box-shadow: 0 8px 18px rgba(17,24,39,0.03);
    }}

    .mn-action-card .title {{
        font-size: 0.96rem;
        font-weight: 700;
        color: {KIMI_DARK};
        margin-bottom: 6px;
    }}

    .mn-action-card .desc {{
        font-size: 0.82rem;
        color: {KIMI_GRAY};
        line-height: 1.6;
    }}

    div[data-testid="stForm"] {{
        border: 1px solid rgba(23,24,28,0.08);
        border-radius: 20px;
        background: rgba(255,255,255,0.72);
        box-shadow: 0 10px 28px rgba(17,24,39,0.04);
        padding: 16px 18px 10px;
    }}

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {{
        background: rgba(255,255,255,0.88) !important;
        border-radius: 14px !important;
        border-color: rgba(23,24,28,0.12) !important;
        box-shadow: none !important;
    }}

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus {{
        border-color: rgba(0,113,227,0.35) !important;
        box-shadow: 0 0 0 3px rgba(0,113,227,0.10) !important;
    }}

    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {{
        border-radius: 14px !important;
        border: 1px solid rgba(23,24,28,0.08) !important;
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(245,247,250,0.95)) !important;
        color: {KIMI_DARK} !important;
        box-shadow: 0 8px 18px rgba(17,24,39,0.04) !important;
        transition: all 160ms ease !important;
    }}

    div[data-testid="stButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {{
        transform: translateY(-1px);
        border-color: rgba(0,113,227,0.20) !important;
        box-shadow: 0 12px 24px rgba(17,24,39,0.08) !important;
    }}

    div[data-testid="stExpander"] {{
        border: 1px solid rgba(23,24,28,0.08);
        border-radius: 18px;
        background: rgba(255,255,255,0.78);
        box-shadow: 0 8px 20px rgba(17,24,39,0.03);
    }}

    div[data-testid="stExpander"] details summary {{
        font-weight: 600;
        color: {KIMI_DARK};
    }}

    [data-testid="stMetric"] {{
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(23,24,28,0.08);
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(17,24,39,0.04);
        padding: 12px 14px;
    }}

    [data-testid="stRadio"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label {{
        color: {KIMI_GRAY};
    }}

    h1, h2, h3 {{
        color: {KIMI_DARK} !important;
        font-weight: 600 !important;
    }}

    .kimi-card {{
        background: {KIMI_CARD_BG};
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 2px 20px rgba(0,0,0,0.04);
        border: 1px solid {KIMI_BORDER};
        transition: all 0.3s ease;
        margin-bottom: 16px;
    }}

    .kimi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }}

    .kimi-stat {{
        text-align: center;
        padding: 20px;
    }}

    .kimi-stat .number {{
        font-size: 2.5rem;
        font-weight: 700;
        color: {KIMI_DARK};
        line-height: 1;
    }}

    .kimi-stat .label {{
        font-size: 0.875rem;
        color: {KIMI_GRAY};
        margin-top: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .kimi-badge {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.03em;
    }}

    .badge-hot {{ background: rgba(52,199,89,0.12); color: #34c759; }}
    .badge-warm {{ background: rgba(255,149,0,0.12); color: #ff9500; }}
    .badge-cold {{ background: rgba(142,142,147,0.12); color: #8e8e93; }}

    .layer-l0 {{
        background: rgba(0,113,227,0.08);
        border-left: 3px solid {KIMI_BLUE};
        padding: 12px 16px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 8px;
    }}

    .layer-l1 {{
        background: rgba(175,82,222,0.08);
        border-left: 3px solid #af52de;
        padding: 12px 16px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 8px;
    }}

    .layer-l2 {{
        background: rgba(52,199,89,0.08);
        border-left: 3px solid #34c759;
        padding: 12px 16px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 8px;
    }}

    .expand-btn {{
        background: none;
        border: none;
        color: {KIMI_BLUE};
        font-size: 0.8rem;
        cursor: pointer;
        padding: 4px 0;
    }}

    .expand-btn:hover {{
        text-decoration: underline;
    }}

    .phase-bar {{
        display: flex;
        gap: 2px;
        border-radius: 8px;
        overflow: hidden;
        height: 32px;
    }}

    .phase-cell {{
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.6rem;
        color: white;
        font-weight: 600;
        transition: all 0.2s;
        cursor: pointer;
        min-width: 0;
        overflow: hidden;
    }}

    .phase-cell:hover {{
        filter: brightness(1.2);
        flex: 2;
    }}

    .phase-ok {{ background: #34c759; }}
    .phase-skip {{ background: #8e8e93; }}
    .phase-warn {{ background: #ff9500; }}
    .phase-err {{ background: #ff3b30; }}

    .dream-diary {{
        display: grid;
        gap: 12px;
        margin-top: 8px;
    }}

    .dream-diary-item {{
        display: grid;
        grid-template-columns: 32px minmax(0, 1fr);
        gap: 12px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(23,24,28,0.07);
        box-shadow: 0 8px 20px rgba(17,24,39,0.035);
    }}

    .dream-diary-index {{
        width: 28px;
        height: 28px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(0,113,227,0.10);
        color: {KIMI_BLUE};
        font-size: 0.78rem;
        font-weight: 800;
    }}

    .dream-diary-title {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 4px;
    }}

    .dream-diary-title strong {{
        color: {KIMI_DARK};
        font-size: 0.94rem;
    }}

    .dream-diary-body {{
        color: #3a3d44;
        font-size: 0.86rem;
        line-height: 1.7;
    }}

    .dream-diary-muted {{
        color: {KIMI_GRAY};
        font-size: 0.76rem;
        margin-top: 4px;
    }}

    .skill-card {{
        background: rgba(255,255,255,0.88);
        border: 1px solid var(--mn-border);
        border-radius: 22px;
        padding: 18px;
        box-shadow: 0 12px 30px rgba(17,24,39,0.04);
    }}

    .skill-title {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 10px;
    }}

    .skill-title h3 {{
        margin: 0;
        font-size: 1rem;
    }}

    .skill-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
    }}

    .skill-meta span {{
        display: inline-flex;
        align-items: center;
        padding: 4px 8px;
        border-radius: 999px;
        background: rgba(0,0,0,0.04);
        color: {KIMI_GRAY};
        font-size: 0.72rem;
    }}

    .mn-empty {{
        padding: 32px;
        text-align: center;
        color: {KIMI_GRAY};
    }}

    .mn-empty .emoji {{
        font-size: 2rem;
        margin-bottom: 10px;
    }}

    .mn-divider {{
        height: 1px;
        background: rgba(23,24,28,0.08);
        margin: 16px 0;
    }}
</style>
"""
