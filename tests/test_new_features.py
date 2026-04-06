"""
Testes para score, parcelamento, anomalia, forecasting,
clustering, sazonalidade e helpers do Raio-X.
"""

import pandas as pd

from services.data_engine import (
    calcular_score_financeiro,
    detectar_anomalia,
    detectar_parcelamento,
    normalize_card_filter_list,
)
from services.forecasting import (
    agrupar_descricoes,
    analisar_sazonalidade,
    calcular_tendencia,
    prever_gastos_categoria,
)
from views import tab_historico
from views.tab_raiox import (
    _build_category_context,
    _build_interventions,
    _classify_cycle_status,
)


class TestScoreFinanceiro:
    def test_excelente(self):
        result = calcular_score_financeiro(35, 80, True, 3, 2)
        assert result["score"] == 100
        assert result["label"] == "Excelente"

    def test_critico(self):
        result = calcular_score_financeiro(5, 110, False, 15, 20)
        assert result["score"] < 50
        assert result["label"] == "Crítico"

    def test_pilares_somam_ao_score(self):
        result = calcular_score_financeiro(25, 90, True, 7, 10)
        assert result["score"] == sum(result["pilares"].values())


class TestDetectarParcelamento:
    def test_formato_parc_keyword(self):
        assert detectar_parcelamento("MAGAZINE LUIZA PARC 3/12") == (3, 12)

    def test_formato_meio_string(self):
        assert detectar_parcelamento("MAGAZINE LUIZA 3/18") == (3, 18)

    def test_rejeita_data(self):
        assert detectar_parcelamento("12/11 FARMACIA POPULAR") is None


class TestDetectarAnomalia:
    def test_anomalia_com_zscore(self):
        assert detectar_anomalia(500, 100, 50) is True

    def test_normal(self):
        assert detectar_anomalia(120, 100, 50) is False

    def test_std_zero(self):
        assert detectar_anomalia(300, 100, 0) is True
        assert detectar_anomalia(150, 100, 0) is False


class TestEMA:
    def test_previsao_basica(self):
        result = prever_gastos_categoria([100, 120, 110, 130], alpha=0.3)
        assert result > 0
        assert isinstance(result, float)

    def test_um_elemento(self):
        assert prever_gastos_categoria([500]) == 500.0


class TestTendencia:
    def test_subindo(self):
        assert calcular_tendencia([100, 120, 150]) == "↑"

    def test_estavel(self):
        assert calcular_tendencia([100, 102, 101]) == "→"


class TestClustering:
    def test_agrupa_similares(self):
        clusters = agrupar_descricoes(["UBER TRIP BR", "UBER EATS", "NETFLIX MENSAL"], threshold=0.5)
        assert len(clusters) <= 2


class TestSazonalidade:
    def test_basico(self):
        result = analisar_sazonalidade(
            {
                "01/25": 10000,
                "02/25": 9500,
                "03/25": 10200,
                "04/25": 9800,
                "05/25": 10100,
                "12/24": 16000,
            }
        )
        assert result["12"]["tipo"] == "alto"

    def test_vazio(self):
        assert analisar_sazonalidade({}) == {}


class TestNormalizeCardFilterList:
    def test_aceita_csv(self):
        assert normalize_card_filter_list("1234, 5678") == ["1234", "5678"]

    def test_aceita_lista(self):
        assert normalize_card_filter_list(["1234", " 5678 "]) == ["1234", "5678"]

    def test_vazio(self):
        assert normalize_card_filter_list(None) == []
        assert normalize_card_filter_list("") == []


class TestRaioXHelpers:
    def test_contexto_categoria_ignora_creditos_para_gasto(self):
        current = {
            "df_ops": pd.DataFrame(
                [
                    {"Categoria": "Alimentação", "Valor": 120.0, "Tipo": "debito"},
                    {"Categoria": "Alimentação", "Valor": 35.0, "Tipo": "credito"},
                    {"Categoria": "Transporte", "Valor": 80.0, "Tipo": "debito"},
                ]
            ),
            "total_comprometido": 200.0,
        }
        previous = [
            {"df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 90.0, "Tipo": "debito"}])},
            {"df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 100.0, "Tipo": "debito"}])},
            {"df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 95.0, "Tipo": "debito"}])},
        ]
        context = _build_category_context(current, previous, {"Alimentação": 110.0})
        assert float(context["gasto_debito_por_categoria"]["Alimentação"]) == 120.0
        assert context["credito_total"] == 35.0
        assert context["categorias_acima_do_limite"][0]["categoria"] == "Alimentação"

    def test_status_controlado(self):
        status = _classify_cycle_status(
            False,
            {"saldo_teto": 1500.0, "saldo_variaveis": 700.0, "aporte_real": 3500.0, "pct_teto": 72.0},
            2500.0,
            2.0,
            95.0,
            {"categorias_acima_do_limite": [], "anomalias_relevantes": []},
        )
        assert status["label"] == "Controlado"

    def test_status_em_atencao(self):
        status = _classify_cycle_status(
            False,
            {"saldo_teto": 500.0, "saldo_variaveis": 250.0, "aporte_real": 2200.0, "pct_teto": 88.0},
            2000.0,
            3.0,
            40.0,
            {"categorias_acima_do_limite": [], "anomalias_relevantes": []},
        )
        assert status["label"] == "Em atenção"

    def test_status_critico(self):
        status = _classify_cycle_status(
            False,
            {"saldo_teto": -200.0, "saldo_variaveis": -50.0, "aporte_real": 900.0, "pct_teto": 103.0},
            2000.0,
            0.0,
            20.0,
            {"categorias_acima_do_limite": [], "anomalias_relevantes": []},
        )
        assert status["label"] == "Crítico"

    def test_intervencoes_priorizadas(self):
        cards = _build_interventions(
            True,
            {
                "saldo_teto": -300.0,
                "saldo_variaveis": -120.0,
                "meta_ameacada": True,
                "aporte_real": 1200.0,
                "df_config": pd.DataFrame(),
            },
            2000.0,
            4,
            3,
            {
                "categorias_acima_do_limite": [{"categoria": "Lazer", "limite": 200.0, "atual": 350.0, "excesso": 150.0}],
                "anomalias_relevantes": [{"categoria": "Transporte", "atual": 400.0, "media": 180.0, "pct": 122.0}],
            },
        )
        assert [card["priority"] for card in cards[:4]] == [1, 2, 3, 4]

    def test_contexto_suprime_insights_sem_historico_suficiente(self):
        current = {
            "df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 120.0, "Tipo": "debito"}]),
            "total_comprometido": 120.0,
        }
        previous = [
            {"df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 90.0, "Tipo": "debito"}])},
            {"df_ops": pd.DataFrame([{"Categoria": "Alimentação", "Valor": 100.0, "Tipo": "debito"}])},
        ]
        context = _build_category_context(current, previous, {})
        assert context["anomalias_relevantes"] == []
        assert context["radar"] == []

    def test_tab_historico_importa_sazonalidade(self):
        assert "analisar_sazonalidade" in tab_historico.__dict__
