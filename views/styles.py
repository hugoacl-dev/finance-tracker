import streamlit as st


def _detect_theme() -> str:
    """Detecta o tema ativo do Streamlit (light ou dark)."""
    try:
        base = st.get_option("theme.base")
        if base:
            return base
    except Exception:
        pass
    return "dark"


def render_styles():
    theme = _detect_theme()
    is_light = (theme == "light")

    # ── Design Tokens condicionais ──
    if is_light:
        tokens = {
            "card_bg":          "#ffffff",
            "card_bg2":         "#f1f5f9",
            "border":           "#e2e8f0",
            "border_strong":    "#cbd5e1",
            "text":             "#1e293b",
            "text_muted":       "#64748b",
            "bar_bg":           "#e2e8f0",
            "survival_grad":    "linear-gradient(135deg, #0284c7, #0ea5e9, #38bdf8)",
            "survival_text":    "#ffffff",
            "shadow":           "0 4px 24px rgba(0,0,0,.08)",
            "shadow_sm":        "0 2px 12px rgba(0,0,0,.06)",
            "accent":           "#0284c7",
            "hover_bg":         "#f8fafc",
            "badge_green_bg":   "rgba(22,163,74,.12)",
            "badge_green_fg":   "#16a34a",
            "badge_yellow_bg":  "rgba(202,138,4,.12)",
            "badge_yellow_fg":  "#ca8a04",
            "badge_red_bg":     "rgba(220,38,38,.12)",
            "badge_red_fg":     "#dc2626",
        }
    else:
        tokens = {
            "card_bg":          "#16162a",
            "card_bg2":         "#1f1f3a",
            "border":           "rgba(255,255,255,0.09)",
            "border_strong":    "rgba(255,255,255,0.22)",
            "text":             "#e0e0f0",
            "text_muted":       "#a0a0c0",
            "bar_bg":           "#1e1e2f",
            "survival_grad":    "linear-gradient(135deg, #0f2027, #203a43, #2c5364)",
            "survival_text":    "#ffffff",
            "shadow":           "0 8px 32px rgba(0,0,0,.35)",
            "shadow_sm":        "0 4px 20px rgba(0,0,0,.25)",
            "accent":           "#00c9ff",
            "hover_bg":         "#1f1f3a",
            "badge_green_bg":   "rgba(0,230,118,.15)",
            "badge_green_fg":   "#00e676",
            "badge_yellow_bg":  "rgba(255,214,0,.15)",
            "badge_yellow_fg":  "#ffd600",
            "badge_red_bg":     "rgba(255,75,43,.15)",
            "badge_red_fg":     "#ff4b2b",
        }

    t = tokens  # alias curto

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap');
    html, body, [class*="stApp"] {{
        font-family: 'Inter', sans-serif;
    }}

    /* ════════════════
       SURVIVAL CARD
    ════════════════ */
    .survival-card {{
        background: {t["survival_grad"]};
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
        color: {t["survival_text"]};
        box-shadow: {t["shadow"]};
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }}
    .survival-card::before {{
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.1);
        pointer-events: none;
    }}
    .survival-card .label {{
        font-size: .85rem;
        text-transform: uppercase;
        letter-spacing: 3px;
        opacity: .75;
        font-weight: 600;
    }}
    .survival-card .value {{
        font-size: 3.8rem;
        font-weight: 900;
        line-height: 1.15;
        margin: .3rem 0;
    }}
    .survival-card .sub {{
        font-size: 1rem;
        opacity: .6;
        margin-top: .3rem;
        font-weight: 500;
    }}
    .survival-card .forecast {{
        font-size: .85rem;
        opacity: .5;
        margin-top: .5rem;
        letter-spacing: .3px;
        font-weight: 500;
    }}
    .survival-card.danger .value {{
        animation: pulse-danger 2s ease-in-out infinite;
    }}
    @keyframes pulse-danger {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50%       {{ opacity: .85; transform: scale(1.03); }}
    }}

    /* ════════════════
       PROGRESS BARS
    ════════════════ */
    .progress-outer {{
        background: {t["bar_bg"]};
        border-radius: 14px;
        height: 38px;
        overflow: hidden;
        box-shadow: inset 0 2px 6px rgba(0,0,0,.15);
        margin-bottom: .4rem;
    }}
    .progress-inner {{
        height: 100%;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 14px;
        font-weight: 700;
        font-size: .85rem;
        color: #fff;
        transition: width .6s cubic-bezier(.4,0,.2,1);
    }}

    /* ════════════════
       ALERTS
    ════════════════ */
    .alert-red {{
        background: linear-gradient(90deg, #ff416c, #ff4b2b);
        color: #fff;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
        font-size: 1.05rem;
        box-shadow: 0 4px 20px rgba(255,65,108,.3);
    }}
    .alert-yellow {{
        background: linear-gradient(90deg, #f7971e, #ffd200);
        color: #1e1e2f;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
        font-size: 1.05rem;
    }}

    /* ════════════════════════════════════
       SUMMARY TABLE  — Estilo Slate
    ════════════════════════════════════ */
    .summary-table {{
        width: 100%;
        border-collapse: collapse;
        background: {t["card_bg"]};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: {t["shadow_sm"]};
        margin-bottom: 1.2rem;
    }}
    .summary-table thead tr {{
        border-bottom: 2px solid {t["border_strong"]};
    }}
    .summary-table th {{
        padding: 14px 18px;
        text-align: left;
        color: {t["text_muted"]};
        text-transform: uppercase;
        font-size: .72rem;
        letter-spacing: 2px;
        font-weight: 700;
        white-space: nowrap;
    }}
    .summary-table th:last-child,
    .summary-table th:not(:first-child) {{
        text-align: right;
    }}
    .summary-table td {{
        padding: 13px 18px;
        color: {t["text"]};
        font-size: .93rem;
        border-bottom: 1px solid {t["border"]};
        line-height: 1.5;
    }}
    .summary-table td:last-child,
    .summary-table td:not(:first-child) {{
        text-align: right;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }}
    .summary-table tr:last-child td {{
        font-weight: 900;
        border-bottom: none;
    }}
    .summary-table tbody tr {{
        transition: background .15s ease;
    }}
    .summary-table tbody tr:hover {{
        background: {t["hover_bg"]};
    }}

    /* ════════════════════════════════════
       EXPANDERS COMO LINHAS DE TABELA
    ════════════════════════════════════ */
    /* Remove bordas gerais e padroniza o fundo */
    div[data-testid="stExpander"] {{
        background: {t["card_bg"]};
        border: none !important;
        border-radius: 14px;
        box-shadow: {t["shadow_sm"]};
        margin-bottom: 0.15rem;
    }}
    div[data-testid="stExpander"] > details {{
        border: none !important;
    }}
    
    /* Header do Expander idêntico ao td da tabela */
    div[data-testid="stExpander"] summary {{
        background: {t["card_bg"]};
        padding: 13px 18px !important;
        border-bottom: 1px solid {t["border"]};
        color: {t["text"]};
        font-size: .93rem;
        transition: background .15s ease;
    }}
    div[data-testid="stExpander"] summary:hover {{
        background: {t["hover_bg"]};
        color: {t["text"]};
    }}
    
    /* Formatação do conteúdo interno do expander (o dataframe) */
    div[data-testid="stExpander"] > details > div {{
        padding: 1rem !important;
        background: {t["card_bg2"]};
        border-bottom-left-radius: 14px;
        border-bottom-right-radius: 14px;
    }}
    
    /* Esconder o ícone svg do summary para usarmos a setinha nativa text-based ou mantê-lo suave */
    div[data-testid="stExpander"] summary svg {{
        margin-right: 0.5rem;
        fill: {t["text_muted"]};
    }}

    /* ════════════════
       METRIC CARDS
    ════════════════ */
    div[data-testid="stMetric"] {{
        background: {t["card_bg"]};
        border-radius: 14px;
        padding: 1.2rem;
        box-shadow: {t["shadow_sm"]};
        border-left: 3px solid {t["accent"]};
        transition: transform .2s ease, box-shadow .2s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: {t["shadow"]};
    }}
    div[data-testid="stMetric"] label {{
        color: {t["text_muted"]} !important;
        font-weight: 600;
        letter-spacing: .8px;
        font-size: .8rem;
    }}
    div[data-testid="stMetricValue"] > div {{
        color: {t["text"]} !important;
        font-weight: 900;
    }}

    /* ════════════════
       SECTION HEADERS
    ════════════════ */
    .section-header {{
        font-size: .95rem;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: {t["text_muted"]};
        margin: 2rem 0 .8rem 0;
        border-bottom: 1px solid {t["border"]};
        padding-bottom: .4rem;
        font-weight: 700;
    }}

    .header-params {{
        display: flex;
        flex-wrap: wrap;
        gap: 0 .6rem;
        font-size: .85rem;
        color: {t["text_muted"]};
        margin-top: -10px;
    }}

    /* ════════════════
       BADGES
    ════════════════ */
    .badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .3px;
        white-space: nowrap;
    }}
    .badge-green  {{ background: {t["badge_green_bg"]};  color: {t["badge_green_fg"]}; }}
    .badge-yellow {{ background: {t["badge_yellow_bg"]}; color: {t["badge_yellow_fg"]}; }}
    .badge-red    {{ background: {t["badge_red_bg"]};    color: {t["badge_red_fg"]}; }}

    /* ════════════════
       CATEGORY GAUGES
    ════════════════ */
    .cat-gauge-label {{
        margin-bottom: 0.3rem;
        font-size: 0.93rem;
        color: {t["text"]};
        display: flex;
        justify-content: space-between;
        font-weight: 500;
    }}

    /* ════════════════
       STREAMLIT OVERRIDES
    ════════════════ */
    /* Tabs */
    div[data-testid="stTabs"] button[data-baseweb="tab"] {{
        font-weight: 600;
        letter-spacing: .5px;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        border-right: 1px solid {t["border"]};
    }}

    /* Rodapé */
    .stCaption {{
        color: {t["text_muted"]} !important;
    }}

    /* ══════════════════════
       TABLET  ≤ 768 px
    ══════════════════════ */
    @media (max-width: 768px) {{
        .survival-card {{
            padding: 2rem 1.5rem;
            border-radius: 16px;
        }}
        .survival-card .value {{ font-size: 3rem; }}

        .summary-table th {{ padding: 12px 14px; }}
        .summary-table td {{ padding: 11px 14px; font-size: .88rem; }}

        div[data-testid="stMetric"] {{ padding: 1rem; }}
        .cycle-state-card {{
            padding: 1.15rem 1.1rem 1rem 1.1rem;
            border-radius: 18px;
        }}
        .state-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
        }}
        .state-grid .state-item:last-child {{
            grid-column: 1 / -1;
        }}
        .state-value {{
            font-size: clamp(1.35rem, 4vw, 1.8rem);
        }}
        .state-summary {{
            font-size: .9rem;
            line-height: 1.5;
        }}
        .intervention-card {{
            padding: .95rem 1rem;
        }}
        .score-topline {{
            align-items: flex-start;
        }}

        /* Gauges: impedir truncamento do label */
        .cat-gauge-label {{
            font-size: .85rem;
            gap: 4px;
        }}
    }}

    /* ══════════════════════════
       MOBILE  ≤ 480 px (iPhone 15 = 393px)
    ══════════════════════════ */
    @media (max-width: 480px) {{

        /* ── Safe-Area para notch + home indicator ── */
        html, body {{
            padding-left: env(safe-area-inset-left, 0);
            padding-right: env(safe-area-inset-right, 0);
        }}
        [class*="stApp"] {{
            padding-bottom: env(safe-area-inset-bottom, 0) !important;
        }}

        /* ── Survival Card ── */
        .survival-card {{
            padding: 1.4rem 1rem;
            border-radius: 14px;
            margin-bottom: .8rem;
        }}
        .survival-card .value  {{ font-size: clamp(2rem, 8vw, 3rem); }}
        .survival-card .label  {{ font-size: .72rem; letter-spacing: 1.5px; }}
        .survival-card .sub    {{ font-size: .82rem; }}
        .survival-card .forecast {{ font-size: .72rem; }}

        /* ── Progress Bars: taller for touch ── */
        .progress-outer {{ height: 32px; border-radius: 10px; }}
        .progress-inner {{
            font-size: .65rem;
            padding-right: 8px;
            border-radius: 10px;
            white-space: nowrap;
            overflow: hidden;
        }}

        /* ── Alerts ── */
        .alert-red, .alert-yellow {{
            font-size: .88rem;
            padding: .7rem .9rem;
            border-radius: 10px;
        }}

        /* ── Summary Table: swipeable horizontal ── */
        .summary-table {{
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: 10px;
        }}
        .summary-table th {{
            padding: 8px 10px;
            font-size: .6rem;
            letter-spacing: .8px;
            white-space: nowrap;
        }}
        .summary-table td {{
            padding: 8px 10px;
            font-size: .8rem;
            white-space: nowrap;
        }}
        /* Primeira coluna sticky (nome da linha) */
        .summary-table td:first-child,
        .summary-table th:first-child {{
            position: sticky;
            left: 0;
            background: {t["card_bg"]};
            z-index: 1;
            min-width: 100px;
            white-space: normal;
            word-break: break-word;
        }}

        /* ── Metric Cards: 2-per-row grid ── */
        div[data-testid="stMetric"] {{
            padding: .7rem .6rem;
            border-radius: 10px;
            min-height: 0;
        }}
        div[data-testid="stMetric"] label {{
            letter-spacing: 0;
            font-size: .65rem;
            line-height: 1.2;
        }}
        div[data-testid="stMetricValue"] > div {{
            font-size: 1rem !important;
        }}
        /* Delta values */
        div[data-testid="stMetricDelta"] {{
            font-size: .65rem !important;
        }}

        /* ── Tabs: compact labels ── */
        div[data-testid="stTabs"] button[data-baseweb="tab"] {{
            font-size: .72rem !important;
            padding: 8px 6px !important;
            letter-spacing: 0 !important;
            min-height: 44px;
        }}

        /* ── Section Headers ── */
        .section-header {{
            font-size: .78rem;
            letter-spacing: .8px;
            margin: 1rem 0 .4rem 0;
        }}

        .header-params {{
            font-size: .72rem;
            gap: 0 .3rem;
        }}

        .cycle-state-card {{
            padding: 1rem .95rem .9rem .95rem;
            border-radius: 14px;
        }}
        .state-topline {{
            flex-direction: column;
            align-items: flex-start;
            gap: .45rem;
            margin-bottom: .75rem;
        }}
        .state-cycle {{
            font-size: .72rem;
            letter-spacing: .45px;
        }}
        .state-grid {{
            grid-template-columns: 1fr;
            gap: .65rem;
        }}
        .state-grid .state-item:last-child {{
            grid-column: auto;
        }}
        .state-item {{
            padding: .85rem .9rem;
            border-radius: 14px;
        }}
        .state-label {{
            font-size: .68rem;
            letter-spacing: .3px;
            margin-bottom: .25rem;
        }}
        .state-value {{
            font-size: clamp(1.3rem, 7vw, 1.9rem);
            word-break: break-word;
        }}
        .state-sub {{
            font-size: .75rem;
            line-height: 1.35;
        }}
        .state-summary {{
            margin-top: .8rem;
            font-size: .88rem;
            line-height: 1.5;
        }}

        /* ── Badges: larger touch targets ── */
        .badge {{
            padding: 5px 12px;
            font-size: .74rem;
            min-height: 32px;
            display: inline-flex;
            align-items: center;
        }}

        /* ── Category Gauge Labels ── */
        .cat-gauge-label {{
            font-size: .78rem;
            flex-wrap: wrap;
            gap: 2px 0;
        }}
        .cat-gauge-label span:last-child {{
            font-size: .72rem;
        }}

        /* ── Sidebar: auto collapse on mobile ── */
        section[data-testid="stSidebar"] {{
            min-width: 0 !important;
        }}

        .intervention-card {{
            padding: .9rem .95rem;
            border-radius: 14px;
            margin-bottom: .65rem;
        }}
        .intervention-title {{
            font-size: .9rem;
            line-height: 1.35;
        }}
        .intervention-line {{
            font-size: .82rem;
            line-height: 1.45;
        }}

        .score-panel {{
            padding: .9rem .95rem;
            border-radius: 14px;
        }}
        .score-topline {{
            flex-direction: column;
            align-items: flex-start;
            gap: .45rem;
        }}
        .score-chip {{
            width: 100%;
            justify-content: center;
            text-align: center;
        }}
        .score-copy {{
            font-size: .88rem;
            line-height: 1.35;
        }}
        .score-note {{
            font-size: .82rem;
            line-height: 1.45;
        }}

        /* ── Inputs & Buttons: min 44px touch target ── */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] > div,
        div[data-testid="stMultiSelect"] > div {{
            min-height: 44px !important;
            font-size: .88rem !important;
        }}
        button[kind="primary"],
        button[kind="secondary"],
        .stButton > button {{
            min-height: 44px !important;
            font-size: .88rem !important;
        }}

        /* ── Dataframes: enable horizontal scroll ── */
        div[data-testid="stDataFrame"] {{
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
        }}
        div[data-testid="stDataFrame"] table {{
            font-size: .78rem !important;
        }}

        /* ── Expander: touch-friendly header ── */
        div[data-testid="stExpander"] summary {{
            min-height: 44px;
            display: flex;
            align-items: center;
            font-size: .85rem;
        }}

        /* ── Score badge: full-width on mobile ── */
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
            display: flex !important;
            flex-wrap: nowrap !important;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
            gap: .25rem;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {{
            display: none;
        }}
        div[data-testid="stTabs"] button[data-baseweb="tab"] {{
            flex: 0 0 auto;
            white-space: nowrap;
        }}

        div[data-testid="stPlotlyChart"] {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        /* ── Form columns: stack vertically ── */
        div[data-testid="stHorizontalBlock"] {{
            flex-wrap: wrap !important;
        }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }}
    }}

    /* ════════════════
       SKELETON LOADING
    ════════════════ */
    .skeleton {{
        background: linear-gradient(90deg, {t["card_bg"]} 25%, {t["card_bg2"]} 50%, {t["card_bg"]} 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        height: 20px;
        margin-bottom: 8px;
    }}
    .skeleton-lg {{ height: 45px; }}
    .skeleton-sm {{ height: 14px; width: 60%; }}
    @keyframes shimmer {{
        0% {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
    }}

    /* ════════════════
       CYCLE STATE
    ════════════════ */
    .cycle-state-card {{
        background: linear-gradient(135deg, {t["card_bg"]}, {t["card_bg2"]});
        border: 1px solid {t["border_strong"]};
        border-radius: 20px;
        padding: 1.4rem 1.4rem 1.1rem 1.4rem;
        box-shadow: {t["shadow_sm"]};
        margin-bottom: 1.2rem;
    }}
    .state-topline {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .8rem;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }}
    .status-pill {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: .38rem .8rem;
        font-weight: 800;
        font-size: .78rem;
        letter-spacing: .4px;
        text-transform: uppercase;
    }}
    .status-positive {{
        background: {t["badge_green_bg"]};
        color: {t["badge_green_fg"]};
    }}
    .status-warning {{
        background: {t["badge_yellow_bg"]};
        color: {t["badge_yellow_fg"]};
    }}
    .status-critical {{
        background: {t["badge_red_bg"]};
        color: {t["badge_red_fg"]};
    }}
    .state-cycle {{
        color: {t["text_muted"]};
        font-size: .8rem;
        font-weight: 700;
        letter-spacing: .6px;
        text-transform: uppercase;
    }}
    .state-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .9rem;
    }}
    .state-item {{
        background: rgba(255,255,255,0.03);
        border: 1px solid {t["border"]};
        border-radius: 16px;
        padding: 1rem;
    }}
    .state-label {{
        color: {t["text_muted"]};
        font-size: .76rem;
        letter-spacing: .4px;
        text-transform: uppercase;
        font-weight: 700;
        margin-bottom: .35rem;
    }}
    .state-value {{
        color: {t["text"]};
        font-size: 1.6rem;
        line-height: 1.15;
        font-weight: 900;
    }}
    .state-sub {{
        color: {t["text_muted"]};
        font-size: .82rem;
        margin-top: .25rem;
    }}
    .state-summary {{
        margin-top: 1rem;
        color: {t["text"]};
        font-size: .96rem;
        line-height: 1.55;
        font-weight: 600;
    }}

    /* ════════════════
       INTERVENTIONS
    ════════════════ */
    .intervention-card {{
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: .75rem;
        border: 1px solid {t["border"]};
        background: {t["card_bg"]};
        box-shadow: {t["shadow_sm"]};
    }}
    .intervention-card.warning {{
        border-left: 4px solid {t["badge_yellow_fg"]};
    }}
    .intervention-card.critical {{
        border-left: 4px solid {t["badge_red_fg"]};
    }}
    .intervention-card.info {{
        border-left: 4px solid {t["accent"]};
    }}
    .intervention-title {{
        color: {t["text"]};
        font-size: .98rem;
        font-weight: 800;
        margin-bottom: .45rem;
    }}
    .intervention-line {{
        color: {t["text_muted"]};
        font-size: .9rem;
        line-height: 1.5;
        margin-bottom: .18rem;
    }}
    .intervention-line strong {{
        color: {t["text"]};
    }}
    .score-panel {{
        border: 1px solid {t["border"]};
        background: linear-gradient(180deg, {t["card_bg"]}, {t["card_bg2"]});
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }}
    .score-topline {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .8rem;
        flex-wrap: wrap;
        margin-bottom: .45rem;
    }}
    .score-chip {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: .3rem .75rem;
        font-size: .82rem;
        font-weight: 800;
        color: {t["text"]};
        background: {t["card_bg2"]};
        border: 1px solid {t["border"]};
    }}
    .score-copy {{
        color: {t["text"]};
        font-size: .95rem;
        font-weight: 700;
    }}
    .score-note {{
        color: {t["text_muted"]};
        font-size: .9rem;
        line-height: 1.5;
    }}

    @media (max-width: 768px) {{
        .cycle-state-card {{
            padding: 1.15rem 1.1rem 1rem 1.1rem;
            border-radius: 18px;
        }}
        .state-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
        }}
        .state-grid .state-item:last-child {{
            grid-column: 1 / -1;
        }}
        .state-value {{
            font-size: clamp(1.35rem, 4vw, 1.8rem);
        }}
        .state-summary {{
            font-size: .9rem;
            line-height: 1.5;
        }}
        .intervention-card {{
            padding: .95rem 1rem;
        }}
        .score-topline {{
            align-items: flex-start;
        }}
    }}

    @media (max-width: 480px) {{
        .cycle-state-card {{
            padding: 1rem .95rem .9rem .95rem;
            border-radius: 14px;
        }}
        .state-topline {{
            flex-direction: column;
            align-items: flex-start;
            gap: .45rem;
            margin-bottom: .75rem;
        }}
        .state-cycle {{
            font-size: .72rem;
            letter-spacing: .45px;
        }}
        .state-grid {{
            grid-template-columns: 1fr;
            gap: .65rem;
        }}
        .state-grid .state-item:last-child {{
            grid-column: auto;
        }}
        .state-item {{
            padding: .85rem .9rem;
            border-radius: 14px;
        }}
        .state-label {{
            font-size: .68rem;
            letter-spacing: .3px;
            margin-bottom: .25rem;
        }}
        .state-value {{
            font-size: clamp(1.3rem, 7vw, 1.9rem);
            word-break: break-word;
        }}
        .state-sub {{
            font-size: .75rem;
            line-height: 1.35;
        }}
        .state-summary {{
            margin-top: .8rem;
            font-size: .88rem;
            line-height: 1.5;
        }}
        .intervention-card {{
            padding: .9rem .95rem;
            border-radius: 14px;
            margin-bottom: .65rem;
        }}
        .intervention-title {{
            font-size: .9rem;
            line-height: 1.35;
        }}
        .intervention-line {{
            font-size: .82rem;
            line-height: 1.45;
        }}
        .score-panel {{
            padding: .9rem .95rem;
            border-radius: 14px;
        }}
        .score-topline {{
            flex-direction: column;
            align-items: flex-start;
            gap: .45rem;
        }}
        .score-chip {{
            width: 100%;
            justify-content: center;
            text-align: center;
        }}
        .score-copy {{
            font-size: .88rem;
            line-height: 1.35;
        }}
        .score-note {{
            font-size: .82rem;
            line-height: 1.45;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

