import streamlit as st
from views.styles import render_styles
from views import tab_raiox, tab_historico, tab_importacao, tab_settings
from core.config import DEFAULTS
from services import get_data_service

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# Perfil Ativo (Multi-Tenant)
st.session_state["perfil_ativo"] = st.sidebar.radio("👤 Perfil Atual", ["Principal", "Dependente"], key="perfil_global")
st.sidebar.markdown("---")

render_styles()

perfil_ativo = st.session_state["perfil_ativo"]

# Inicializar DataService (Supabase)
data_service = get_data_service()

# Carregar dados do perfil ativo
cfg_raw = data_service.get_profile_config(perfil_ativo)
cfg = {**DEFAULTS, **cfg_raw} if cfg_raw else DEFAULTS.copy()

mensal_data = data_service.get_mensal_data(perfil_ativo)
transacoes_data = data_service.get_transacoes_data(perfil_ativo)

# Inject into Session State for the Views
st.session_state["cfg"] = cfg
st.session_state["cfg_raw"] = cfg_raw
st.session_state["transacoes_data"] = transacoes_data
st.session_state["mensal_data"] = mensal_data
st.session_state["data_service"] = data_service

# ── Onboarding Guard ──
all_meses = list(transacoes_data.keys())
onboarding_done = cfg_raw.get("onboarding_done", False) if cfg_raw else False

if not all_meses and not onboarding_done and not st.session_state.get("onboarding_done"):
    from views.onboarding import render_onboarding
    render_onboarding()
else:
    # TABS
    tab_raio_x, tab_historico_t, tab_insights, tab_config = st.tabs(
        ["🔬 Raio-X do Ciclo", "📈 Evolução Histórica", "🤖 Insights IA", "⚙️ Configurações"])

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
st.caption("Finance Tracker © 2026")
