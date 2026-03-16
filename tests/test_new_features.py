"""
Testes para as novas funções: score, parcelamento, anomalia,
forecasting, clustering, sazonalidade.
"""
import pytest
from services.data_engine import (
    calcular_score_financeiro,
    detectar_parcelamento,
    detectar_anomalia,
)
from services.forecasting import (
    prever_gastos_categoria,
    calcular_tendencia,
    agrupar_descricoes,
    analisar_sazonalidade,
)


# ═══════════════════════════════════════
# Score de Saúde Financeira
# ═══════════════════════════════════════
class TestScoreFinanceiro:
    def test_excelente(self):
        r = calcular_score_financeiro(
            savings_rate=35, pct_teto=80, meta_batida=True,
            consistencia_std=3, pct_nao_classificados=2,
        )
        assert r["score"] == 100
        assert r["label"] == "Excelente"
        assert r["emoji"] == "🏆"

    def test_critico(self):
        r = calcular_score_financeiro(
            savings_rate=5, pct_teto=110, meta_batida=False,
            consistencia_std=15, pct_nao_classificados=20,
        )
        assert r["score"] < 50
        assert r["label"] == "Crítico"

    def test_pilares_somam_ao_score(self):
        r = calcular_score_financeiro(
            savings_rate=25, pct_teto=90, meta_batida=True,
            consistencia_std=7, pct_nao_classificados=10,
        )
        assert r["score"] == sum(r["pilares"].values())


# ═══════════════════════════════════════
# Detecção de Parcelamentos
# ═══════════════════════════════════════
class TestDetectarParcelamento:
    def test_formato_parc_keyword(self):
        assert detectar_parcelamento("MAGAZINE LUIZA PARC 3/12") == (3, 12)

    def test_formato_parcela_keyword(self):
        assert detectar_parcelamento("LOJA PARCELA 03/12") == (3, 12)

    def test_formato_meio_string(self):
        """Padrão X/Y no meio da string com total > 12"""
        assert detectar_parcelamento("MAGAZINE LUIZA 3/18") == (3, 18)

    def test_sem_parcelamento(self):
        assert detectar_parcelamento("UBER TRIP BR") is None

    def test_vazio(self):
        assert detectar_parcelamento("") is None

    def test_invalido_atual_maior_que_total(self):
        assert detectar_parcelamento("LOJA PARC 15/12") is None

    def test_total_excessivo(self):
        assert detectar_parcelamento("LOJA PARC 1/99") is None

    def test_data_no_inicio_nao_detecta(self):
        """01/03 PAGUE MENOS 1399 — é data, não parcela!"""
        assert detectar_parcelamento("01/03 PAGUE MENOS 1399") is None

    def test_data_dd_mm_nao_detecta(self):
        """12/11 FARMACIA — é data, não parcela!"""
        assert detectar_parcelamento("12/11 FARMACIA POPULAR") is None

    def test_parcela_1_de_1_nao_detecta(self):
        """1/1 não faz sentido como parcelamento."""
        assert detectar_parcelamento("LOJA PARC 1/1") is None


# ═══════════════════════════════════════
# Detecção de Anomalias
# ═══════════════════════════════════════
class TestDetectarAnomalia:
    def test_anomalia_com_zscore(self):
        assert detectar_anomalia(valor=500, media=100, std=50) is True

    def test_normal(self):
        assert detectar_anomalia(valor=120, media=100, std=50) is False

    def test_std_zero(self):
        # Fallback: valor > media * 2
        assert detectar_anomalia(valor=300, media=100, std=0) is True
        assert detectar_anomalia(valor=150, media=100, std=0) is False


# ═══════════════════════════════════════
# Previsão de Gastos (EMA)
# ═══════════════════════════════════════
class TestEMA:
    def test_previsao_basica(self):
        hist = [100, 120, 110, 130]
        r = prever_gastos_categoria(hist, alpha=0.3)
        assert r > 0
        assert isinstance(r, float)

    def test_vazio(self):
        assert prever_gastos_categoria([]) == 0.0

    def test_um_elemento(self):
        assert prever_gastos_categoria([500]) == 500.0


# ═══════════════════════════════════════
# Tendência
# ═══════════════════════════════════════
class TestTendencia:
    def test_subindo(self):
        assert calcular_tendencia([100, 120, 150]) == "↑"

    def test_caindo(self):
        assert calcular_tendencia([150, 120, 100]) == "↓"

    def test_estavel(self):
        assert calcular_tendencia([100, 102, 101]) == "→"

    def test_poucos_dados(self):
        assert calcular_tendencia([100]) == "→"


# ═══════════════════════════════════════
# Clustering de Descrições
# ═══════════════════════════════════════
class TestClustering:
    def test_agrupa_similares(self):
        descricoes = ["UBER TRIP BR", "UBER EATS", "NETFLIX MENSAL"]
        clusters = agrupar_descricoes(descricoes, threshold=0.5)
        # UBER TRIP BR e UBER EATS devem estar juntos
        assert len(clusters) <= 2

    def test_vazio(self):
        assert agrupar_descricoes([]) == {}


# ═══════════════════════════════════════
# Sazonalidade
# ═══════════════════════════════════════
class TestSazonalidade:
    def test_basico(self):
        historico = {
            "01/25": 10000, "02/25": 9500, "03/25": 10200,
            "04/25": 9800, "05/25": 10100, "12/24": 16000,
        }
        r = analisar_sazonalidade(historico)
        assert "12" in r
        assert r["12"]["tipo"] == "alto"

    def test_vazio(self):
        assert analisar_sazonalidade({}) == {}
