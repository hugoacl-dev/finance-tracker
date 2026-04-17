import streamlit as st
import streamlit.components.v1 as components


def _detect_theme() -> str:
    """Detecta o tema ativo do Streamlit (light ou dark).
    
    Usada pelas views para decisões server-side (ex: template Plotly).
    Limitação: retorna o valor do config, não a escolha runtime do usuário.
    """
    try:
        base = st.get_option("theme.base")
        if base:
            return base
    except Exception:
        pass
    return "dark"


def _inject_theme_bridge():
    """
    Injeta um micro-script JS que observa a cor de fundo real do .stApp
    (controlada pelo Streamlit/Emotion) e sincroniza um atributo
    data-theme no <html>. O CSS customizado usa esse atributo para
    alternar tokens de cor — garantindo coerência entre componentes
    nativos e customizados independente de como o tema foi escolhido
    (toggle manual, System, ou config.toml).
    """
    components.html(
        """
        <script>
        (function() {
            function syncTheme() {
                const app = window.parent.document.querySelector('.stApp');
                if (!app) return;
                const bg = getComputedStyle(app).backgroundColor;
                // Heurística: se o canal R do rgb() for < 128, é dark
                const m = bg.match(/\\d+/g);
                const isDark = m ? parseInt(m[0]) < 128 : true;
                window.parent.document.documentElement.setAttribute(
                    'data-theme', isDark ? 'dark' : 'light'
                );
            }
            // Observar mudanças no estilo do .stApp (Emotion troca classes)
            const observer = new MutationObserver(syncTheme);
            const target = window.parent.document.querySelector('.stApp');
            if (target) {
                observer.observe(target, { attributes: true, attributeFilter: ['class'] });
            }
            // Sync inicial
            syncTheme();
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def render_styles():
    """
    Injeta o Design System completo.

    A estratégia de temas funciona em 2 camadas:
    1. _inject_theme_bridge(): script JS que detecta o tema real do Streamlit
       e marca <html data-theme="light|dark">.
    2. CSS usa :root (light padrão) + html[data-theme="dark"] :root (override).
       Também inclui @media (prefers-color-scheme: dark) como fallback imediato
       para evitar flash de tema errado antes do JS executar.
    """

    _inject_theme_bridge()

    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap');

    /* ═══════════════════════════════════════
       TOKENS — Light (padrão)
       ═══════════════════════════════════════ */
    :root {
        --bg-canvas: #F7F7F3;
        --bg-surface: #FFFFFF;
        --bg-surface-alt: #F2F4EF;
        --bg-surface-emphasis: #EDEAE1;
        --border-subtle: #E7E4DB;
        --border-strong: #D6D1C4;
        --text-primary: #16181D;
        --text-secondary: #667085;
        --text-subtle: #8A8F98;
        --brand-primary: #0F766E;
        --brand-soft: #DDF3EF;
        --brand-soft-alt: rgba(15,118,110,0.08);
        --info: #2563EB;
        --info-soft: #DBEAFE;
        --success: #15803D;
        --success-soft: #DCFCE7;
        --warning: #B45309;
        --warning-soft: #FEF3C7;
        --danger: #B42318;
        --danger-soft: #FEE4E2;
        --shadow-sm: 0 2px 10px rgba(16,24,40,0.05);
        --shadow-md: 0 10px 24px rgba(16,24,40,0.06);
        --overlay: rgba(255,255,255,0.7);
    }

    /* ═══════════════════════════════════════
       TOKENS — Dark (via JS bridge)
       ═══════════════════════════════════════ */
    html[data-theme="dark"] {
        --bg-canvas: #111318;
        --bg-surface: #171A20;
        --bg-surface-alt: #1E232B;
        --bg-surface-emphasis: #232A33;
        --border-subtle: #2B313C;
        --border-strong: #3A4352;
        --text-primary: #F3F4F6;
        --text-secondary: #98A2B3;
        --text-subtle: #7C8798;
        --brand-primary: #2DD4BF;
        --brand-soft: rgba(45,212,191,0.14);
        --brand-soft-alt: rgba(45,212,191,0.09);
        --info: #60A5FA;
        --info-soft: rgba(96,165,250,0.16);
        --success: #4ADE80;
        --success-soft: rgba(74,222,128,0.14);
        --warning: #FBBF24;
        --warning-soft: rgba(251,191,36,0.14);
        --danger: #F87171;
        --danger-soft: rgba(248,113,113,0.16);
        --shadow-sm: 0 2px 10px rgba(0,0,0,0.22);
        --shadow-md: 0 12px 24px rgba(0,0,0,0.25);
        --overlay: rgba(17,19,24,0.6);
    }

    /* Fallback: se o JS não executou ainda, seguir preferência do SO */
    @media (prefers-color-scheme: dark) {
        html:not([data-theme]) {
            --bg-canvas: #111318;
            --bg-surface: #171A20;
            --bg-surface-alt: #1E232B;
            --bg-surface-emphasis: #232A33;
            --border-subtle: #2B313C;
            --border-strong: #3A4352;
            --text-primary: #F3F4F6;
            --text-secondary: #98A2B3;
            --text-subtle: #7C8798;
            --brand-primary: #2DD4BF;
            --brand-soft: rgba(45,212,191,0.14);
            --brand-soft-alt: rgba(45,212,191,0.09);
            --info: #60A5FA;
            --info-soft: rgba(96,165,250,0.16);
            --success: #4ADE80;
            --success-soft: rgba(74,222,128,0.14);
            --warning: #FBBF24;
            --warning-soft: rgba(251,191,36,0.14);
            --danger: #F87171;
            --danger-soft: rgba(248,113,113,0.16);
            --shadow-sm: 0 2px 10px rgba(0,0,0,0.22);
            --shadow-md: 0 12px 24px rgba(0,0,0,0.25);
            --overlay: rgba(17,19,24,0.6);
        }
    }

    /* ═══════════════════════════════════════
       BASE & LAYOUT
       ═══════════════════════════════════════ */

    html, body, [class*="stApp"] {
        font-family: 'Manrope', system-ui, sans-serif;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums lining-nums;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, var(--brand-soft-alt), transparent 34%),
            linear-gradient(180deg, var(--bg-canvas), var(--bg-canvas));
    }

    [data-testid="stAppViewContainer"] > .main {
        background: transparent;
    }

    .block-container {
        padding-top: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 1380px;
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--border-subtle);
    }

    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-secondary) !important;
    }

    /* ═══════════════════════════════════════
       TABS
       ═══════════════════════════════════════ */

    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        min-height: 44px;
        padding: 0.65rem 0.75rem !important;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.82rem !important;
        letter-spacing: 0;
        color: var(--text-secondary);
    }

    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: var(--bg-surface);
        color: var(--text-primary);
        box-shadow: var(--shadow-sm);
    }

    /* ═══════════════════════════════════════
       SECTION HEADERS & CONTEXT
       ═══════════════════════════════════════ */

    .section-header {
        margin: 1.25rem 0 0.65rem 0;
        padding-bottom: 0.45rem;
        border-bottom: 1px solid var(--border-subtle);
        color: var(--text-secondary);
        font-size: 0.88rem;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: none;
    }

    .header-params {
        display: flex;
        flex-wrap: wrap;
        gap: .35rem .5rem;
        color: var(--text-secondary);
        font-size: 0.78rem;
    }

    .context-bar {
        display: grid;
        grid-template-columns: 1fr;
        gap: 0.65rem;
        margin: 0.25rem 0 1rem 0;
    }

    .context-chip {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 0.8rem 0.95rem;
        box-shadow: var(--shadow-sm);
    }

    .context-chip .label {
        color: var(--text-secondary);
        font-size: 0.72rem;
        font-weight: 700;
        margin-bottom: 0.15rem;
    }

    .context-chip .value {
        color: var(--text-primary);
        font-size: 1rem;
        font-weight: 700;
    }

    /* ═══════════════════════════════════════
       HERO / SURVIVAL CARD
       ═══════════════════════════════════════ */

    .hero-card,
    .survival-card {
        background:
            linear-gradient(180deg, var(--bg-surface), var(--bg-surface-alt));
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 1.15rem;
        color: var(--text-primary);
        box-shadow: var(--shadow-md);
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
        text-align: left;
    }

    .hero-card::before,
    .survival-card::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, var(--brand-soft-alt), transparent 55%);
        pointer-events: none;
    }

    .hero-card .label,
    .survival-card .label {
        color: var(--text-secondary);
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: none;
        position: relative;
    }

    .hero-card .value,
    .survival-card .value {
        color: var(--brand-primary) !important;
        font-size: clamp(2.2rem, 8vw, 3.5rem);
        line-height: 1.05;
        font-weight: 800;
        margin: 0.25rem 0 0.4rem 0;
        position: relative;
    }

    .hero-card .sub,
    .survival-card .sub {
        color: var(--text-secondary);
        font-size: 0.9rem;
        line-height: 1.4;
        font-weight: 600;
        margin-top: 0.1rem;
        position: relative;
    }

    .hero-card .forecast,
    .survival-card .forecast {
        color: var(--text-secondary);
        font-size: 0.8rem;
        line-height: 1.45;
        margin-top: 0.65rem;
        position: relative;
    }

    .survival-card.danger {
        border-color: var(--danger);
        background: linear-gradient(180deg, var(--bg-surface), var(--danger-soft));
    }

    .survival-card.danger .value {
        color: var(--danger) !important;
    }

    /* ═══════════════════════════════════════
       ACTION CALLOUTS
       ═══════════════════════════════════════ */

    .action-callout {
        border-radius: 14px;
        border: 1px solid var(--border-subtle);
        background: var(--bg-surface);
        padding: 0.95rem 1rem;
        box-shadow: var(--shadow-sm);
        margin-bottom: 0.75rem;
    }

    .action-callout strong {
        display: block;
        margin-bottom: 0.15rem;
    }

    .action-callout.info {
        border-left: 4px solid var(--info);
        background: linear-gradient(180deg, var(--bg-surface), var(--info-soft));
    }

    .action-callout.success {
        border-left: 4px solid var(--success);
        background: linear-gradient(180deg, var(--bg-surface), var(--success-soft));
    }

    .action-callout.warning {
        border-left: 4px solid var(--warning);
        background: linear-gradient(180deg, var(--bg-surface), var(--warning-soft));
    }

    .action-callout.error {
        border-left: 4px solid var(--danger);
        background: linear-gradient(180deg, var(--bg-surface), var(--danger-soft));
    }

    /* ═══════════════════════════════════════
       DANGER ZONE
       ═══════════════════════════════════════ */

    .danger-zone {
        background: linear-gradient(180deg, var(--bg-surface), var(--danger-soft));
        border: 1px solid var(--danger);
        border-radius: 14px;
        padding: 1rem;
        box-shadow: var(--shadow-sm);
    }

    /* ═══════════════════════════════════════
       METRICS
       ═══════════════════════════════════════ */

    div[data-testid="stMetric"] {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 0.95rem 1rem;
        box-shadow: var(--shadow-sm);
        min-height: 0;
    }

    div[data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0;
    }

    div[data-testid="stMetricValue"] > div {
        color: var(--text-primary) !important;
        font-weight: 800;
        font-size: clamp(1.5rem, 4vw, 2.15rem);
        line-height: 1.15;
    }

    div[data-testid="stMetricDelta"] {
        font-size: 0.72rem !important;
    }

    /* ═══════════════════════════════════════
       PROGRESS BARS
       ═══════════════════════════════════════ */

    .progress-outer {
        background: var(--bg-surface-emphasis);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        height: 34px;
        overflow: hidden;
        margin-bottom: 0.45rem;
    }

    .progress-inner {
        height: 100%;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 12px;
        font-weight: 700;
        font-size: 0.78rem;
        color: #fff;
        transition: width .35s ease;
        white-space: nowrap;
        overflow: hidden;
    }

    /* ═══════════════════════════════════════
       BADGES
       ═══════════════════════════════════════ */

    .badge {
        display: inline-flex;
        align-items: center;
        gap: .25rem;
        min-height: 30px;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }

    .badge-green {
        background: var(--success-soft);
        color: var(--success);
    }

    .badge-yellow {
        background: var(--warning-soft);
        color: var(--warning);
    }

    .badge-red {
        background: var(--danger-soft);
        color: var(--danger);
    }

    /* ═══════════════════════════════════════
       SUMMARY TABLES
       ═══════════════════════════════════════ */

    .summary-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        margin-bottom: 1rem;
    }

    .summary-table thead tr {
        background: var(--bg-surface-alt);
    }

    .summary-table th {
        padding: 0.8rem 0.85rem;
        color: var(--text-secondary);
        text-align: left;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: none;
        letter-spacing: 0;
        border-bottom: 1px solid var(--border-subtle);
        white-space: nowrap;
    }

    .summary-table th:last-child,
    .summary-table th:not(:first-child) {
        text-align: right;
    }

    .summary-table td {
        padding: 0.78rem 0.85rem;
        color: var(--text-primary);
        font-size: 0.84rem;
        border-bottom: 1px solid var(--border-subtle);
        line-height: 1.45;
        background: var(--bg-surface);
    }

    .summary-table td:last-child,
    .summary-table td:not(:first-child) {
        text-align: right;
        font-weight: 600;
    }

    .summary-table tr:last-child td {
        border-bottom: none;
    }

    /* ═══════════════════════════════════════
       EXPANDERS
       ═══════════════════════════════════════ */

    div[data-testid="stExpander"] {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle) !important;
        border-radius: 14px;
        box-shadow: var(--shadow-sm);
        margin-bottom: 0.5rem;
        overflow: hidden;
    }

    div[data-testid="stExpander"] > details {
        border: none !important;
    }

    div[data-testid="stExpander"] summary {
        min-height: 44px;
        display: flex;
        align-items: center;
        background: var(--bg-surface);
        color: var(--text-primary);
        padding: 0.85rem 0.95rem !important;
        font-size: 0.88rem;
        font-weight: 700;
    }

    div[data-testid="stExpander"] summary svg {
        fill: var(--text-secondary);
    }

    div[data-testid="stExpander"] > details > div {
        background: var(--bg-surface-alt);
        padding: 0.85rem 0.95rem !important;
    }

    /* ═══════════════════════════════════════
       CATEGORY GAUGES
       ═══════════════════════════════════════ */

    .cat-gauge-label {
        margin-bottom: 0.35rem;
        display: flex;
        justify-content: space-between;
        gap: 0.6rem;
        flex-wrap: wrap;
        color: var(--text-primary);
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* ═══════════════════════════════════════
       FORM ELEMENTS — TOUCH TARGETS
       ═══════════════════════════════════════ */

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stMultiSelect"] > div,
    button[kind="primary"],
    button[kind="secondary"],
    .stButton > button {
        min-height: 44px !important;
        font-size: 0.92rem !important;
    }

    /* ═══════════════════════════════════════
       DATA FRAMES
       ═══════════════════════════════════════ */

    div[data-testid="stDataFrame"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }

    div[data-testid="stDataFrame"] table {
        font-size: 0.8rem !important;
        font-variant-numeric: tabular-nums;
    }

    [data-testid="stHorizontalBlock"] {
        gap: 0.75rem;
    }

    /* ═══════════════════════════════════════
       RESPONSIVE — Tablet (481px+)
       ═══════════════════════════════════════ */

    @media (min-width: 481px) {
        .block-container {
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            padding-top: 1.1rem !important;
        }

        .context-bar {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .section-header {
            font-size: 0.92rem;
        }

        .summary-table th,
        .summary-table td {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }

    /* ═══════════════════════════════════════
       RESPONSIVE — Desktop (769px+)
       ═══════════════════════════════════════ */

    @media (min-width: 769px) {
        .block-container {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-top: 1.35rem !important;
        }

        .context-bar {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .hero-card,
        .survival-card {
            padding: 1.35rem 1.4rem;
        }

        .hero-card .value,
        .survival-card .value {
            font-size: clamp(2.8rem, 5vw, 4rem);
        }

        .section-header {
            margin-top: 1.6rem;
            font-size: 0.95rem;
        }

        div[data-testid="stMetric"] {
            padding: 1rem 1.05rem;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
