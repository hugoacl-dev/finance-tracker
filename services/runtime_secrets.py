"""
Helpers para ler configuracoes sensiveis sem acoplar o app a um unico backend.
"""
import os

import streamlit as st


def get_secret(name: str, default=None):
    """Lê primeiro do ambiente e depois de st.secrets, com fallback seguro."""
    env_value = os.getenv(name)
    if env_value:
        return env_value

    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def has_supabase_credentials() -> bool:
    """Indica se as credenciais minimas do Supabase estao disponiveis."""
    return bool(get_secret("SUPABASE_URL")) and bool(get_secret("SUPABASE_KEY"))
