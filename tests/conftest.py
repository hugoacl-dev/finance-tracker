"""
Fixtures reutilizáveis para testes do FTracker.
"""
import pytest
import pandas as pd


@pytest.fixture
def cfg_default():
    return {
        "Receita_Base": 21000.0,
        "Meta_Aporte": 10000.0,
        "Teto_Gastos": 11000.0,
        "Dia_Fechamento": 13,
    }


@pytest.fixture
def df_config_vazio():
    return pd.DataFrame()


@pytest.fixture
def df_ops_vazio():
    return pd.DataFrame()


@pytest.fixture
def df_config_sample():
    return pd.DataFrame([
        {"Descricao_Fatura": "Aluguel", "Valor": 2500.0, "Tipo": "Nao_Cartao"},
        {"Descricao_Fatura": "Plano Saúde", "Valor": 850.0, "Tipo": "Nao_Cartao"},
        {"Descricao_Fatura": "Netflix", "Valor": 55.90, "Tipo": "Cartao"},
        {"Descricao_Fatura": "Spotify", "Valor": 34.90, "Tipo": "Cartao"},
    ])


@pytest.fixture
def df_ops_sample():
    return pd.DataFrame([
        {"Descricao": "UBER TRIP", "Valor": 45.00, "Categoria": "Transporte", "Cartao": "1111"},
        {"Descricao": "IFOOD", "Valor": 89.90, "Categoria": "Alimentação", "Cartao": "1111"},
        {"Descricao": "AMAZON", "Valor": 350.00, "Categoria": "Compras", "Cartao": "2222"},
        {"Descricao": "NETFLIX", "Valor": 55.90, "Categoria": "Streaming", "Cartao": "1111"},
        {"Descricao": "COBASI", "Valor": 120.00, "Categoria": "Pet", "Cartao": "1111"},
    ])


@pytest.fixture
def df_ops_dependente():
    """Transações com cartão 3333 (dependente)."""
    return pd.DataFrame([
        {"Descricao": "UBER TRIP", "Valor": 30.00, "Categoria": "Transporte", "Cartao": "3333"},
        {"Descricao": "FARMACIA", "Valor": 65.00, "Categoria": "Saúde", "Cartao": "3333"},
        {"Descricao": "MERCADO", "Valor": 200.00, "Categoria": "Alimentação", "Cartao": "1111"},
    ])
