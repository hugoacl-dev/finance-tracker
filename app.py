import os
import re
import datetime
import subprocess
import streamlit as st
from views.styles import render_styles
from views import tab_raiox, tab_historico, tab_importacao, tab_settings
from core.config import DEFAULTS
from services import get_data_service

@st.cache_data(ttl=3600, show_spinner=False)
def _get_git_info() -> dict:
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        def _run(*args):
            return subprocess.run(list(args), capture_output=True, text=True, cwd=app_dir).stdout.strip()
        short_hash = _run("git", "rev-parse", "--short", "HEAD") or "?"
        full_hash  = _run("git", "rev-parse", "HEAD")
        raw_date   = _run("git", "log", "-1", "--format=%ci")  # e.g. "2026-03-15 22:17:14 -0300"
        message    = _run("git", "log", "-1", "--format=%s")
        remote     = _run("git", "remote", "get-url", "origin")
        date_fmt   = raw_date[:16] if raw_date else ""  # "2026-03-15 22:17"
        # Derivar URL do GitHub a partir do remote
        github_base = ""
        m = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote)
        if m:
            github_base = f"https://github.com/{m.group(1)}"
        else:
            m = re.search(r'/git/([^/]+/[^/]+?)(?:\.git)?$', remote)
            if m:
                github_base = f"https://github.com/{m.group(1)}"
        commit_url = f"{github_base}/commit/{full_hash}" if github_base and full_hash else ""
        return {"hash": short_hash, "full_hash": full_hash, "date": date_fmt,
                "message": message, "url": commit_url}
    except Exception:
        return {"hash": "?", "full_hash": "", "date": "", "message": "", "url": ""}

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

if st.query_params.get("prototype") == "raiox":
    from views.prototype_raiox_fintech import render_page as render_raiox_prototype

    render_raiox_prototype()
    st.stop()

# Perfil Ativo (Multi-Tenant)
st.session_state["perfil_ativo"] = st.sidebar.radio("👤 Perfil Atual", ["Principal", "Dependente"], key="perfil_global")

render_styles()

perfil_ativo = st.session_state["perfil_ativo"]

# Inicializar DataService (Supabase)
data_service = get_data_service()
if getattr(data_service, "mode", "") == "local":
    st.sidebar.warning("Modo local de demonstracao ativo. Dados do Supabase nao estao conectados.")

# Carregar dados do perfil ativo
cfg_raw = data_service.get_profile_config(perfil_ativo)
cfg = {**DEFAULTS, **cfg_raw} if cfg_raw else DEFAULTS.copy()

# ── Sidebar: versão e última importação ──
_git = _get_git_info()
_version_link = f"[`{_git['hash']}`]({_git['url']})" if _git['url'] else f"`{_git['hash']}`"
_sidebar_lines = [f"versão {_version_link}"]
if _git['date']:
    _sidebar_lines.append(f"{_git['date']} · {_git['message'][:60]}")
st.sidebar.markdown("---")
st.sidebar.caption("  \n".join(_sidebar_lines))
_ultima_imp_raw = (cfg_raw or {}).get("Ultima_Importacao")
if _ultima_imp_raw:
    try:
        _dt = datetime.datetime.fromisoformat(_ultima_imp_raw)
        _ultima_fmt = _dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        _ultima_fmt = _ultima_imp_raw
    st.sidebar.caption(f"🕒 Última importação: {_ultima_fmt}")

mensal_data = data_service.get_mensal_data(perfil_ativo)
transacoes_data = data_service.get_transacoes_data(perfil_ativo)
goals_data = data_service.get_goals(perfil_ativo)
category_budgets_data = data_service.get_category_budgets(perfil_ativo)

# Inject into Session State for the Views
st.session_state["cfg"] = cfg
st.session_state["cfg_raw"] = cfg_raw
st.session_state["transacoes_data"] = transacoes_data
st.session_state["mensal_data"] = mensal_data
st.session_state["goals_data"] = goals_data
st.session_state["category_budgets_data"] = category_budgets_data
st.session_state["data_service"] = data_service

# ── Onboarding Guard ──
all_meses = list(set(mensal_data) | set(transacoes_data))
onboarding_done = cfg_raw.get("onboarding_done", False) if cfg_raw else False

if not all_meses and not onboarding_done and not st.session_state.get("onboarding_done"):
    from views.onboarding import render_onboarding
    render_onboarding()
else:
    # TABS
    tab_raio_x, tab_historico_t, tab_insights, tab_config = st.tabs(
        ["🔬 Raio-X", "📈 Histórico", "🤖 IA", "⚙️ Config"])

    with tab_raio_x:
        tab_raiox.render_page()

    with tab_historico_t:
        tab_historico.render_page()

    with tab_insights:
        tab_importacao.render_page()

    with tab_config:
        tab_settings.render_page()

# Rodapé
st.markdown("---")
_footer_parts = ["Finance Tracker © 2026", _version_link]
if _git['date']:
    _footer_parts.append(_git['date'])
    _footer_parts.append(_git['message'][:60])
if _ultima_imp_raw:
    try:
        _dt = datetime.datetime.fromisoformat(_ultima_imp_raw)
        _footer_parts.append(f"🕒 Última importação: {_dt.strftime('%d/%m/%Y às %H:%M')}")
    except Exception:
        _footer_parts.append(f"🕒 Última importação: {_ultima_imp_raw}")
st.caption(" · ".join(_footer_parts))
