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
    _build_budget_snapshot,
    _build_category_context,
    _build_interventions,
    _classify_cycle_status,
    _prepare_launch_table,
    _render_cycle_kpis,
    _render_category_ranking,
    _render_launches,
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
    def test_resumo_orcamento_detalha_creditos_sem_quebrar_total_liquido(self):
        snapshot = _build_budget_snapshot(
            {
                "total_fixos": 100.0,
                "total_variaveis": 80.0,
                "total_comprometido": 180.0,
                "saldo_teto": 20.0,
                "aporte_real": 320.0,
                "meta_ameacada": False,
            },
            {
                "gasto_debito_por_categoria": pd.Series({"Compras": 100.0}),
                "credito_total": 20.0,
            },
            250.0,
        )
        labels = [row["label"] for row in snapshot["rows"]]
        assert "Debitos variaveis" in labels
        assert "Creditos/estornos" in labels
        assert "Variaveis liquidas do ciclo" in labels
        credit_row = next(row for row in snapshot["rows"] if row["label"] == "Creditos/estornos")
        net_row = next(row for row in snapshot["rows"] if row["label"] == "Variaveis liquidas do ciclo")
        assert credit_row["value"] == -20.0
        assert net_row["value"] == 80.0

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
            True,
        )
        assert [card["priority"] for card in cards[:4]] == [1, 2, 3, 4]

    def test_intervencoes_fechadas_nao_pedem_acao_imediata_de_conciliacao(self):
        cards = _build_interventions(
            False,
            {
                "saldo_teto": 50.0,
                "saldo_variaveis": 20.0,
                "meta_ameacada": False,
                "aporte_real": 1200.0,
                "df_config": pd.DataFrame(
                    [{"Tipo": "Cartao", "Status_Conciliacao": "⏳ Pendente", "Valor": 55.0, "Descricao_Fatura": "Streaming"}]
                ),
            },
            1000.0,
            0,
            0,
            {"categorias_acima_do_limite": [], "anomalias_relevantes": []},
            False,
        )
        assert cards == []

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

    def test_motivo_do_destaque_usa_contexto_completo_do_ciclo(self):
        full = pd.DataFrame(
            [{"Descricao": f"Mercado {idx}", "Categoria": "Mercado", "Valor": 10.0, "Tipo": "debito"} for idx in range(1, 8)]
            + [{"Descricao": "Mercado fora", "Categoria": "Mercado", "Valor": 100.0, "Tipo": "debito"}]
        )
        filtered = full[full["Descricao"] == "Mercado fora"].copy()
        prepared = _prepare_launch_table(filtered, reference_ops=full)

        assert prepared.iloc[0]["Motivo do destaque"] == "Valor fora do padrão da categoria"
    def test_render_categoria_responsiva_emite_bloco_mobile_e_desktop(self, monkeypatch):
        captured = []

        def fake_markdown(html, unsafe_allow_html=False):
            captured.append(html)

        monkeypatch.setattr("views.tab_raiox.st.markdown", fake_markdown)
        ranking = pd.DataFrame(
            [
                {
                    "Categoria": "Mercado",
                    "Gasto": "R$ 500,00",
                    "% dos debitos": "25.0%",
                    "Referencia": "R$ 450,00",
                    "Leitura": "Acima do limite",
                }
            ]
        )
        _render_category_ranking(ranking)
        assert captured
        assert "class=\"desktop-only\"" in captured[0]
        assert "class=\"mobile-only\"" in captured[0]
        assert "Mercado" in captured[0]

    def test_render_lancamentos_responsivo_preserva_motivo(self, monkeypatch):
        captured = []

        def fake_markdown(html, unsafe_allow_html=False):
            captured.append(html)

        monkeypatch.setattr("views.tab_raiox.st.markdown", fake_markdown)
        launches = pd.DataFrame(
            [
                {
                    "Descricao": "Uber Trip",
                    "Categoria": "Transporte",
                    "Motivo do destaque": "Valor fora do padrão da categoria",
                    "Valor": "R$ 80,00",
                    "Cartao": "Nubank",
                    "Tipo": "Debito",
                }
            ]
        )
        _render_launches(launches)
        assert captured
        assert "Uber Trip" in captured[0]
        assert "Valor fora do padrão da categoria" in captured[0]
        assert "class=\"mobile-stack-card\"" in captured[0]



    def test_render_categoria_mobile_indica_quando_ha_mais_itens(self, monkeypatch):
        captured = []

        def fake_markdown(html, unsafe_allow_html=False):
            captured.append(html)

        monkeypatch.setattr("views.tab_raiox.st.markdown", fake_markdown)
        ranking = pd.DataFrame(
            [
                {"Categoria": f"Cat {idx}", "Gasto": "R$ 10,00", "% dos debitos": "10.0%", "Referencia": "R$ 8,00", "Leitura": "Maior peso do ciclo"}
                for idx in range(1, 6)
            ]
        )
        _render_category_ranking(ranking)
        assert "Mostrando as 4 categorias mais relevantes" in captured[0]

    def test_render_lancamentos_mobile_mostra_resumo_quando_ha_muitos(self, monkeypatch):
        captured = []

        def fake_markdown(html, unsafe_allow_html=False):
            captured.append(html)

        monkeypatch.setattr("views.tab_raiox.st.markdown", fake_markdown)
        launches = pd.DataFrame(
            [
                {"Descricao": f"Compra {idx}", "Categoria": "Mercado", "Motivo do destaque": "?", "Valor": "R$ 10,00", "Cartao": "Nubank", "Tipo": "Debito"}
                for idx in range(10)
            ]
        )
        _render_launches(launches)
        assert "Mostrando os 8 lancamentos mais relevantes" in captured[0]

    def test_render_kpis_emite_bloco_mobile_e_desktop(self, monkeypatch):
        captured = []

        def fake_markdown(html, unsafe_allow_html=False):
            captured.append(html)

        monkeypatch.setattr("views.tab_raiox.st.markdown", fake_markdown)
        _render_cycle_kpis(
            current={"total_variaveis": 500.0, "saldo_teto": 1200.0, "pct_teto": 72.0, "aporte_real": 3000.0, "df_ops": pd.DataFrame()},
            meta_aporte=2500.0,
            previous={"total_variaveis": 450.0, "aporte_real": 2800.0, "df_ops": pd.DataFrame()},
            category_context={"credito_total": 100.0},
            savings_rate=32.5,
            receita_base=6000.0,
        )
        assert captured
        assert "Folga do teto" in captured[0]
        assert "Creditos/estornos" in captured[0]
        assert 'class="mobile-only"' in captured[0]

    def test_tab_historico_importa_sazonalidade(self):
        assert "analisar_sazonalidade" in tab_historico.__dict__
