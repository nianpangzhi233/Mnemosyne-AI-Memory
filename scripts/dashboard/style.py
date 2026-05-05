KIMI_BLUE = "#0071e3"
KIMI_DARK = "#1d1d1f"
KIMI_GRAY = "#6e6e73"
KIMI_LIGHT = "#f5f5f7"
KIMI_WHITE = "#ffffff"
KIMI_CARD_BG = "#fbfbfd"
KIMI_BORDER = "#e5e5e7"

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }}

    section[data-testid="stSidebar"] {{
        background: {KIMI_DARK} !important;
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

    .main .block-container {{
        padding-top: 2rem !important;
        max-width: 1200px !important;
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
</style>
"""
