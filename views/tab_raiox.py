import calendar
import statistics
from datetime import date, timedelta
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.utils import mes_sort_key
from services.data_engine import (
    calcular_score_financeiro,
    detectar_anomalia,
    detectar_parcelamento,
    normalize_card_filter_list,
    processar_mes,
)
from views.styles import _detect_theme


def _format_currency(value: float) -> str:
    return f"R$ {value:,.2f}"


def _get_plotly_theme() -> tuple[str, str, str]:
    try:
        theme_base = st.get_option("theme.base")
    except Exception:
        theme_base = "dark"
    is_light = theme_base == "light"
    return (
        "plotly" if is_light else "plotly_dark",
        "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.08)",
        "rgba(0,0,0,0)",
    )


def _get_ui_palette() -> dict[str, str]:
    is_light = _detect_theme() == "light"
    if is_light:
        return {
            "positive_text": "#15803d",
            "negative_text": "#b91c1c",
            "neutral_text": "#0f172a",
            "warning_gradient": "linear-gradient(90deg, #d97706, #f59e0b)",
            "critical_gradient": "linear-gradient(90deg, #dc2626, #f97316)",
            "positive_gradient": "linear-gradient(90deg, #0f766e, #22c55e)",
            "radar_history_line": "#0f6cbd",
            "radar_history_fill": "rgba(15, 108, 189, 0.18)",
            "radar_current_line": "#b91c1c",
            "radar_current_fill": "rgba(185, 28, 28, 0.18)",
            "credit_row_style": "background-color: #dcfce726; color: #166534; font-weight: 600",
        }
    return {
        "positive_text": "#22c55e",
        "negative_text": "#ff5c5c",
        "neutral_text": "inherit",
        "warning_gradient": "linear-gradient(90deg, #f7971e, #ffd200)",
        "critical_gradient": "linear-gradient(90deg, #ff416c, #ff4b2b)",
        "positive_gradient": "linear-gradient(90deg, #00c9ff, #92fe9d)",
        "radar_history_line": "#00c9ff",
        "radar_history_fill": "rgba(0, 201, 255, 0.18)",
        "radar_current_line": "#ff4b2b",
        "radar_current_fill": "rgba(255, 75, 43, 0.28)",
        "credit_row_style": "background-color: #14532d26; color: #22c55e; font-weight: 600",
    }


def _parse_cycle_period(mes_label: str, dia_fechamento: int) -> dict:
    year, month = mes_sort_key(mes_label)
    if not year or not month:
        return {"is_active": False, "days_remaining": 0, "days_elapsed": 0, "cycle_days": 30}

    close_day = min(dia_fechamento, calendar.monthrange(year, month)[1])
    close_date = date(year, month, close_day)
    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year
    prev_close_day = min(dia_fechamento, calendar.monthrange(prev_year, prev_month)[1])
    start_date = date(prev_year, prev_month, prev_close_day) + timedelta(days=1)
    today = date.today()
    cycle_days = (close_date - start_date).days + 1
    is_active = start_date <= today <= close_date
    return {
        "is_active": is_active,
        "days_remaining": (close_date - today).days + 1 if is_active else 0,
        "days_elapsed": (today - start_date).days + 1 if is_active else cycle_days,
        "cycle_days": cycle_days,
    }


def _get_debit_ops(df_ops: pd.DataFrame) -> pd.DataFrame:
    if df_ops.empty or "Tipo" not in df_ops.columns:
        return df_ops.copy()
    return df_ops[df_ops["Tipo"] != "credito"].copy()


def _get_credit_ops(df_ops: pd.DataFrame) -> pd.DataFrame:
    if df_ops.empty or "Tipo" not in df_ops.columns:
        return pd.DataFrame(columns=df_ops.columns)
    return df_ops[df_ops["Tipo"] == "credito"].copy()


def _get_category_totals(df_ops: pd.DataFrame) -> pd.Series:
    debit_ops = _get_debit_ops(df_ops)
    if debit_ops.empty or "Categoria" not in debit_ops.columns:
        return pd.Series(dtype="float64")
    return debit_ops.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)


def _build_processed_history(
    months: list[str],
    mensal_data: dict,
    transacoes_data: dict,
    perfil_ativo: str,
    teto_gastos: float,
    receita_base: float,
    meta_aporte: float,
    cartoes_aceitos: list[str],
    cartoes_excluidos: list[str],
) -> dict[str, dict]:
    history = {}
    for mes in months:
        history[mes] = processar_mes(
            pd.DataFrame(mensal_data.get(mes, [])),
            pd.DataFrame(transacoes_data.get(mes, [])),
            perfil_ativo,
            teto_gastos,
            receita_base,
            meta_aporte,
            cartoes_aceitos,
            cartoes_excluidos,
        )
    return history


def _build_category_context(current: dict, previous_results: list[dict], budgets: dict[str, float]) -> dict:
    current_totals = _get_category_totals(current["df_ops"])
    history_by_cat: dict[str, list[float]] = {}
    for result in previous_results:
        for categoria, valor in _get_category_totals(result["df_ops"]).items():
            history_by_cat.setdefault(categoria, []).append(float(valor))

    anomalies = []
    for categoria, atual in current_totals.items():
        historico = history_by_cat.get(categoria, [])
        if len(historico) < 3:
            continue
        media = statistics.mean(historico)
        std = statistics.stdev(historico) if len(historico) > 1 else 0.0
        if detectar_anomalia(float(atual), media, std, z_threshold=1.8) and atual > media:
            pct = ((float(atual) / media) - 1) * 100 if media > 0 else 0.0
            anomalies.append({"categoria": categoria, "atual": float(atual), "media": media, "pct": pct})
    anomalies.sort(key=lambda item: item["atual"] - item["media"], reverse=True)

    over_budget = []
    for categoria, limite in budgets.items():
        atual = float(current_totals.get(categoria, 0.0))
        if limite > 0 and atual > float(limite):
            over_budget.append(
                {"categoria": categoria, "limite": float(limite), "atual": atual, "excesso": atual - float(limite)}
            )
    over_budget.sort(key=lambda item: item["excesso"], reverse=True)

    controls = []
    all_cats = set(current_totals.index).union(budgets.keys())
    for categoria, historico in history_by_cat.items():
        if len(historico) >= 3:
            all_cats.add(categoria)
    for categoria in all_cats:
        atual = float(current_totals.get(categoria, 0.0))
        historico = history_by_cat.get(categoria, [])
        media_hist = statistics.mean(historico) if len(historico) >= 3 else 0.0
        referencia = float(budgets.get(categoria, 0.0)) or media_hist
        if referencia > 0:
            controls.append(
                {
                    "categoria": categoria,
                    "atual": atual,
                    "referencia": referencia,
                    "fonte": "Orçamento" if categoria in budgets else "Média histórica",
                    "pct": (atual / referencia) * 100,
                }
            )
    controls.sort(key=lambda item: (item["pct"], item["atual"]), reverse=True)

    radar = []
    for categoria in sorted(set(current_totals.index).union(history_by_cat.keys())):
        historico = history_by_cat.get(categoria, [])
        if len(historico) >= 3:
            media = statistics.mean(historico)
            atual = float(current_totals.get(categoria, 0.0))
            if media > 0 or atual > 0:
                radar.append((categoria, atual, media))

    credit_ops = _get_credit_ops(current["df_ops"])
    credit_total = float(credit_ops["Valor"].sum()) if not credit_ops.empty and "Valor" in credit_ops.columns else 0.0
    return {
        "gasto_debito_por_categoria": current_totals,
        "credito_total": credit_total,
        "comprometido_total": current["total_comprometido"],
        "categorias_acima_do_limite": over_budget,
        "top_categorias_relevantes": current_totals.head(5),
        "anomalias_relevantes": anomalies,
        "controles_categoria": controls,
        "radar": radar,
    }


def _build_budget_snapshot(current: dict, category_context: dict, meta_aporte: float) -> dict:
    debit_totals = category_context["gasto_debito_por_categoria"]
    if hasattr(debit_totals, "empty") and not debit_totals.empty:
        debit_variable_total = float(debit_totals.sum())
    else:
        debit_variable_total = max(float(current["total_variaveis"]), 0.0)
    credit_total = float(category_context["credito_total"])

    rows = [
        {"label": "Total Fixos", "value": float(current["total_fixos"]), "tone": "default", "strong": True},
    ]
    if credit_total > 0:
        rows.extend(
            [
                {"label": "Debitos variaveis", "value": debit_variable_total, "tone": "default", "strong": False},
                {"label": "Creditos/estornos", "value": -credit_total, "tone": "positive", "strong": False},
                {"label": "Variaveis liquidas do ciclo", "value": float(current["total_variaveis"]), "tone": "default", "strong": False},
            ]
        )
    else:
        rows.append({"label": "Variaveis do ciclo", "value": float(current["total_variaveis"]), "tone": "default", "strong": False})

    rows.extend(
        [
            {"label": "Total Comprometido", "value": float(current["total_comprometido"]), "tone": "default", "strong": True},
            {"label": "Saldo restante do teto", "value": float(current["saldo_teto"]), "tone": "default", "strong": False},
            {"label": "Meta de aporte", "value": float(meta_aporte), "tone": "default", "strong": False},
            {
                "label": "Aporte projetado",
                "value": float(current["aporte_real"]),
                "tone": "positive" if not current["meta_ameacada"] else "negative",
                "strong": True,
            },
        ]
    )
    return {
        "rows": rows,
        "debit_variable_total": debit_variable_total,
        "credit_total": credit_total,
    }


def _build_category_ranking(category_context: dict) -> pd.DataFrame:
    totals = category_context["gasto_debito_por_categoria"]
    if totals.empty:
        return pd.DataFrame()

    total_debito = float(totals.sum()) or 1.0
    controls_map = {item["categoria"]: item for item in category_context["controles_categoria"]}
    over_budget = {item["categoria"]: item for item in category_context["categorias_acima_do_limite"]}
    anomaly_map = {item["categoria"]: item for item in category_context["anomalias_relevantes"]}
    rows = []
    for categoria, valor in totals.head(6).items():
        control = controls_map.get(categoria)
        referencia = control["referencia"] if control else 0.0
        if categoria in over_budget:
            leitura = "Acima do limite"
        elif categoria in anomaly_map:
            leitura = "Acima do padrao"
        else:
            leitura = "Maior peso do ciclo"
        rows.append(
            {
                "Categoria": categoria,
                "Gasto": _format_currency(float(valor)),
                "% dos debitos": f"{(float(valor) / total_debito) * 100:.1f}%",
                "Referencia": _format_currency(float(referencia)) if referencia > 0 else "-",
                "Leitura": leitura,
            }
        )
    return pd.DataFrame(rows)


def _classify_cycle_status(config_invalid: bool, result: dict, meta_aporte: float, pct_outros: float, ritmo_pct: float | None, category_context: dict) -> dict:
    meta_gap = meta_aporte - result["aporte_real"]
    if result["saldo_teto"] < 0 or result["saldo_variaveis"] < 0 or (meta_aporte > 0 and meta_gap > max(500.0, meta_aporte * 0.1)):
        return {"label": "Crítico", "pill": "status-critical"}
    if config_invalid or result["pct_teto"] >= 85 or (ritmo_pct is not None and ritmo_pct < 50) or category_context["categorias_acima_do_limite"] or category_context["anomalias_relevantes"] or pct_outros >= 15:
        return {"label": "Em atenção", "pill": "status-warning"}
    return {"label": "Controlado", "pill": "status-positive"}


def _build_cycle_summary(status: dict, result: dict, meta_aporte: float, ritmo_diario: float | None, days_remaining: int, category_context: dict, pct_outros: float, is_active: bool) -> str:
    if not is_active:
        if status["label"] == "Crítico":
            if result["saldo_teto"] < 0:
                return f"Este ciclo fechou acima do teto em {_format_currency(abs(result['saldo_teto']))}. Use esse excesso como ajuste de partida para o próximo fechamento."
            if result["saldo_variaveis"] < 0:
                return "O ciclo fechou com variáveis acima da margem planejada. O próximo fechamento precisa começar com um teto mais protegido."
            return f"O ciclo terminou {_format_currency(meta_aporte - result['aporte_real'])} abaixo da meta de aporte. Vale revisar onde a folga se perdeu."
        if status["label"] == "Em atenção":
            if category_context["categorias_acima_do_limite"]:
                top = category_context["categorias_acima_do_limite"][0]
                return f"{top['categoria']} foi a principal fonte de pressão, com {_format_currency(top['excesso'])} acima da referência do ciclo."
            if pct_outros > 0:
                return f"{pct_outros:.0f}% dos débitos ainda estão sem categoria útil. Isso reduz a precisão do diagnóstico."
            return "O fechamento ficou dentro do possível, mas com sinais de pressão que merecem ajuste fino no próximo ciclo."
    if status["label"] == "Crítico":
        if result["saldo_teto"] < 0:
            return f"Você já ultrapassou o teto em {_format_currency(abs(result['saldo_teto']))}. O foco agora é cortar saídas variáveis imediatamente."
        if result["saldo_variaveis"] < 0:
            return "O orçamento de variáveis virou negativo antes do fechamento. Congele gastos discricionários até recuperar folga."
        return f"O aporte projetado está {_format_currency(meta_aporte - result['aporte_real'])} abaixo da meta. Ajuste o ritmo do ciclo agora."
    if status["label"] == "Em atenção":
        if category_context["categorias_acima_do_limite"]:
            top = category_context["categorias_acima_do_limite"][0]
            return f"{top['categoria']} já passou do limite em {_format_currency(top['excesso'])}. Redirecione os próximos gastos."
        if ritmo_diario is not None and days_remaining > 0:
            return f"Você ainda cabe no teto, mas precisa manter um ritmo próximo de {_format_currency(ritmo_diario)}/dia pelos próximos {days_remaining} dias."
        if pct_outros > 0:
            return f"{pct_outros:.0f}% dos débitos ainda estão sem categoria útil. Isso reduz a precisão do diagnóstico."
        return "O ciclo segue controlável, mas já exige atenção nas próximas decisões."
    if ritmo_diario is not None and days_remaining > 0:
        return f"Seu orçamento segue respirando: há espaço para cerca de {_format_currency(ritmo_diario)}/dia até o fechamento sem comprometer o teto."
    return "O resultado final do ciclo ficou dentro dos parâmetros principais do planejamento."


def _build_interventions(config_invalid: bool, result: dict, meta_aporte: float, days_remaining: int, qtd_outros: int, category_context: dict, is_active: bool) -> list[dict]:
    if not is_active:
        cards = []
        if config_invalid:
            cards.append({"priority": 1, "tone": "warning", "title": "Configuração financeira incompleta", "what": "Receita base ou teto de gastos ainda não estão configurados de forma consistente.", "impact": "Parte do diagnóstico deixa de refletir o plano real do perfil.", "action": "Revise os parâmetros globais antes de usar este fechamento como base comparativa."})
        if result["saldo_teto"] < 0 or result["saldo_variaveis"] < 0:
            impact = f"O teto fechou acima do planejado em {_format_currency(abs(result['saldo_teto']))}." if result["saldo_teto"] < 0 else f"As variáveis fecharam negativas em {_format_currency(abs(result['saldo_variaveis']))}."
            cards.append({"priority": 2, "tone": "critical", "title": "O ciclo fechou em excesso", "what": "O comprometido total passou do limite ou o saldo disponível para variáveis acabou antes do fechamento.", "impact": impact, "action": "Use esse excesso para recalibrar o próximo ciclo antes de liberar gastos discricionários."})
        if meta_aporte > 0 and result["meta_ameacada"]:
            cards.append({"priority": 3, "tone": "warning", "title": "Meta de aporte não foi alcançada", "what": "O aporte final do ciclo ficou abaixo da meta definida.", "impact": f"Faltaram {_format_currency(meta_aporte - result['aporte_real'])} para bater a meta de {_format_currency(meta_aporte)}.", "action": "Defina onde esse valor será recuperado no próximo ciclo antes de reabrir margem para extras."})
        if category_context["categorias_acima_do_limite"]:
            top = category_context["categorias_acima_do_limite"][0]
            cards.append({"priority": 4, "tone": "warning", "title": f"{top['categoria']} foi a principal pressão", "what": "A categoria fechou acima da referência definida para o ciclo.", "impact": f"Gasto atual: {_format_currency(top['atual'])} para uma referência de {_format_currency(top['limite'])}.", "action": "Trate essa categoria como o primeiro ajuste da próxima rodada."})
        if category_context["anomalias_relevantes"]:
            top = category_context["anomalias_relevantes"][0]
            cards.append({"priority": 5, "tone": "info", "title": f"{top['categoria']} fechou fora do padrão", "what": "O gasto desta categoria terminou acima do comportamento histórico recente.", "impact": f"Valor atual: {_format_currency(top['atual'])}, cerca de {top['pct']:.0f}% acima da média de {_format_currency(top['media'])}.", "action": "Confirme se esse aumento foi pontual ou se precisa virar regra de planejamento."})
        if qtd_outros > 0:
            cards.append({"priority": 6, "tone": "info", "title": "Há lançamentos sem leitura útil", "what": "Parte dos débitos ainda está classificada como Outros.", "impact": f"{qtd_outros} lançamento(s) continuam fora das categorias analíticas do ciclo.", "action": "Reclassifique esses lançamentos antes de usar este fechamento como base histórica."})
        return sorted(cards, key=lambda item: item["priority"])
    cards = []
    if config_invalid:
        cards.append({"priority": 1, "tone": "warning", "title": "Configuração financeira incompleta", "what": "Receita base ou teto de gastos ainda não estão configurados de forma consistente.", "impact": "Parte do diagnóstico deixa de refletir o plano real do perfil.", "action": "Revise os parâmetros globais na aba Configurações antes de usar este raio-X como referência."})
    if result["saldo_teto"] < 0 or result["saldo_variaveis"] < 0:
        impact = f"O teto já foi ultrapassado em {_format_currency(abs(result['saldo_teto']))}." if result["saldo_teto"] < 0 else f"O orçamento de variáveis ficou negativo em {_format_currency(abs(result['saldo_variaveis']))}."
        cards.append({"priority": 2, "tone": "critical", "title": "O ciclo entrou na zona de excesso", "what": "O comprometido total já passou do limite ou o saldo disponível para variáveis acabou antes do fechamento.", "impact": impact, "action": "Suspenda gastos discricionários e preserve apenas despesas essenciais até recuperar margem."})
    if meta_aporte > 0 and result["meta_ameacada"]:
        cards.append({"priority": 3, "tone": "warning", "title": "Meta de aporte ameaçada", "what": "O aporte projetado do ciclo está abaixo da meta definida.", "impact": f"Faltam {_format_currency(meta_aporte - result['aporte_real'])} para bater a meta de {_format_currency(meta_aporte)}.", "action": "Reduza categorias discricionárias primeiro para proteger o valor do aporte."})
    if category_context["categorias_acima_do_limite"]:
        top = category_context["categorias_acima_do_limite"][0]
        cards.append({"priority": 4, "tone": "warning", "title": f"{top['categoria']} passou do limite", "what": "A categoria já consumiu mais do que o teto definido para este ciclo.", "impact": f"Gasto atual: {_format_currency(top['atual'])} para um limite de {_format_currency(top['limite'])}.", "action": "Congele novas saídas nesta categoria e compense o excesso nas próximas decisões."})
    if category_context["anomalias_relevantes"]:
        top = category_context["anomalias_relevantes"][0]
        cards.append({"priority": 5, "tone": "info", "title": f"{top['categoria']} fugiu do padrão", "what": "O gasto atual desta categoria está acima do comportamento histórico recente.", "impact": f"Valor atual: {_format_currency(top['atual'])}, cerca de {top['pct']:.0f}% acima da média de {_format_currency(top['media'])}.", "action": "Revise os lançamentos desta categoria e confirme se o aumento foi intencional."})
    if qtd_outros > 0:
        cards.append({"priority": 6, "tone": "info", "title": "Há lançamentos sem leitura útil", "what": "Parte dos débitos ainda está classificada como Outros.", "impact": f"{qtd_outros} lançamento(s) continuam fora das categorias analíticas do ciclo.", "action": "Classifique esses lançamentos para melhorar a precisão dos insights e dos limites."})
    if is_active and days_remaining <= 5 and not result["df_config"].empty and "Tipo" in result["df_config"].columns:
        df_cartao = result["df_config"][result["df_config"]["Tipo"].astype(str).str.strip().str.lower() == "cartao"]
        if not df_cartao.empty and "Status_Conciliacao" in df_cartao.columns:
            pendentes = df_cartao[df_cartao["Status_Conciliacao"] == "⏳ Pendente"]
            if not pendentes.empty:
                cards.append({"priority": 7, "tone": "info", "title": "Fixos de cartão ainda pendentes", "what": "Nem todos os gastos fixos de cartão apareceram na conciliação do ciclo atual.", "impact": f"{len(pendentes)} gasto(s) fixos seguem pendentes a {days_remaining} dia(s) do fechamento.", "action": "Confira a fatura e valide se a ausência é temporária ou se exige ajuste cadastral."})
    return sorted(cards, key=lambda item: item["priority"])


def _render_intervention(card: dict, action_label: str) -> None:
    card_html = f"""
    <div class="intervention-card {card["tone"]}">
        <div class="intervention-title">{card["title"]}</div>
        <div class="intervention-line"><strong>O que aconteceu:</strong> {card["what"]}</div>
        <div class="intervention-line"><strong>Impacto:</strong> {card["impact"]}</div>
        <div class="intervention-line"><strong>{action_label}:</strong> {card["action"]}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _prepare_launch_table(df_ops: pd.DataFrame, reference_ops: pd.DataFrame | None = None) -> pd.DataFrame:
    disp = df_ops.copy()
    debit_ops = _get_debit_ops(reference_ops if reference_ops is not None else df_ops)
    stats = debit_ops.groupby("Categoria")["Valor"].agg(["mean", "std"]).to_dict(orient="index") if not debit_ops.empty and "Categoria" in debit_ops.columns else {}
    reasons, weights = [], []
    for _, row in disp.iterrows():
        parts, weight = [], float(row.get("Valor", 0) or 0)
        tipo = row.get("Tipo", "debito")
        categoria = row.get("Categoria", "")
        if tipo == "credito":
            parts.append("Crédito/estorno")
            weight += 60
        parcela = detectar_parcelamento(str(row.get("Descricao", "")))
        if parcela:
            parts.append(f"Parcelado {parcela[0]}/{parcela[1]}")
            weight += 80
        if categoria in stats and tipo != "credito":
            media = stats[categoria].get("mean", 0)
            std = stats[categoria].get("std", 0)
            if std and detectar_anomalia(float(row.get("Valor", 0) or 0), media, std, z_threshold=1.8):
                parts.append("Valor fora do padrão da categoria")
                weight += 100
        reasons.append(" | ".join(parts) or "—")
        weights.append(weight)
    disp["Motivo do destaque"] = reasons
    disp["_peso"] = weights
    return disp


def _safe_text(value: object, fallback: str = "—") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _render_category_ranking(category_ranking: pd.DataFrame) -> None:
    if category_ranking.empty:
        return

    mobile_limit = 4
    desktop_rows = []
    mobile_cards = []
    for idx, (_, row) in enumerate(category_ranking.iterrows()):
        categoria = escape(_safe_text(row.get("Categoria")))
        gasto = escape(_safe_text(row.get("Gasto")))
        share = escape(_safe_text(row.get("% dos debitos")))
        referencia = escape(_safe_text(row.get("Referencia")))
        leitura = escape(_safe_text(row.get("Leitura")))
        desktop_rows.append(
            "<tr>"
            f"<td class=\"strong\">{categoria}</td>"
            f"<td class=\"numeric strong\">{gasto}</td>"
            f"<td class=\"numeric\">{share}</td>"
            f"<td class=\"numeric muted\">{referencia}</td>"
            f"<td>{leitura}</td>"
            "</tr>"
        )
        if idx >= mobile_limit:
            continue
        mobile_cards.append(
            "<div class=\"mobile-stack-card\">"
            "<div class=\"mobile-stack-head\">"
            f"<div class=\"mobile-stack-title\">{categoria}</div>"
            f"<div class=\"mobile-stack-value\">{gasto}</div>"
            "</div>"
            "<div class=\"mobile-stack-grid\">"
            f"<div class=\"mobile-stack-row\"><span class=\"mobile-stack-label\">Peso</span><span class=\"mobile-stack-copy\">{share}</span></div>"
            f"<div class=\"mobile-stack-row\"><span class=\"mobile-stack-label\">Referência</span><span class=\"mobile-stack-copy\">{referencia}</span></div>"
            "</div>"
            f"<div class=\"mobile-stack-note\">{leitura}</div>"
            "</div>"
        )

    desktop_html = (
        "<div class=\"desktop-only\">"
        "<table class=\"responsive-data-table\">"
        "<thead><tr><th>Categoria</th><th>Gasto</th><th>% dos débitos</th><th>Referência</th><th>Leitura</th></tr></thead>"
        f"<tbody>{''.join(desktop_rows)}</tbody>"
        "</table>"
        "</div>"
    )
    footer = ""
    if len(category_ranking) > mobile_limit:
        footer = f'<div class="mobile-stack-footer">Mostrando as {mobile_limit} categorias mais relevantes. Abra os detalhes para ver o restante.</div>'
    mobile_html = f"<div class=\"mobile-only\"><div class=\"mobile-stack\">{''.join(mobile_cards)}</div>{footer}</div>"
    st.markdown(desktop_html + mobile_html, unsafe_allow_html=True)


def _render_cycle_kpis(
    current: dict,
    meta_aporte: float,
    previous: dict | None,
    category_context: dict,
    savings_rate: float,
    receita_base: float,
) -> None:
    delta_variaveis = current["total_variaveis"] - previous["total_variaveis"] if previous else None
    previous_credit_total = (
        float(_get_credit_ops(previous["df_ops"])["Valor"].sum())
        if previous is not None and not _get_credit_ops(previous["df_ops"]).empty
        else 0.0
    )
    delta_creditos = category_context["credito_total"] - previous_credit_total if previous else None
    delta_sr = savings_rate - ((previous["aporte_real"] / receita_base) * 100) if previous and receita_base > 0 else None
    meta_delta = current["aporte_real"] - meta_aporte if meta_aporte > 0 else current["aporte_real"]

    def _signed_currency(value: float | None) -> str:
        if value is None:
            return "Sem comparativo recente."
        direction = "acima" if value > 0 else "abaixo" if value < 0 else "em linha"
        return f"{_format_currency(abs(value))} {direction} do ciclo anterior."

    meta_copy = "Meta de aporte nao definida."
    if meta_aporte > 0:
        meta_copy = f"{_format_currency(abs(meta_delta))} {'acima' if meta_delta >= 0 else 'abaixo'} da meta."

    desktop_cards = [
        ("Variaveis liquidas", _format_currency(current["total_variaveis"]), _signed_currency(delta_variaveis)),
        ("Distancia da meta", _format_currency(abs(meta_delta)) if meta_aporte > 0 else _format_currency(current["aporte_real"]), meta_copy),
        ("Creditos/estornos", _format_currency(category_context["credito_total"]), _signed_currency(delta_creditos)),
        ("Savings rate", f"{savings_rate:.1f}%", f"{delta_sr:+.1f}pp vs ciclo anterior." if delta_sr is not None else "Sem comparativo recente."),
    ]
    mobile_cards = [
        ("Folga do teto", _format_currency(current["saldo_teto"]), f'{current["pct_teto"]:.1f}% do teto consumido.', "positive" if current["saldo_teto"] >= 0 else "negative"),
        ("Distancia da meta", _format_currency(abs(meta_delta)) if meta_aporte > 0 else _format_currency(current["aporte_real"]), "Meta batida ou acima." if meta_aporte > 0 and meta_delta >= 0 else "Meta abaixo do planejado." if meta_aporte > 0 else "Sem meta definida.", "positive" if meta_aporte <= 0 or meta_delta >= 0 else "negative"),
        ("Variaveis liquidas", _format_currency(current["total_variaveis"]), "Ja considera creditos e estornos do ciclo.", "neutral"),
    ]

    desktop_html = '<div class="desktop-only"><div class="kpi-grid">' + "".join(
        f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><span class="kpi-sub neutral">{copy}</span></div>'
        for label, value, copy in desktop_cards
    ) + "</div></div>"
    mobile_html = '<div class="mobile-only"><div class="kpi-grid mobile-kpi-grid">' + "".join(
        f'<div class="kpi-card {tone}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><span class="kpi-sub neutral">{copy}</span></div>'
        for label, value, copy, tone in mobile_cards
    ) + f'</div><div class="kpi-inline-summary"><span>Creditos/estornos: <strong>{_format_currency(category_context["credito_total"])}</strong></span><span>Savings rate: <strong>{savings_rate:.1f}%</strong></span></div></div>'
    st.markdown(desktop_html + mobile_html, unsafe_allow_html=True)


def _render_launches(disp: pd.DataFrame) -> None:
    if disp.empty:
        st.info("Nenhum lançamento atende aos filtros atuais.")
        return

    mobile_limit = 8
    desktop_rows = []
    mobile_cards = []
    empty_marker = _safe_text(None)
    for idx, (_, row) in enumerate(disp.iterrows()):
        descricao = escape(_safe_text(row.get("Descricao")))
        categoria = escape(_safe_text(row.get("Categoria")))
        motivo = escape(_safe_text(row.get("Motivo do destaque")))
        valor = escape(_safe_text(row.get("Valor")))
        cartao = escape(_safe_text(row.get("Cartao")))
        tipo = escape(_safe_text(row.get("Tipo")))
        is_credit = "credito" in tipo.lower()
        reason_html = "" if motivo == empty_marker else f"<div class=\"mobile-stack-note\"><strong>Motivo:</strong> {motivo}</div>"
        desktop_rows.append(
            f"<tr class=\"{'credit-row' if is_credit else ''}\">"
            f"<td class=\"strong\">{descricao}</td>"
            f"<td>{categoria}</td>"
            f"<td class=\"muted\">{motivo}</td>"
            f"<td class=\"numeric strong\">{valor}</td>"
            f"<td>{cartao}</td>"
            f"<td>{tipo}</td>"
            "</tr>"
        )
        if idx >= mobile_limit:
            continue
        tags = [categoria]
        if cartao != empty_marker:
            tags.append(cartao)
        if is_credit:
            tags.append(tipo)
        mobile_cards.append(
            "<div class=\"mobile-stack-card\">"
            "<div class=\"mobile-stack-head\">"
            f"<div class=\"mobile-stack-title\">{descricao}</div>"
            f"<div class=\"mobile-stack-value{' positive' if is_credit else ''}\">{valor}</div>"
            "</div>"
            "<div class=\"mobile-stack-tags\">"
            + "".join(f'<span class="mobile-stack-tag">{tag}</span>' for tag in tags)
            + "</div>"
            + f"{reason_html}"
            + "</div>"
        )

    desktop_html = (
        "<div class=\"desktop-only\">"
        "<table class=\"responsive-data-table\">"
        "<thead><tr><th>Descrição</th><th>Categoria</th><th>Motivo do destaque</th><th>Valor</th><th>Cartão</th><th>Tipo</th></tr></thead>"
        f"<tbody>{''.join(desktop_rows)}</tbody>"
        "</table>"
        "</div>"
    )
    footer = ""
    if len(disp) > mobile_limit:
        footer = f'<div class="mobile-stack-footer">Mostrando os {mobile_limit} lancamentos mais relevantes. Use busca ou filtro para refinar a analise.</div>'
    mobile_html = f"<div class=\"mobile-only\"><div class=\"mobile-stack\">{''.join(mobile_cards)}</div>{footer}</div>"
    st.markdown(desktop_html + mobile_html, unsafe_allow_html=True)


def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    category_budgets = st.session_state.get("category_budgets_data", {}) or {}
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    plotly_template, _, plotly_bg = _get_plotly_theme()
    ui_palette = _get_ui_palette()

    months = sorted(list(transacoes_data.keys()), key=mes_sort_key)
    if not months:
        st.info("Nenhum mês cadastrado. Vá na aba ⚙️ Configurações para criar um mês.")
        return

    receita_base = float(cfg.get("Receita_Base", 0) or 0)
    meta_aporte = float(cfg.get("Meta_Aporte", 0) or 0)
    teto_gastos = float(cfg.get("Teto_Gastos", 0) or 0)
    dia_fechamento = int(cfg.get("Dia_Fechamento", 13))
    cartoes_aceitos = normalize_card_filter_list(cfg.get("Cartoes_Aceitos"))
    cartoes_excluidos = normalize_card_filter_list(cfg.get("Cartoes_Excluidos"))

    mes_sel = st.selectbox("Selecione o Ciclo de Fatura", months, index=len(months) - 1)
    history = _build_processed_history(months, mensal_data, transacoes_data, perfil_ativo, teto_gastos, receita_base, meta_aporte, cartoes_aceitos, cartoes_excluidos)
    current = history[mes_sel]
    idx = months.index(mes_sel)
    previous_results = [history[mes] for mes in months[:idx]]
    previous = history[months[idx - 1]] if idx > 0 else None

    cycle = _parse_cycle_period(mes_sel, dia_fechamento)
    ritmo_diario = current["saldo_variaveis"] / cycle["days_remaining"] if cycle["is_active"] and cycle["days_remaining"] > 0 else None
    ritmo_base = current["limite_base_var"] / cycle["cycle_days"] if cycle["is_active"] and cycle["cycle_days"] > 0 and current["limite_base_var"] > 0 else None
    ritmo_pct = (ritmo_diario / ritmo_base) * 100 if ritmo_diario is not None and ritmo_base not in (None, 0) else None
    debit_ops = _get_debit_ops(current["df_ops"])
    qtd_outros = len(debit_ops[debit_ops["Categoria"] == "Outros"]) if not debit_ops.empty and "Categoria" in debit_ops.columns else 0
    pct_outros = (qtd_outros / len(debit_ops) * 100) if len(debit_ops) > 0 else 0.0
    savings_rate = (current["aporte_real"] / receita_base * 100) if receita_base > 0 else 0.0
    sr_history = [((history[mes]["aporte_real"] / receita_base) * 100) for mes in months[max(0, len(months) - 6):] if receita_base > 0]
    std_sr = statistics.stdev(sr_history) if len(sr_history) > 1 else 0.0
    score_data = calcular_score_financeiro(savings_rate, current["pct_teto"], not current["meta_ameacada"], std_sr, pct_outros)
    category_context = _build_category_context(current, previous_results, category_budgets)
    budget_snapshot = _build_budget_snapshot(current, category_context, meta_aporte)
    category_ranking = _build_category_ranking(category_context)
    status = _classify_cycle_status(receita_base <= 0 or teto_gastos <= 0, current, meta_aporte, pct_outros, ritmo_pct, category_context)
    summary = _build_cycle_summary(status, current, meta_aporte, ritmo_diario, cycle["days_remaining"], category_context, pct_outros, cycle["is_active"])
    interventions = _build_interventions(receita_base <= 0 or teto_gastos <= 0, current, meta_aporte, cycle["days_remaining"], qtd_outros, category_context, cycle["is_active"])

    state_label = "Ritmo disponível por dia" if cycle["is_active"] else "Margem final vs teto"
    state_value = _format_currency(ritmo_diario) if ritmo_diario is not None else _format_currency(current["saldo_teto"])
    if cycle["is_active"]:
        state_sub = f"{cycle['days_remaining']} dia(s) até o fechamento"
    else:
        state_sub = "Positivo indica folga; negativo indica excesso."

    hero_html = f"""
    <div class="cycle-state-card">
        <div class="state-topline">
            <span class="status-pill {status["pill"]}">{status["label"]}</span>
            <span class="state-cycle">{mes_sel}</span>
        </div>
        <div class="state-grid">
            <div class="state-item">
                <div class="state-label">Comprometido</div>
                <div class="state-value">{_format_currency(current["total_comprometido"])}</div>
                <div class="state-sub">{current["pct_teto"]:.1f}% do teto de {_format_currency(teto_gastos)}</div>
            </div>
            <div class="state-item">
                <div class="state-label">Aporte projetado</div>
                <div class="state-value">{_format_currency(current["aporte_real"])}</div>
                <div class="state-sub">Meta: {_format_currency(meta_aporte)}</div>
            </div>
            <div class="state-item">
                <div class="state-label">{state_label}</div>
                <div class="state-value">{state_value}</div>
                <div class="state-sub">{state_sub}</div>
            </div>
        </div>
        <div class="state-summary">{summary}</div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    if interventions:
        title = "Intervenções Prioritárias" if cycle["is_active"] else "Leituras Prioritárias do Ciclo"
        action_label = "Ação agora" if cycle["is_active"] else "Ajuste sugerido"
        st.markdown(f'<p class="section-header">{title}</p>', unsafe_allow_html=True)
        for card in interventions[:4]:
            _render_intervention(card, action_label)
        if len(interventions) > 4:
            with st.expander("Outros sinais do ciclo"):
                for card in interventions[4:]:
                    _render_intervention(card, action_label)

    st.markdown('<p class="section-header">KPIs do Ciclo</p>', unsafe_allow_html=True)
    _render_cycle_kpis(current, meta_aporte, previous, category_context, savings_rate, receita_base)

    st.markdown('<p class="section-header">Resumo do Orçamento</p>', unsafe_allow_html=True)
    summary_html = '<table class="summary-table"><tbody>'
    for row in budget_snapshot["rows"]:
        color = (
            ui_palette["positive_text"]
            if row["tone"] == "positive"
            else ui_palette["negative_text"]
            if row["tone"] == "negative"
            else ui_palette["neutral_text"]
        )
        value_markup = _format_currency(row["value"])
        if row["strong"]:
            summary_html += f'<tr><td><strong>{row["label"]}</strong></td><td style="text-align:right; color:{color};"><strong>{value_markup}</strong></td></tr>'
        else:
            summary_html += f'<tr><td>{row["label"]}</td><td style="text-align:right; color:{color};">{value_markup}</td></tr>'
    summary_html += '</tbody></table>'
    st.markdown(summary_html, unsafe_allow_html=True)

    tipo_icons = {"Nao_Cartao": "🏠 Essenciais", "Cartao": "💳 Cartão", "Extra": "⭐ Extras"}
    if not current["df_config"].empty and "Tipo" in current["df_config"].columns:
        tipos_col = current["df_config"]["Tipo"].astype(str).str.strip()
        df_cartao = current["df_config"][tipos_col == "Cartao"].copy()
        if not df_cartao.empty and "Status_Conciliacao" in df_cartao.columns:
            confirmados = df_cartao[df_cartao["Status_Conciliacao"] == "✅ Confirmado"]
            pendentes = len(df_cartao) - len(confirmados)
            st.caption(f"Conciliação dos fixos de cartão: {len(confirmados)}/{len(df_cartao)} confirmados, {pendentes} pendentes.")
        for tipo in tipos_col.unique():
            df_tipo = current["df_config"][tipos_col == tipo].copy()
            with st.expander(f'{tipo_icons.get(tipo, tipo)} — **{_format_currency(float(df_tipo["Valor"].sum()))}**'):
                df_show = df_tipo[["Descricao_Fatura", "Valor", "Status_Conciliacao"]].rename(columns={"Descricao_Fatura": "Descrição", "Valor": "Valor", "Status_Conciliacao": "Status"})
                st.dataframe(df_show.style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True, hide_index=True)

    if not category_context["top_categorias_relevantes"].empty:
        st.markdown('<p class="section-header">Alvos de Ajuste por Categoria</p>', unsafe_allow_html=True)
        if not category_ranking.empty:
            _render_category_ranking(category_ranking)
        chart_data = category_context["top_categorias_relevantes"].reset_index()
        chart_data.columns = ["Categoria", "Valor"]
        with st.expander("Abrir visualização gráfica das categorias", expanded=False):
            tab_donut, tab_tree = st.tabs(["Visão macro", "Detalhamento"])
            with tab_donut:
                fig_donut = px.pie(chart_data, names="Categoria", values="Valor", hole=0.58, color_discrete_sequence=px.colors.qualitative.Safe)
                fig_donut.update_traces(textinfo="percent+label", texttemplate="<b>%{label}</b><br>%{percent:.1%}", hovertemplate="<b>%{label}</b><br>Gasto: R$ %{value:,.2f}<br>%{percent:.1%} do total<extra></extra>", textposition="outside")
                fig_donut.update_layout(template=plotly_template, paper_bgcolor=plotly_bg, plot_bgcolor=plotly_bg, margin=dict(t=20, b=20, l=10, r=10), height=430, showlegend=False)
                st.plotly_chart(fig_donut, use_container_width=True)
            with tab_tree:
                detail_ops = _get_debit_ops(current["df_ops"]).copy()
                if not detail_ops.empty and {"Categoria", "Descricao", "Valor"}.issubset(detail_ops.columns):
                    detail_ops["Descricao"] = detail_ops["Descricao"].fillna("Desconhecido")
                    fig_tree = px.treemap(detail_ops, path=[px.Constant("Débitos"), "Categoria", "Descricao"], values="Valor", color="Categoria", color_discrete_sequence=px.colors.qualitative.Safe)
                    fig_tree.update_traces(textinfo="label+value+percent parent", texttemplate="%{label}<br>R$ %{value:,.2f}<br>%{percentParent:.1%}", hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percentParent:.1%} da categoria<extra></extra>")
                    fig_tree.update_layout(template=plotly_template, paper_bgcolor=plotly_bg, plot_bgcolor=plotly_bg, margin=dict(t=20, b=20, l=10, r=10), height=500)
                    st.plotly_chart(fig_tree, use_container_width=True)
                else:
                    st.info("Sem detalhe suficiente para montar a visão expandida deste ciclo.")

    if category_context["controles_categoria"]:
        with st.expander("Ver referencias e limites por categoria", expanded=False):
            for item in category_context["controles_categoria"]:
                pct_visual = min(item["pct"], 100)
                color = (
                    ui_palette["critical_gradient"]
                    if item["pct"] >= 100
                    else ui_palette["warning_gradient"]
                    if item["pct"] >= 80
                    else ui_palette["positive_gradient"]
                )
                icon = "ALTO" if item["pct"] >= 100 else "ATEN" if item["pct"] >= 80 else "OK"
                st.markdown(f'<div class="cat-gauge-label"><span>{icon} <strong>{item["categoria"]}</strong> <small style="opacity:.55">({item["fonte"]})</small></span><span>{_format_currency(item["atual"])} / {_format_currency(item["referencia"])} ({item["pct"]:.1f}%)</span></div><div class="progress-outer" style="height:20px; margin-bottom:1rem;"><div class="progress-inner" style="width:{pct_visual:.1f}%; background:{color}; font-size:.75rem; padding-right:8px;">{item["pct"]:.0f}%</div></div>', unsafe_allow_html=True)

    st.markdown('<p class="section-header">Score Financeiro</p>', unsafe_allow_html=True)
    score_note = "Indicador composto; use como apoio, não como diagnóstico principal."
    if status["label"] == "Crítico":
        score_note = "Mesmo com eficiência relativa em alguns pilares, o diagnóstico do ciclo continua crítico e tem prioridade."
    elif status["label"] == "Em atenção":
        score_note = "O score ajuda a contextualizar a disciplina do ciclo, mas não substitui os sinais de atenção listados acima."
    st.markdown(f'<div class="score-panel"><div class="score-topline"><span class="score-chip">{score_data["emoji"]} Score {score_data["score"]}/100</span><span class="score-copy">{score_data["label"]}</span></div><div class="score-note">{score_note}</div></div>', unsafe_allow_html=True)
    with st.expander("Detalhes metodológicos do score", expanded=False):
        for pillar, points in score_data["pilares"].items():
            maximum = {"Savings Rate": 30, "Aderência ao Teto": 25, "Meta de Aporte": 20, "Consistência": 15, "Organização": 10}.get(pillar, 10)
            pct = (points / maximum) * 100 if maximum else 0
            color = (
                ui_palette["positive_gradient"]
                if pct >= 70
                else ui_palette["warning_gradient"]
                if pct >= 50
                else ui_palette["critical_gradient"]
            )
            st.markdown(f'<div class="cat-gauge-label"><span>{pillar}</span><span>{points}/{maximum}</span></div><div class="progress-outer" style="height:16px; margin-bottom:.75rem;"><div class="progress-inner" style="width:{pct:.0f}%; background:{color}; font-size:.7rem;"></div></div>', unsafe_allow_html=True)

    if len(category_context["radar"]) >= 3:
        with st.expander("Abrir comparação histórica por categoria", expanded=False):
            categories = [item[0] for item in category_context["radar"]]
            current_values = [item[1] for item in category_context["radar"]]
            history_values = [item[2] for item in category_context["radar"]]
            max_value = max(max(current_values, default=0), max(history_values, default=0), 1)
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=history_values + [history_values[0]], theta=categories + [categories[0]], fill="toself", name="Média histórica", line_color=ui_palette["radar_history_line"], fillcolor=ui_palette["radar_history_fill"]))
            fig_radar.add_trace(go.Scatterpolar(r=current_values + [current_values[0]], theta=categories + [categories[0]], fill="toself", name=f"Atual ({mes_sel})", line_color=ui_palette["radar_current_line"], fillcolor=ui_palette["radar_current_fill"]))
            fig_radar.update_layout(template=plotly_template, paper_bgcolor=plotly_bg, plot_bgcolor=plotly_bg, polar=dict(radialaxis=dict(visible=True, range=[0, max_value * 1.15], showticklabels=False)), showlegend=True, height=420, margin=dict(t=30, b=30, l=30, r=30))
            st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown(f'<p class="section-header">Lançamentos — {mes_sel}</p>', unsafe_allow_html=True)
    if current["df_ops"].empty:
        st.info("Nenhum lançamento após aplicação dos filtros.")
        return
    col_busca, col_filtro = st.columns(2)
    with col_busca:
        busca = st.text_input("Buscar lançamento", key="busca_lancamentos", placeholder="Ex: UBER, COBASI...")
    with col_filtro:
        opcoes = sorted(current["df_ops"]["Categoria"].dropna().unique().tolist()) if "Categoria" in current["df_ops"].columns else []
        filtro_cat = st.multiselect("Filtrar por categoria", options=opcoes, key="filtro_cat_lanc")
    disp = _prepare_launch_table(current["df_ops"], reference_ops=current["df_ops"])
    if busca and busca.strip():
        disp = disp[disp["Descricao"].str.contains(busca.strip(), case=False, na=False)]
    if filtro_cat and "Categoria" in disp.columns:
        disp = disp[disp["Categoria"].isin(filtro_cat)]
    if disp.empty:
        st.info("Nenhum lançamento atende aos filtros atuais.")
        return
    launch_view = disp.sort_values("_peso", ascending=False)
    empty_marker = _safe_text(None)
    reason_col = ["Motivo do destaque"] if "Motivo do destaque" in launch_view.columns and launch_view["Motivo do destaque"].map(_safe_text).ne(empty_marker).any() else []
    display_cols = [c for c in ["Descricao", "Categoria", *reason_col, "Valor", "Cartao", "Tipo"] if c in launch_view.columns]
    launch_view = launch_view[display_cols].copy()
    launch_view["Valor"] = launch_view["Valor"].map(lambda value: _format_currency(float(value)) if isinstance(value, (int, float)) else value)
    if "Tipo" in launch_view.columns:
        launch_view["Tipo"] = launch_view["Tipo"].map(lambda item: "Credito" if item == "credito" else "Debito")
    _render_launches(launch_view)
