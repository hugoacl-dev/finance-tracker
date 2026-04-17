import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from services.data_engine import processar_mes
from services.forecasting import prever_gastos_categoria, calcular_tendencia, analisar_sazonalidade
from core.utils import mes_sort_key

def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")

    # ── Detecção de tema para gráficos Plotly ──
    try:
        _theme_base = st.get_option("theme.base")
    except Exception:
        _theme_base = "dark"
    _is_light   = (_theme_base == "light")
    _plotly_tpl = "plotly" if _is_light else "plotly_dark"
    _plotly_bg  = "rgba(0,0,0,0)"
    _plotly_plot_bg = "rgba(248,250,252,0.5)" if _is_light else "rgba(22,22,42,0.7)"
    _plotly_grid = "rgba(0,0,0,0.08)" if _is_light else "rgba(255,255,255,0.08)"
    _brand = "#0F766E" if _is_light else "#2DD4BF"
    _info = "#2563EB" if _is_light else "#60A5FA"
    _success = "#15803D" if _is_light else "#4ADE80"
    _warning = "#B45309" if _is_light else "#F59E0B"
    _danger = "#B42318" if _is_light else "#F87171"
    _bar_success = "linear-gradient(90deg, #0F766E, #34D399)"
    _bar_warning = "linear-gradient(90deg, #B45309, #F59E0B)"
    _bar_danger = "linear-gradient(90deg, #B42318, #F87171)"

    all_meses = sorted(list(transacoes_data.keys()), key=mes_sort_key)

    RECEITA_BASE   = cfg.get("Receita_Base", 0)
    META_APORTE    = cfg.get("Meta_Aporte", 0)
    TETO_GASTOS    = cfg.get("Teto_Gastos", 0)
    DIA_FECHAMENTO = int(cfg.get("Dia_Fechamento", 13))
    CARTOES_ACEITOS   = cfg.get("Cartoes_Aceitos")
    CARTOES_EXCLUIDOS = cfg.get("Cartoes_Excluidos")

    # Extrair anos disponíveis para filtro
    anos_disponiveis = sorted(set(mes_sort_key(m)[0] for m in all_meses))
    anos_labels = [str(a) for a in anos_disponiveis]

    ano_filtro = None
    if len(anos_labels) > 1:
        opcoes = ["Todos"] + anos_labels
        ano_sel = st.selectbox("Filtrar por ano", opcoes, key="filtro_ano_hist")
        if ano_sel != "Todos":
            ano_filtro = int(ano_sel)

    meses_filtrados = all_meses if ano_filtro is None else [
        m for m in all_meses if mes_sort_key(m)[0] == ano_filtro
    ]

    # ── Calcular histórico ──
    hist_rows = []
    for mes in meses_filtrados:
        try:
            df_c_m = pd.DataFrame(mensal_data.get(mes, []))
            df_o_m = pd.DataFrame(transacoes_data.get(mes, []))
            rm = processar_mes(df_c_m, df_o_m, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)
            aporte_real   = rm["aporte_real"]
            savings_rate  = (aporte_real / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
            delta_vs_meta = aporte_real - META_APORTE
            meta_pct      = (aporte_real / META_APORTE * 100) if META_APORTE > 0 else 0
            hist_rows.append({
                "Mês":              mes,
                "Comprometido":     rm["total_comprometido"],
                "Total Fixos":      rm["total_fixos"],
                "Total Variáveis":  rm["total_variaveis"],
                "Aporte Real":      aporte_real,
                "Meta Aporte":      META_APORTE,
                "_delta":           delta_vs_meta,
                "_savings_rate":    savings_rate,
                "_meta_pct":        meta_pct,
            })
        except Exception:
            pass

    if not hist_rows:
        st.info("Nenhum dado histórico disponível.")
        return

    df_hist = pd.DataFrame(hist_rows)

        # ════════════════════════════════════════════
# GRÁFICO: Dual-Axis — Savings Rate + Aporte Real
    # ════════════════════════════════════════════
    from plotly.subplots import make_subplots

    st.markdown('<p class="section-header">Poupança: Taxa vs Aporte Real</p>', unsafe_allow_html=True)

    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])

    # Barras: Aporte Real (eixo direito)
    bar_colors = [
        "rgba(21,128,61,.40)" if v >= META_APORTE else "rgba(180,35,24,.34)"
        for v in df_hist["Aporte Real"]
    ]
    fig_dual.add_trace(go.Bar(
        x=df_hist["Mês"],
        y=df_hist["Aporte Real"],
        marker_color=bar_colors,
        opacity=0.5,
        text=df_hist["Aporte Real"].map(lambda v: f"R$ {v:,.0f}"),
        textposition="outside",
        name="Aporte Real (R$)",
    ), secondary_y=True)

    # Linha: Savings Rate (eixo esquerdo)
    fig_dual.add_trace(go.Scatter(
        x=df_hist["Mês"],
        y=df_hist["_savings_rate"],
        mode="lines+markers+text",
        line=dict(color=_brand, width=3),
        marker=dict(size=9, color=_brand, line=dict(width=2, color="#fff")),
        text=df_hist["_savings_rate"].map(lambda v: f"{v:.1f}%"),
        textposition="top center",
        textfont=dict(size=11, color=_brand),
        name="Savings Rate (%)",
    ), secondary_y=False)

    # Benchmark 30%
    fig_dual.add_hline(
        y=30, secondary_y=False,
        line_dash="dot", line_color=_success, line_width=1.5,
        annotation_text="Meta 30%",
        annotation_position="top left",
        annotation_font=dict(color=_success, size=11),
    )

    fig_dual.update_layout(
        template=_plotly_tpl,
        paper_bgcolor=_plotly_bg,
        plot_bgcolor=_plotly_plot_bg,
        height=340,
        margin=dict(t=25, b=30, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font_size=11),
        bargap=0.3,
    )
    fig_dual.update_yaxes(
        title_text="Savings Rate %", secondary_y=False,
        ticksuffix="%", gridcolor=_plotly_grid, range=[0, max(df_hist["_savings_rate"].max() * 1.3, 40)],
    )
    fig_dual.update_yaxes(
        title_text="Aporte R$", secondary_y=True,
        showgrid=False,
    )
    st.plotly_chart(fig_dual, use_container_width=True)

    # ════════════════════════════════════════════
        # ════════════════════════════════════════════
# GRÁFICO: Stacked Bars — Fixos + Variáveis
    # ════════════════════════════════════════════
    st.markdown('<p class="section-header">Composição Mensal — Fixos vs Variáveis</p>',
                unsafe_allow_html=True)

    fig_stack = go.Figure()

    # Barras empilhadas: Fixos (base) + Variáveis (topo)
    fig_stack.add_trace(go.Bar(
        x=df_hist["Mês"],
        y=df_hist["Total Fixos"],
        name="Fixos",
        marker_color=_info,
        text=df_hist["Total Fixos"].map(lambda v: f"R$ {v:,.0f}"),
        textposition="inside",
        textfont=dict(size=10, color="#fff"),
    ))
    fig_stack.add_trace(go.Bar(
        x=df_hist["Mês"],
        y=df_hist["Total Variáveis"],
        name="Variáveis",
        marker_color=_warning,
        text=df_hist["Total Variáveis"].map(lambda v: f"R$ {v:,.0f}"),
        textposition="inside",
        textfont=dict(size=10, color="#fff"),
    ))

    # Linha do Teto
    fig_stack.add_hline(
        y=TETO_GASTOS,
        line_dash="dash", line_color=_danger, line_width=2.5,
        annotation_text=f"Teto R$ {TETO_GASTOS:,.0f}",
        annotation_position="top left",
        annotation_font=dict(color=_danger, size=12),
    )

    # Linha do Total (para ver se cruzou o teto)
    fig_stack.add_trace(go.Scatter(
        x=df_hist["Mês"],
        y=df_hist["Comprometido"],
        mode="lines+markers",
        line=dict(color="rgba(0,0,0,.45)" if _is_light else "rgba(255,255,255,.5)", width=1.5, dash="dot"),
        marker=dict(size=5, color="rgba(0,0,0,.55)" if _is_light else "rgba(255,255,255,.7)"),
        name="Total",
        showlegend=True,
    ))

    fig_stack.update_layout(
        template=_plotly_tpl,
        paper_bgcolor=_plotly_bg,
        plot_bgcolor=_plotly_plot_bg,
        height=380,
        margin=dict(t=30, b=40, l=30, r=15),
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font_size=11),
        yaxis=dict(gridcolor=_plotly_grid, title_text="R$"),
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # ════════════════════════════════════════════
        # ════════════════════════════════════════════
# METAS DE LONGO PRAZO — PROGRESS
    # ════════════════════════════════════════════
    data_service = st.session_state.get("data_service")
    if data_service:
        try:
            goals = data_service.get_goals(perfil_ativo)
        except Exception:
            goals = []

        if goals:
            st.markdown('<p class="section-header">🎯 Progresso das Metas</p>', unsafe_allow_html=True)

            # Determinar ciclos FECHADOS com base na data real
            from datetime import date
            hoje = date.today()

            # Mapa de conversão de nomes de meses em PT-BR para números
            meses_pt = {
                "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
                "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
            }

            ciclos_fechados = []
            for row in hist_rows:
                try:
                    mes_str = str(row.get("Mês", "")).strip().lower()
                    if not mes_str: continue

                    if "/" in mes_str:
                        # Formato numérico ex: "03/25" ou "03/2025"
                        mm, aa = mes_str.split("/")
                        mes_ciclo = int(mm)
                    else:
                        # Formato texto ex: "março 25" ou "mar 2025"
                        partes = mes_str.split()
                        if len(partes) != 2: continue
                        nome_mes, aa = partes
                        nome_mes_curto = nome_mes[:3]
                        if nome_mes_curto not in meses_pt: continue
                        mes_ciclo = meses_pt[nome_mes_curto]

                    ano_ciclo = int(aa) if len(str(aa)) == 4 else 2000 + int(aa)
                    
                    # O ciclo fecha no Dia_Fechamento do PRÓPRIO MÊS
                    mes_fech = mes_ciclo
                    ano_fech = ano_ciclo
                    data_fechamento = date(ano_fech, mes_fech, min(DIA_FECHAMENTO, 28))
                    
                    if hoje > data_fechamento:
                        ciclos_fechados.append(row)
                except Exception:
                    continue

            aporte_acumulado = 0
            aporte_mensal_medio = 0
            for row in ciclos_fechados:
                aporte_acumulado += max(0, row.get("Aporte Real", 0))
            if ciclos_fechados:
                aporte_mensal_medio = aporte_acumulado / len(ciclos_fechados)

            for g in goals:
                titulo = g["titulo"]
                valor_alvo = g["valor_alvo"]
                prazo = g["prazo_meses"]

                # Progresso baseado nos aportes acumulados
                pct = min(100, (aporte_acumulado / valor_alvo * 100)) if valor_alvo > 0 else 0
                faltante = max(0, valor_alvo - aporte_acumulado)

                # Projeção
                if aporte_mensal_medio > 0:
                    meses_restantes = faltante / aporte_mensal_medio
                    projecao_txt = f"~{int(meses_restantes)} meses restantes no ritmo atual"
                    on_track = meses_restantes <= prazo
                else:
                    projecao_txt = "Sem dados suficientes para projetar"
                    on_track = False

                bar_color = _bar_success if on_track else _bar_warning
                status_emoji = "🟢" if on_track else "🟡"

                st.markdown(f"""
                <div class="cat-gauge-label">
                    <span>{status_emoji} <strong>{titulo}</strong></span>
                    <span>R$ {aporte_acumulado:,.0f} / R$ {valor_alvo:,.0f} ({pct:.0f}%)</span>
                </div>
                <div class="progress-outer" style="height:20px; margin-bottom:.3rem;">
                    <div class="progress-inner" style="width:{min(pct, 100):.1f}%; background:{bar_color}; font-size:.7rem; padding-right:8px;">
                        {pct:.0f}%
                    </div>
                </div>
                <div style="font-size:.75rem; opacity:.6; margin-bottom:1.2rem;">
                    {projecao_txt} · Meta: {prazo} meses · Faltam R$ {faltante:,.0f}
                </div>
                """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────


    # ════════════════════════════════════════════
# TABELA DE EVOLUÇÃO PATRIMONIAL
    # ════════════════════════════════════════════
    st.markdown('<p class="section-header">📊 Evolução Patrimonial</p>', unsafe_allow_html=True)

    def _status_badge(meta_pct):
        if meta_pct >= 100:
            return '<span class="badge badge-green">🟢 Meta Batida</span>'
        elif meta_pct >= 90:
            return '<span class="badge badge-yellow">🟡 Próximo</span>'
        else:
            return '<span class="badge badge-red">🔴 Abaixo</span>'

    def _delta_html(delta):
        color = _success if delta >= 0 else _danger
        sign  = "+" if delta >= 0 else ""
        return f'<span style="color:{color}; font-weight:700">{sign}R$ {delta:,.2f}</span>'

    def _sr_bar(sr):
        """Inline Savings Rate micro-bar."""
        w = min(sr, 50)  # cap visual at 50%
        if sr >= 30:
            c = _bar_success
            cls = "badge-green"
        elif sr >= 20:
            c = _bar_warning
            cls = "badge-yellow"
        else:
            c = _bar_danger
            cls = "badge-red"
        return f'''<div style="display:flex; align-items:center; gap:8px; justify-content:flex-end;">
            <span class="badge {cls}" style="min-width:52px; text-align:center;">{sr:.1f}%</span>
            <div style="flex:1; max-width:60px; height:6px; background:{_plotly_grid}; border-radius:3px; overflow:hidden;">
                <div style="width:{w*2}%; height:100%; background:{c}; border-radius:3px;"></div>
            </div>
        </div>'''

    def _comprometido_bar(comprometido, teto):
        """Mini-bar mostrando comprometido vs teto."""
        if teto <= 0:
            return f"R$ {comprometido:,.2f}"
        pct = min((comprometido / teto) * 100, 120)
        if pct >= 100:
            c = _danger
        elif pct >= 85:
            c = _warning
        else:
            c = _brand
        return f'''<div>
            <span style="font-weight:600;">R$ {comprometido:,.2f}</span>
            <div style="height:4px; background:{_plotly_grid}; border-radius:2px; margin-top:4px; overflow:hidden;">
                <div style="width:{min(pct, 100):.0f}%; height:100%; background:{c}; border-radius:2px;"></div>
            </div>
        </div>'''

    # Encontrar melhor e pior mês
    best_sr_idx = df_hist["_savings_rate"].idxmax() if not df_hist.empty else -1
    worst_sr_idx = df_hist["_savings_rate"].idxmin() if not df_hist.empty else -1

    table_html = '<table class="summary-table">'
    table_html += (
        '<thead><tr>'
        '<th>Mês</th>'
        '<th style="text-align:right">Comprometido</th>'
        '<th style="text-align:right">Aporte Real</th>'
        '<th style="text-align:right">Δ vs Meta</th>'
        '<th style="text-align:right">Savings Rate</th>'
        '<th style="text-align:right">Status</th>'
        '</tr></thead><tbody>'
    )
    for idx, row in df_hist.iterrows():
        # Highlight para melhor/pior mês
        row_style = ""
        medal = ""
        if idx == best_sr_idx and len(df_hist) > 2:
            row_style = f'style="background:rgba(21,128,61,.08); border-left:3px solid {_success};"'
            medal = " 🏆"
        elif idx == worst_sr_idx and len(df_hist) > 2:
            row_style = f'style="background:rgba(180,35,24,.06); border-left:3px solid {_danger};"'

        table_html += (
            f'<tr {row_style}>'
            f'<td><strong>{row["Mês"]}{medal}</strong></td>'
            f'<td>{_comprometido_bar(row["Comprometido"], TETO_GASTOS)}</td>'
            f'<td style="font-weight:700;">R$ {row["Aporte Real"]:,.2f}</td>'
            f'<td>{_delta_html(row["_delta"])}</td>'
            f'<td>{_sr_bar(row["_savings_rate"])}</td>'
            f'<td>{_status_badge(row["_meta_pct"])}</td>'
            f'</tr>'
        )
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    # ════════════════════════════════════════════
        # ════════════════════════════════════════════
# PREVISÃO DE GASTOS (EMA) — tabela estilizada
    # ════════════════════════════════════════════
    if len(meses_filtrados) >= 3:
        st.markdown('<p class="section-header">🔮 Previsão do Próximo Ciclo</p>', unsafe_allow_html=True)

        # Coletar histórico por categoria
        cat_historico: dict[str, list[float]] = {}
        for m in meses_filtrados:
            cat_sums: dict[str, float] = {}
            for t in transacoes_data.get(m, []):
                c = t.get("Categoria", "Outros")
                v = float(t.get("Valor", 0))
                cat_sums[c] = cat_sums.get(c, 0) + v
            for c, v in cat_sums.items():
                if c not in cat_historico:
                    cat_historico[c] = []
                cat_historico[c].append(v)

        # Gerar previsões
        forecast_rows = []
        for cat, hist in sorted(cat_historico.items()):
            if len(hist) >= 2:
                media = sum(hist) / len(hist)
                previsao = prever_gastos_categoria(hist, alpha=0.3)
                tendencia = calcular_tendencia(hist)
                delta_pct = ((previsao - media) / media * 100) if media > 0 else 0
                forecast_rows.append({
                    "cat": cat, "media": media, "previsao": previsao,
                    "tendencia": tendencia, "delta_pct": delta_pct,
                })

        if forecast_rows:
            fc_html = '<table class="summary-table">'
            fc_html += (
                '<thead><tr>'
                '<th>Categoria</th>'
                '<th style="text-align:right">Média Hist.</th>'
                '<th style="text-align:right">Previsão</th>'
                '<th style="text-align:right">Δ</th>'
                '<th style="text-align:center">Tendência</th>'
                '</tr></thead><tbody>'
            )
            for f in forecast_rows:
                # Cores por tendência
                if f["tendencia"] == "↑":
                    t_color = _danger
                    t_bg = "rgba(180,35,24,.10)"
                elif f["tendencia"] == "↓":
                    t_color = _success
                    t_bg = "rgba(21,128,61,.10)"
                else:
                    t_color = _plotly_grid
                    t_bg = "transparent"

                d_sign = "+" if f["delta_pct"] >= 0 else ""
                d_color = _danger if f["delta_pct"] > 5 else (_success if f["delta_pct"] < -5 else "inherit")

                # Bullet micro-chart: média vs previsão
                max_val = max(f["media"], f["previsao"], 1)
                w_media = (f["media"] / max_val) * 60
                w_prev = (f["previsao"] / max_val) * 60

                bullet = f'''<div style="position:relative; width:60px; height:10px; display:inline-block; vertical-align:middle;">
                    <div style="position:absolute; width:{w_media:.0f}px; height:10px; background:rgba(37,99,235,.22); border-radius:3px;"></div>
                    <div style="position:absolute; width:3px; height:10px; left:{w_prev:.0f}px; background:{t_color}; border-radius:2px;"></div>
                </div>'''

                fc_html += (
                    f'<tr>'
                    f'<td><strong>{f["cat"]}</strong></td>'
                    f'<td>R$ {f["media"]:,.0f}</td>'
                    f'<td style="font-weight:700;">R$ {f["previsao"]:,.0f} {bullet}</td>'
                    f'<td style="color:{d_color}; font-weight:600;">{d_sign}{f["delta_pct"]:.0f}%</td>'
                    f'<td style="text-align:center;">'
                    f'<span style="display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; border-radius:8px; background:{t_bg}; font-size:1.1rem;">{f["tendencia"]}</span>'
                    f'</td>'
                    f'</tr>'
                )
            fc_html += '</tbody></table>'
            st.markdown(fc_html, unsafe_allow_html=True)
            st.caption("💡 EMA dá mais peso aos meses recentes. ↑ subindo · ↓ caindo · → estável. Barra: <span style='color:#2563EB'>█</span> média, <span style='font-weight:700'>|</span> previsão.", unsafe_allow_html=True)

    # ════════════════════════════════════════════
        # ════════════════════════════════════════════
# SAZONALIDADE
    # ════════════════════════════════════════════
    if len(meses_filtrados) >= 6:
        historico_comprometido = {row["Mês"]: row["Comprometido"] for _, row in df_hist.iterrows()}
        sazonal = analisar_sazonalidade(historico_comprometido)

        if sazonal:
            # Verificar se o mes atual está em período sazonal
            from datetime import date
            mes_atual_num = str(date.today().month).zfill(2)
            if mes_atual_num in sazonal and sazonal[mes_atual_num]["tipo"] != "normal":
                info = sazonal[mes_atual_num]
                if info["tipo"] == "alto":
                    st.warning(f"📅 **Atenção sazonal:** {info['label']}. Considere provisionar R\\$ {info['media'] - sum(historico_comprometido.values())/len(historico_comprometido):,.0f} extra.")
                else:
                    st.success(f"📅 {info['label']}. Aproveite para reforçar seus aportes!")

    # ════════════════════════════════════════════
    # ALERTAS DE TENDÊNCIA POR CATEGORIA
    # ════════════════════════════════════════════
    if len(meses_filtrados) > 1:
        st.markdown('<p class="section-header">Alertas de Tendência por Categoria</p>', unsafe_allow_html=True)
        mes_atual   = meses_filtrados[-1]
        meses_passados = meses_filtrados[:-1]

        cat_history = {}
        for m in meses_passados:
            df_ops = transacoes_data.get(m, [])
            if df_ops:
                for t in df_ops:
                    c = t.get("Categoria", "Outros")
                    v = float(t.get("Valor", 0))
                    if c not in cat_history:
                        cat_history[c] = []
                    cat_history[c].append((m, v))

        cat_avg = {}
        for c, vals in cat_history.items():
            m_sums = {}
            for m, v in vals:
                m_sums[m] = m_sums.get(m, 0) + v
            cat_avg[c] = sum(m_sums.values()) / len(meses_passados)

        curr_ops  = transacoes_data.get(mes_atual, [])
        curr_sums = {}
        for t in curr_ops:
            c = t.get("Categoria", "Outros")
            v = float(t.get("Valor", 0))
            curr_sums[c] = curr_sums.get(c, 0) + v

        alertas_gerados = False
        for c, val_atual in curr_sums.items():
            if c in cat_avg and cat_avg[c] > 0:
                avg = cat_avg[c]
                if val_atual > avg * 1.2:
                    pct_increase = ((val_atual / avg) - 1) * 100
                    st.warning(f"⚠️ **{c}**: R\\$ {val_atual:,.2f} em {mes_atual}. Isso é **{pct_increase:.0f}% acima** da sua média (R\\$ {avg:,.2f}).")
                    alertas_gerados = True

        if not alertas_gerados:
            st.success(f"Excelente! Em {mes_atual}, nenhuma categoria de gastos ultrapassou a média histórica em mais de 20%.")


    # ════════════════════════════════════════════
# DETALHAMENTO NUMÉRICO (tabela estilizada)
    # ════════════════════════════════════════════
    st.markdown('<p class="section-header">Detalhamento por Mês</p>', unsafe_allow_html=True)

    det_html = '<table class="summary-table">'
    det_html += (
        '<thead><tr>'
        '<th>Mês</th>'
        '<th style="text-align:right">Fixos</th>'
        '<th style="text-align:right">Variáveis</th>'
        '<th style="text-align:right">Total</th>'
        '<th style="text-align:right">Composição</th>'
        '</tr></thead><tbody>'
    )
    for _, row in df_hist.iterrows():
        total = row["Comprometido"]
        fixos = row["Total Fixos"]
        variaveis = row["Total Variáveis"]
        pct_fixos = (fixos / total * 100) if total > 0 else 0
        pct_var = 100 - pct_fixos

        # Cor do total baseada no teto
        total_color = _danger if total > TETO_GASTOS else _brand

        # Barra de composição fixos vs variáveis
        comp_bar = f'''<div style="display:flex; align-items:center; gap:6px; justify-content:flex-end;">
            <span style="font-size:.7rem; opacity:.7;">{pct_fixos:.0f}%</span>
            <div style="width:80px; height:8px; background:{_plotly_grid}; border-radius:4px; overflow:hidden; display:flex;">
                <div style="width:{pct_fixos}%; height:100%; background:{_info};" title="Fixos"></div>
                <div style="width:{pct_var}%; height:100%; background:{_warning};" title="Variáveis"></div>
            </div>
            <span style="font-size:.7rem; opacity:.7;">{pct_var:.0f}%</span>
        </div>'''

        det_html += (
            f'<tr>'
            f'<td><strong>{row["Mês"]}</strong></td>'
            f'<td style="color:{_info}; font-weight:600;">R$ {fixos:,.2f}</td>'
            f'<td style="color:{_warning}; font-weight:600;">R$ {variaveis:,.2f}</td>'
            f'<td style="color:{total_color}; font-weight:800;">R$ {total:,.2f}</td>'
            f'<td>{comp_bar}</td>'
            f'</tr>'
        )
    det_html += '</tbody></table>'
    st.markdown(det_html, unsafe_allow_html=True)
    st.caption("🔵 Fixos  ·  🟠 Variáveis")

    # ════════════════════════════════════════════
    
