import calendar
import statistics
from datetime import date, timedelta

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


def _classify_cycle_status(config_invalid: bool, result: dict, meta_aporte: float, pct_outros: float, ritmo_pct: float | None, category_context: dict) -> dict:
    meta_gap = meta_aporte - result["aporte_real"]
    if result["saldo_teto"] < 0 or result["saldo_variaveis"] < 0 or (meta_aporte > 0 and meta_gap > max(500.0, meta_aporte * 0.1)):
        return {"label": "Crítico", "pill": "status-critical"}
    if config_invalid or result["pct_teto"] >= 85 or (ritmo_pct is not None and ritmo_pct < 50) or category_context["categorias_acima_do_limite"] or category_context["anomalias_relevantes"] or pct_outros >= 15:
        return {"label": "Em atenção", "pill": "status-warning"}
    return {"label": "Controlado", "pill": "status-positive"}


def _build_cycle_summary(status: dict, result: dict, meta_aporte: float, ritmo_diario: float | None, days_remaining: int, category_context: dict, pct_outros: float) -> str:
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


def _build_interventions(config_invalid: bool, result: dict, meta_aporte: float, days_remaining: int, qtd_outros: int, category_context: dict) -> list[dict]:
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
    if days_remaining <= 5 and not result["df_config"].empty and "Tipo" in result["df_config"].columns:
        df_cartao = result["df_config"][result["df_config"]["Tipo"].astype(str).str.strip().str.lower() == "cartao"]
        if not df_cartao.empty and "Status_Conciliacao" in df_cartao.columns:
            pendentes = df_cartao[df_cartao["Status_Conciliacao"] == "⏳ Pendente"]
            if not pendentes.empty:
                cards.append({"priority": 7, "tone": "info", "title": "Fixos de cartão ainda pendentes", "what": "Nem todos os gastos fixos de cartão apareceram na conciliação do ciclo atual.", "impact": f"{len(pendentes)} gasto(s) fixos seguem pendentes a {days_remaining} dia(s) do fechamento.", "action": "Confira a fatura e valide se a ausência é temporária ou se exige ajuste cadastral."})
    return sorted(cards, key=lambda item: item["priority"])


def _render_intervention(card: dict) -> None:
    card_html = f"""
    <div class="intervention-card {card["tone"]}">
        <div class="intervention-title">{card["title"]}</div>
        <div class="intervention-line"><strong>O que aconteceu:</strong> {card["what"]}</div>
        <div class="intervention-line"><strong>Impacto:</strong> {card["impact"]}</div>
        <div class="intervention-line"><strong>Ação agora:</strong> {card["action"]}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _prepare_launch_table(df_ops: pd.DataFrame) -> pd.DataFrame:
    disp = df_ops.copy()
    debit_ops = _get_debit_ops(df_ops)
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


def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    category_budgets = st.session_state.get("category_budgets_data", {}) or {}
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    plotly_template, _, plotly_bg = _get_plotly_theme()

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
    status = _classify_cycle_status(receita_base <= 0 or teto_gastos <= 0, current, meta_aporte, pct_outros, ritmo_pct, category_context)
    summary = _build_cycle_summary(status, current, meta_aporte, ritmo_diario, cycle["days_remaining"], category_context, pct_outros)
    interventions = _build_interventions(receita_base <= 0 or teto_gastos <= 0, current, meta_aporte, cycle["days_remaining"], qtd_outros, category_context)

    state_label = "Ritmo disponível por dia" if cycle["is_active"] else "Resultado final do ciclo"
    state_value = _format_currency(ritmo_diario) if ritmo_diario is not None else _format_currency(current["saldo_teto"])
    if cycle["is_active"]:
        state_sub = f"{cycle['days_remaining']} dia(s) até o fechamento"
    else:
        state_sub = f"Saldo final vs teto: {_format_currency(current['saldo_teto'])}"

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
        st.markdown('<p class="section-header">Intervenções Prioritárias</p>', unsafe_allow_html=True)
        for card in interventions[:4]:
            _render_intervention(card)
        if len(interventions) > 4:
            with st.expander("Outros sinais do ciclo"):
                for card in interventions[4:]:
                    _render_intervention(card)

    st.markdown('<p class="section-header">KPIs do Ciclo</p>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    delta_variaveis = current["total_variaveis"] - previous["total_variaveis"] if previous else None
    delta_saldo = current["saldo_teto"] - previous["saldo_teto"] if previous else None
    delta_sr = savings_rate - ((previous["aporte_real"] / receita_base) * 100) if previous and receita_base > 0 else None
    meta_delta = current["aporte_real"] - meta_aporte if meta_aporte > 0 else current["aporte_real"]
    c1.metric("Total Variáveis", _format_currency(current["total_variaveis"]), delta=f"R$ {delta_variaveis:+,.0f} vs anterior" if delta_variaveis is not None else None, delta_color="inverse" if delta_variaveis and delta_variaveis > 0 else "normal")
    c2.metric("Saldo do Teto", _format_currency(current["saldo_teto"]), delta=f"R$ {delta_saldo:+,.0f} vs anterior" if delta_saldo is not None else None)
    c3.metric("Aporte Projetado", _format_currency(current["aporte_real"]), delta=f"R$ {meta_delta:+,.0f} vs meta" if meta_aporte > 0 else "Sem meta definida", delta_color="normal" if meta_delta >= 0 else "inverse")
    c4.metric("Savings Rate", f"{savings_rate:.1f}%", delta=f"{delta_sr:+.1f}pp vs anterior" if delta_sr is not None else None, delta_color="normal" if savings_rate >= 20 else "inverse")

    st.markdown('<p class="section-header">Resumo do Orçamento</p>', unsafe_allow_html=True)
    aporte_color = "#00e676" if not current["meta_ameacada"] else "#ff1744"
    summary_html = '<table class="summary-table"><tbody>'
    summary_html += f'<tr><td><strong>Total Fixos</strong></td><td style="text-align:right"><strong>{_format_currency(current["total_fixos"])}</strong></td></tr>'
    summary_html += f'<tr><td>Variáveis do ciclo</td><td style="text-align:right">{_format_currency(current["total_variaveis"])}</td></tr>'
    if category_context["credito_total"] > 0:
        summary_html += f'<tr><td style="color:#22c55e;">Créditos/estornos</td><td style="text-align:right; color:#22c55e;">− {_format_currency(category_context["credito_total"])}</td></tr>'
    summary_html += f'<tr><td><strong>Total Comprometido</strong></td><td style="text-align:right"><strong>{_format_currency(current["total_comprometido"])}</strong></td></tr>'
    summary_html += f'<tr><td>Saldo restante do teto</td><td style="text-align:right">{_format_currency(current["saldo_teto"])}</td></tr>'
    summary_html += f'<tr><td>Meta de aporte</td><td style="text-align:right">{_format_currency(meta_aporte)}</td></tr>'
    summary_html += f'<tr><td>Aporte projetado</td><td style="text-align:right; color:{aporte_color}; font-weight:900;">{_format_currency(current["aporte_real"])}</td></tr>'
    summary_html += '</tbody></table>'
    st.markdown(summary_html, unsafe_allow_html=True)

    tipo_icons = {"Nao_Cartao": "🏠 Essenciais", "Cartao": "💳 Cartão", "Extra": "⭐ Extras"}
    if not current["df_config"].empty and "Tipo" in current["df_config"].columns:
        tipos_col = current["df_config"]["Tipo"].astype(str).str.strip()
        for tipo in tipos_col.unique():
            df_tipo = current["df_config"][tipos_col == tipo].copy()
            with st.expander(f'{tipo_icons.get(tipo, tipo)} — **{_format_currency(float(df_tipo["Valor"].sum()))}**'):
                df_show = df_tipo[["Descricao_Fatura", "Valor", "Status_Conciliacao"]].rename(columns={"Descricao_Fatura": "Descrição", "Valor": "Valor", "Status_Conciliacao": "Status"})
                st.dataframe(df_show.style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True, hide_index=True)

    if not category_context["top_categorias_relevantes"].empty:
        st.markdown('<p class="section-header">Categorias que Mais Pressionam o Ciclo</p>', unsafe_allow_html=True)
        chart_data = category_context["top_categorias_relevantes"].reset_index()
        chart_data.columns = ["Categoria", "Valor"]
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
        st.markdown('<p class="section-header">Limites e Referências por Categoria</p>', unsafe_allow_html=True)
        for item in category_context["controles_categoria"]:
            pct_visual = min(item["pct"], 100)
            color = "linear-gradient(90deg, #ff416c, #ff4b2b)" if item["pct"] >= 100 else "linear-gradient(90deg, #f7971e, #ffd200)" if item["pct"] >= 80 else "linear-gradient(90deg, #00c9ff, #92fe9d)"
            icon = "🔴" if item["pct"] >= 100 else "🟡" if item["pct"] >= 80 else "🟢"
            st.markdown(f'<div class="cat-gauge-label"><span>{icon} <strong>{item["categoria"]}</strong> <small style="opacity:.55">({item["fonte"]})</small></span><span>{_format_currency(item["atual"])} / {_format_currency(item["referencia"])} ({item["pct"]:.1f}%)</span></div><div class="progress-outer" style="height:20px; margin-bottom:1rem;"><div class="progress-inner" style="width:{pct_visual:.1f}%; background:{color}; font-size:.75rem; padding-right:8px;">{item["pct"]:.0f}%</div></div>', unsafe_allow_html=True)

    st.markdown('<p class="section-header">Score Financeiro</p>', unsafe_allow_html=True)
    score_cls = "badge-green" if score_data["score"] >= 70 else "badge-yellow" if score_data["score"] >= 50 else "badge-red"
    st.markdown(f'<div style="display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1rem;"><span class="badge {score_cls}" style="font-size:1.05rem; padding:6px 18px;">{score_data["emoji"]} Score: {score_data["score"]}/100 — {score_data["label"]}</span><span style="opacity:.75; font-size:.92rem;">Indicador composto; use como apoio, não como diagnóstico principal.</span></div>', unsafe_allow_html=True)
    with st.expander("Detalhes metodológicos do score", expanded=False):
        for pillar, points in score_data["pilares"].items():
            maximum = {"Savings Rate": 30, "Aderência ao Teto": 25, "Meta de Aporte": 20, "Consistência": 15, "Organização": 10}.get(pillar, 10)
            pct = (points / maximum) * 100 if maximum else 0
            color = "linear-gradient(90deg, #00c9ff, #92fe9d)" if pct >= 70 else "linear-gradient(90deg, #f7971e, #ffd200)" if pct >= 50 else "linear-gradient(90deg, #ff416c, #ff4b2b)"
            st.markdown(f'<div class="cat-gauge-label"><span>{pillar}</span><span>{points}/{maximum}</span></div><div class="progress-outer" style="height:16px; margin-bottom:.75rem;"><div class="progress-inner" style="width:{pct:.0f}%; background:{color}; font-size:.7rem;"></div></div>', unsafe_allow_html=True)

    if len(category_context["radar"]) >= 3:
        st.markdown('<p class="section-header">Padrão Histórico por Categoria</p>', unsafe_allow_html=True)
        categories = [item[0] for item in category_context["radar"]]
        current_values = [item[1] for item in category_context["radar"]]
        history_values = [item[2] for item in category_context["radar"]]
        max_value = max(max(current_values, default=0), max(history_values, default=0), 1)
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=history_values + [history_values[0]], theta=categories + [categories[0]], fill="toself", name="Média histórica", line_color="#00c9ff", fillcolor="rgba(0, 201, 255, 0.18)"))
        fig_radar.add_trace(go.Scatterpolar(r=current_values + [current_values[0]], theta=categories + [categories[0]], fill="toself", name=f"Atual ({mes_sel})", line_color="#ff4b2b", fillcolor="rgba(255, 75, 43, 0.28)"))
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
    disp = current["df_ops"].copy()
    if busca and busca.strip():
        disp = disp[disp["Descricao"].str.contains(busca.strip(), case=False, na=False)]
    if filtro_cat and "Categoria" in disp.columns:
        disp = disp[disp["Categoria"].isin(filtro_cat)]
    if disp.empty:
        st.info("Nenhum lançamento atende aos filtros atuais.")
        return
    disp = _prepare_launch_table(disp).sort_values("_peso", ascending=False)
    credit_idx = set(disp.index[disp["Tipo"] == "credito"].tolist()) if "Tipo" in disp.columns else set()
    display_cols = [c for c in ["Descricao", "Categoria", "Motivo do destaque", "Valor", "Cartao", "Tipo"] if c in disp.columns]
    disp = disp[display_cols]
    disp["Valor"] = disp["Valor"].map(lambda value: _format_currency(float(value)) if isinstance(value, (int, float)) else value)
    if "Tipo" in disp.columns:
        disp["Tipo"] = disp["Tipo"].map(lambda item: "↩ Crédito" if item == "credito" else "↓ Débito")

    def _highlight_credit(row):
        return ["background-color: #14532d26; color: #22c55e; font-weight: 600"] * len(row) if row.name in credit_idx else [""] * len(row)

    st.dataframe(disp.style.apply(_highlight_credit, axis=1).hide(axis="index"), use_container_width=True)
