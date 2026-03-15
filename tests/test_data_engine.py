"""
Testes unitários para services/data_engine.py
Cobre: dias_ate_fechamento, normalize_text, is_similar, processar_mes,
       filtro_titularidade, filtro_dedup_fixos, process_idempotency_pass.
"""
import pytest
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from services.data_engine import (
    normalize_text,
    is_similar,
    dias_ate_fechamento,
    filtro_titularidade,
    filtro_dedup_fixos,
    processar_mes,
    process_idempotency_pass,
)


# ═══════════════════════════════════════
# normalize_text
# ═══════════════════════════════════════
class TestNormalizeText:
    def test_acentos(self):
        assert normalize_text("Café") == "CAFE"

    def test_especiais(self):
        assert normalize_text("UBER *TRIP BR") == "UBERTRIPBR"

    def test_vazio(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_numeros(self):
        assert normalize_text("PAG*123") == "PAG123"


# ═══════════════════════════════════════
# is_similar
# ═══════════════════════════════════════
class TestIsSimilar:
    def test_identicos(self):
        assert is_similar("UBER TRIP", "UBER TRIP") is True

    def test_similares(self):
        assert is_similar("UBER TRIP BR", "UBER TRIP") is True

    def test_diferentes(self):
        assert is_similar("UBER", "NETFLIX") is False

    def test_threshold_custom(self):
        assert is_similar("AB", "AC", threshold=0.9) is False
        assert is_similar("AB", "AC", threshold=0.3) is True


# ═══════════════════════════════════════
# dias_ate_fechamento
# ═══════════════════════════════════════
class TestDiasAteFechamento:
    def _mock_hoje(self, ano, mes, dia):
        """Helper para mockar datetime.now com fuso BR."""
        fuso_br = timezone(timedelta(hours=-3))
        dt = datetime(ano, mes, dia, 12, 0, 0, tzinfo=fuso_br)
        return patch("services.data_engine.datetime", wraps=datetime, **{
            "now.return_value": dt,
        })

    def test_antes_do_fechamento(self):
        # dia 5, fechamento dia 13 → 13-5+1 = 9 dias
        with self._mock_hoje(2025, 3, 5):
            resultado = dias_ate_fechamento(13)
            assert resultado == 9

    def test_no_dia_do_fechamento(self):
        # dia 13, fechamento dia 13 → 1 dia (o próprio dia)
        with self._mock_hoje(2025, 3, 13):
            resultado = dias_ate_fechamento(13)
            assert resultado == 1

    def test_apos_fechamento(self):
        # dia 15, fechamento dia 13 → próximo mês 13 - 15 de março
        with self._mock_hoje(2025, 3, 15):
            resultado = dias_ate_fechamento(13)
            assert resultado > 25  # ~30 dias

    def test_dezembro_virada_ano(self):
        # dia 20 dezembro, fechamento dia 13 → 13 janeiro
        with self._mock_hoje(2025, 12, 20):
            resultado = dias_ate_fechamento(13)
            assert resultado > 20

    def test_resultado_sempre_positivo(self):
        with self._mock_hoje(2025, 6, 1):
            resultado = dias_ate_fechamento(13)
            assert resultado > 0


# ═══════════════════════════════════════
# filtro_titularidade
# ═══════════════════════════════════════
class TestFiltroTitularidade:
    def test_exclui_cartao_configurado(self, df_ops_dependente):
        resultado = filtro_titularidade(
            df_ops_dependente, "Principal",
            cartoes_aceitos=["1111"], cartoes_excluidos=["3333"],
        )
        # Deve remover as 2 linhas com cartão 3333, manter a do 1111
        assert len(resultado) == 1
        assert resultado.iloc[0]["Descricao"] == "MERCADO"

    def test_sem_config_nao_filtra(self, df_ops_dependente):
        resultado = filtro_titularidade(df_ops_dependente, "Dependente")
        assert len(resultado) == len(df_ops_dependente)

    def test_aceita_somente_configurados(self):
        df = pd.DataFrame([
            {"Descricao": "A", "Valor": 10, "Cartao": "1111"},
            {"Descricao": "B", "Valor": 20, "Cartao": "9999"},
        ])
        resultado = filtro_titularidade(df, "Principal", cartoes_aceitos=["1111"])
        assert len(resultado) == 1
        assert resultado.iloc[0]["Descricao"] == "A"

    def test_df_vazio(self, df_ops_vazio):
        resultado = filtro_titularidade(df_ops_vazio, "Principal")
        assert resultado.empty

    def test_sem_coluna_cartao(self):
        df = pd.DataFrame([{"Descricao": "teste", "Valor": 10}])
        resultado = filtro_titularidade(df, "Principal")
        assert len(resultado) == 1


# ═══════════════════════════════════════
# filtro_dedup_fixos
# ═══════════════════════════════════════
class TestFiltroDedup:
    def test_remove_fixo_cartao_duplicado(self):
        df_config = pd.DataFrame([
            {"Descricao_Fatura": "NETFLIX", "Valor": 55.90, "Tipo": "Cartao"},
        ])
        df_ops = pd.DataFrame([
            {"Descricao": "Netflix Mensal", "Valor": 55.90, "Categoria": "Streaming"},
            {"Descricao": "IFOOD", "Valor": 30.00, "Categoria": "Alimentação"},
        ])
        resultado = filtro_dedup_fixos(df_ops, df_config)
        assert len(resultado) == 1
        assert resultado.iloc[0]["Descricao"] == "IFOOD"

    def test_nao_remove_fixo_nao_cartao(self):
        df_config = pd.DataFrame([
            {"Descricao_Fatura": "Aluguel", "Valor": 2500.0, "Tipo": "Nao_Cartao"},
        ])
        df_ops = pd.DataFrame([
            {"Descricao": "ALUGUEL PIX", "Valor": 2500.0, "Categoria": "Moradia"},
        ])
        resultado = filtro_dedup_fixos(df_ops, df_config)
        assert len(resultado) == 1  # Não remove porque tipo != Cartao

    def test_ambos_vazios(self, df_config_vazio, df_ops_vazio):
        resultado = filtro_dedup_fixos(df_ops_vazio, df_config_vazio)
        assert resultado.empty


# ═══════════════════════════════════════
# processar_mes
# ═══════════════════════════════════════
class TestProcessarMes:
    def test_mes_completo(self, df_config_sample, df_ops_sample):
        r = processar_mes(
            df_config_sample, df_ops_sample,
            perfil_ativo="Principal",
            teto_gastos=11000, receita_base=21000, meta_aporte=10000,
        )
        assert r["total_fixos"] == pytest.approx(3440.80, abs=0.01)
        # Netflix é fixo de cartão → é removido do df_ops pelo dedup
        # Total variáveis = 45 + 89.90 + 350 + 120 = 604.90
        assert r["total_variaveis"] == pytest.approx(604.90, abs=0.01)
        assert r["total_comprometido"] == pytest.approx(r["total_fixos"] + r["total_variaveis"], abs=0.01)
        assert r["aporte_real"] == pytest.approx(21000 - r["total_comprometido"], abs=0.01)

    def test_mes_vazio(self, df_config_vazio, df_ops_vazio):
        r = processar_mes(
            df_config_vazio, df_ops_vazio,
            perfil_ativo="Principal",
            teto_gastos=11000, receita_base=21000, meta_aporte=10000,
        )
        assert r["total_fixos"] == 0
        assert r["total_variaveis"] == 0
        assert r["aporte_real"] == 21000
        assert r["meta_ameacada"] == False

    def test_meta_ameacada(self, df_config_sample):
        """Quando gastos variáveis são altos demais, meta é ameaçada."""
        df_ops_alto = pd.DataFrame([
            {"Descricao": "VIAGEM", "Valor": 8000.0, "Categoria": "Lazer", "Cartao": "1111"},
        ])
        r = processar_mes(
            df_config_sample, df_ops_alto,
            perfil_ativo="Principal",
            teto_gastos=11000, receita_base=21000, meta_aporte=10000,
        )
        # aporte_real = 21000 - (3440.80 + 8000) = 9559.20 < 10000
        assert r["meta_ameacada"] == True

    def test_saldo_teto(self, df_config_sample, df_ops_sample):
        r = processar_mes(
            df_config_sample, df_ops_sample,
            perfil_ativo="Principal",
            teto_gastos=11000, receita_base=21000, meta_aporte=10000,
        )
        assert r["saldo_teto"] == pytest.approx(11000 - r["total_comprometido"], abs=0.01)

    def test_pct_teto(self, df_config_sample, df_ops_sample):
        r = processar_mes(
            df_config_sample, df_ops_sample,
            perfil_ativo="Principal",
            teto_gastos=11000, receita_base=21000, meta_aporte=10000,
        )
        expected = (r["total_comprometido"] / 11000) * 100
        assert r["pct_teto"] == pytest.approx(expected, abs=0.01)


# ═══════════════════════════════════════
# process_idempotency_pass
# ═══════════════════════════════════════
class TestIdempotencyPass:
    def test_marca_duplicata(self):
        trans = [{"Cartao": "1111", "Descricao": "UBER TRIP", "Valor": 45.0}]
        existing = [{"Cartao": "1111", "Descricao": "UBER TRIP", "Valor": 45.0}]
        buffers = {"Principal": existing}

        def match_fn(sim, price_diff):
            return sim >= 0.8 and price_diff < 0.05

        process_idempotency_pass(trans, buffers, match_fn)
        assert trans[0].get("is_dupe") is True

    def test_nao_marca_diferente(self):
        trans = [{"Cartao": "1111", "Descricao": "UBER", "Valor": 45.0}]
        existing = [{"Cartao": "1111", "Descricao": "NETFLIX", "Valor": 55.0}]
        buffers = {"Principal": existing}

        def match_fn(sim, price_diff):
            return sim >= 0.8 and price_diff < 0.05

        process_idempotency_pass(trans, buffers, match_fn)
        assert trans[0].get("is_dupe") is not True

    def test_ignora_ignorados(self):
        trans = [{"Cartao": "1111", "Descricao": "UBER", "Valor": 45.0, "dest_profile": "Ignorar"}]
        buffers = {"Principal": [{"Cartao": "1111", "Descricao": "UBER", "Valor": 45.0}]}

        def match_fn(sim, price_diff):
            return sim >= 0.8 and price_diff < 0.05

        process_idempotency_pass(trans, buffers, match_fn)
        assert trans[0].get("is_dupe") is not True
