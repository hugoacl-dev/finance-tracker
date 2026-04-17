from datetime import date
import html as html_mod
import statistics

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from services.data_engine import (
    processar_mes,
    calcular_score_financeiro, detectar_parcelamento, detectar_anomalia,
)
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
    _is_light = (_theme_base == "light")
    _plotly_tpl   = "plotly" if _is_light else "plotly_dark"
    _plotly_grid  = "rgba(0,0,0,0.08)" if _is_light else "rgba(255,255,255,0.08)"
    _plotly_bg    = "rgba(0,0,0,0)"

    all_meses = sorted(list(transacoes_data.keys()), key=mes_sort_key)

    # Resolvendo dependencias de escopo global legado
    RECEITA_BASE = cfg.get("Receita_Base", 0)
    META_APORTE  = cfg.get("Meta_Aporte", 0)
    TETO_GASTOS  = cfg.get("Teto_Gastos", 0)
    DIA_FECHAMENTO    = int(cfg.get("Dia_Fechamento", 13))
    CARTOES_ACEITOS   = cfg.get("Cartoes_Aceitos")
    CARTOES_EXCLUIDOS = cfg.get("Cartoes_Excluidos")

    if not all_meses:
        st.info("Nenhum mês cadastrado. Vá na aba ⚙️ Configurações para criar um mês.")
    else:
        mes_sel = st.selectbox("Selecione o Ciclo de Fatura", all_meses,
                               index=len(all_meses) - 1)
        idx_sel = all_meses.index(mes_sel) if mes_sel in all_meses else -1

        df_c = pd.DataFrame(mensal_data.get(mes_sel, []))
        df_o = pd.DataFrame(transacoes_data.get(mes_sel, []))
        r = processar_mes(df_c, df_o, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)
        # Determinar se o ciclo selecionado ainda está aberto (preciso para calcular burn rate)
        fechamento_display = mes_sel
        try:
            meses_pt = {
                "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
                "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
            }
            hoje = date.today()
            m_s = str(mes_sel).strip().lower()
            if "/" in m_s:
                mm, aa = m_s.split("/")
                mes_ciclo = int(mm)
            else:
                partes = m_s.split()
                nome_mes, aa = partes[0], partes[1] if len(partes) > 1 else str(hoje.year)
                mes_ciclo = meses_pt.get(nome_mes[:3], hoje.month)
                
            ano_ciclo = int(aa) if len(str(aa)) == 4 else 2000 + int(aa)
            mes_fech = mes_ciclo
            ano_fech = ano_ciclo
            data_fechamento = date(ano_fech, mes_fech, min(DIA_FECHAMENTO, 28))
            fechamento_display = data_fechamento.strftime("%d/%m")
            
            is_ciclo_ativo = hoje <= data_fechamento
            dias = (data_fechamento - hoje).days + 1 if is_ciclo_ativo else 0
        except Exception:
            hoje = date.today()
            data_fechamento = hoje
            is_ciclo_ativo = False
            dias = 0
            
        limite_diario = r["saldo_variaveis"] / dias if dias > 0 else 0
        budget_diario_inicial = r["limite_base_var"] / 30 if r["limite_base_var"] > 0 else 1
        pct_limite = (limite_diario / budget_diario_inicial) * 100

        # Savings Rate
        savings_rate = (r["aporte_real"] / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
        aporte_label = "Aporte Projetado" if is_ciclo_ativo else "Aporte Real"
        savings_label = "Savings Rate Atual" if is_ciclo_ativo else "Savings Rate Final"

        st.markdown(
            f"""
            <div class="context-bar">
                <div class="context-chip">
                    <div class="label">Receita Base</div>
                    <div class="value">R$ {RECEITA_BASE:,.2f}</div>
                </div>
                <div class="context-chip">
                    <div class="label">Teto do Ciclo</div>
                    <div class="value">R$ {TETO_GASTOS:,.2f}</div>
                </div>
                <div class="context-chip">
                    <div class="label">Meta de Aporte</div>
                    <div class="value">R$ {META_APORTE:,.2f}</div>
                </div>
                <div class="context-chip">
                    <div class="label">Fechamento</div>
                    <div class="value">{fechamento_display}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Score de Saúde Financeira ──
        qtd_outros_score = 0
        total_ops = 0
        if not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
            df_debitos = r["df_ops"][r["df_ops"]["Tipo"] != "credito"] if "Tipo" in r["df_ops"].columns else r["df_ops"]
            total_ops = len(df_debitos)
            qtd_outros_score = len(df_debitos[df_debitos["Categoria"] == "Outros"])
        pct_nao_class = (qtd_outros_score / total_ops * 100) if not r["df_ops"].empty and total_ops > 0 else 0

        # Consistência: stddev do SR dos últimos meses
        sr_history = []
        for m in all_meses[max(0, len(all_meses)-6):]:
            try:
                _df_c = pd.DataFrame(mensal_data.get(m, []))
                _df_o = pd.DataFrame(transacoes_data.get(m, []))
                _rm = processar_mes(_df_c, _df_o, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)
                _sr = (_rm["aporte_real"] / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
                sr_history.append(_sr)
            except Exception:
                pass

        std_sr = statistics.stdev(sr_history) if len(sr_history) > 1 else 0

        score_data = calcular_score_financeiro(
            savings_rate=savings_rate,
            pct_teto=r["pct_teto"],
            meta_batida=not r["meta_ameacada"],
            consistencia_std=std_sr,
            pct_nao_classificados=pct_nao_class,
        )

        # ---- CENTRAL DE AÇÕES (ONBOARDING CONSTANTE) ----
        alertas_acoes = []
        
        # 1. Gatilho de Organização (Não Classificados)
        qtd_outros = 0
        if not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
            df_debitos_alert = r["df_ops"][r["df_ops"]["Tipo"] == "debito"] if "Tipo" in r["df_ops"].columns else r["df_ops"]
            qtd_outros = len(df_debitos_alert[df_debitos_alert["Categoria"] == "Outros"])
        if qtd_outros > 0:
            alertas_acoes.append({
                "tipo": "info",
                "titulo": "🧹 Organização Pendente",
                "mensagem": f"Você possui {qtd_outros} lançamentos aguardando classificação em categorias."
            })
    
        # 2. Gatilho de Extrapolação (Anomalia de Consumo)
        if idx_sel > 0 and not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
            meses_passados = all_meses[:idx_sel]
            cat_history = {}
            for m in meses_passados:
                df_m = transacoes_data.get(m, [])
                for t in df_m:
                    c = t.get("Categoria", "Outros")
                    v = float(t.get("Valor", 0))
                    cat_history[c] = cat_history.get(c, 0) + v
            
            qtd_meses = len(meses_passados)
            if qtd_meses > 0:
                curr_sums = r["df_ops"].groupby("Categoria")["Valor"].sum()
                
                alertas_anomalia = []
                for c, val_atual in curr_sums.items():
                    if c in cat_history and cat_history[c] > 0 and c != "Outros":
                        avg = cat_history[c] / qtd_meses
                        if val_atual > avg * 1.2:
                            pct_increase = ((val_atual / avg) - 1) * 100
                            alertas_anomalia.append(f"{c} está {pct_increase:.0f}% acima da sua média")
                
                if alertas_anomalia:
                    alertas_acoes.append({
                        "tipo": "warning",
                        "titulo": "🚨 Risco de Teto (Anomalia)",
                        "mensagem": " | ".join(alertas_anomalia) + "."
                    })
    
        # 3. Gatilho de Conciliação (Fixos Pendentes)
        if dias <= 5 and not r["df_config"].empty:
            df_cartao = r["df_config"][r["df_config"]["Tipo"].astype(str).str.strip().str.lower() == "cartao"]
            if not df_cartao.empty:
                pendentes = df_cartao[df_cartao["Status_Conciliacao"] == "⏳ Pendente"]
                qtd_pendentes = len(pendentes)
                if qtd_pendentes > 0:
                    alertas_acoes.append({
                        "tipo": "warning",
                        "titulo": "⏳ Atenção aos Fixos",
                        "mensagem": f"Faltam {dias} dias para o fechamento e {qtd_pendentes} gastos fixos ainda não constam na fatura atual."
                    })
    
        # Renderização da Central de Ações
        if alertas_acoes and is_ciclo_ativo:
            st.markdown('<p class="section-header">Próximas ações</p>', unsafe_allow_html=True)
            for alerta in alertas_acoes:
                css_cls = {
                    "info": "info",
                    "warning": "warning",
                    "error": "error",
                }.get(alerta["tipo"], "info")
                st.markdown(
                    f"""
                    <div class="action-callout {css_cls}">
                        <strong>{html_mod.escape(alerta["titulo"])}</strong>
                        <span>{html_mod.escape(alerta["mensagem"])}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    
        # ---- KPI gigante ----
        if is_ciclo_ativo:
            # Burn rate: dias já passados no ciclo = total_do_ciclo - dias_restantes + 1
            # O total de dias do ciclo ~ 30-31 dias. Usar dias_ate_fechamento que retorna
            # dias restantes. Se restam 'dias' e o ciclo tem ~30 dias:
            _total_cycle = 30  # aproximação padrão de 1 ciclo de fatura
            _days_elapsed = max(1, _total_cycle - dias + 1)
            _MIN_DAYS = 7
            if _days_elapsed >= _MIN_DAYS:
                _burn = r["total_variaveis"] / _days_elapsed
                _proj_total = r["total_fixos"] + (_burn * _total_cycle)
                _forecast_str = f"🔥 Burn rate: R$ {_burn:,.2f}/dia &nbsp;·&nbsp; Projeção fechamento: R$ {_proj_total:,.2f}"
            else:
                _forecast_str = f"🔥 Burn rate: -- &nbsp;·&nbsp; Projeção fechamento: -- (disponível após {_MIN_DAYS} dias)"

            limit_color = "#0F766E" if pct_limite >= 50 else ("#B45309" if pct_limite >= 30 else "#B42318")
            danger_cls = " danger" if pct_limite < 30 else ""
            st.markdown(f"""
            <div class="survival-card{danger_cls}">
                <div class="label">Disponível até o fechamento</div>
                <div class="value" style="color:{limit_color}">R$ {limite_diario:,.2f}</div>
                <div class="sub">por dia nos próximos {dias} dias · Fecha {fechamento_display} · Ciclo {mes_sel}</div>
                <div class="forecast">{_forecast_str}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="survival-card">
                <div class="label">Ciclo encerrado</div>
                <div class="value" style="color:#2563EB">R$ {r["saldo_teto"]:,.2f}</div>
                <div class="sub">Saldo final do teto · Fecha {fechamento_display} · Ciclo {mes_sel}</div>
            </div>
            """, unsafe_allow_html=True)
    
        # ---- B1: Comparativo Mês-a-Mês ----
        delta_var, delta_saldo, delta_aporte = None, None, None
        if idx_sel > 0:
            try:
                m_ant = all_meses[idx_sel - 1]
                df_c_ant = pd.DataFrame(mensal_data.get(m_ant, []))
                df_o_ant = pd.DataFrame(transacoes_data.get(m_ant, []))
                r_ant = processar_mes(df_c_ant, df_o_ant, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)
                delta_var = r["total_variaveis"] - r_ant["total_variaveis"]
                delta_saldo = r["saldo_variaveis"] - r_ant["saldo_variaveis"]
                delta_aporte = r["aporte_real"] - r_ant["aporte_real"]
            except Exception:
                pass
    
        # ---- Métricas ----
        # Savings Rate delta vs mês anterior
        delta_sr = None
        if idx_sel > 0:
            try:
                sr_ant = (r_ant["aporte_real"] / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
                delta_sr = savings_rate - sr_ant
            except Exception:
                pass

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Variáveis", f"R$ {r['total_variaveis']:,.2f}",
                  delta=f"R$ {delta_var:+,.0f} vs anterior" if delta_var is not None else None,
                  delta_color="inverse" if delta_var and delta_var > 0 else "normal")
        c2.metric("Saldo p/ Variáveis", f"R$ {r['saldo_variaveis']:,.2f}",
                  delta=f"R$ {delta_saldo:+,.0f} vs anterior" if delta_saldo is not None else None)
        c3.metric(aporte_label, f"R$ {r['aporte_real']:,.2f}",
                  delta="OK" if not r["meta_ameacada"] else "⚠ AMEAÇADO",
                  delta_color="normal" if not r["meta_ameacada"] else "inverse")
        sr_color = "normal" if savings_rate >= 30 else "inverse"
        c4.metric(savings_label, f"{savings_rate:.1f}%",
                  delta=f"{delta_sr:+.1f}pp vs anterior" if delta_sr is not None else None,
                  delta_color=sr_color)
        st.caption(
            f"Envelope inicial para variáveis: R$ {r['limite_base_var']:,.2f} · "
            f"Saldo do teto: R$ {r['saldo_teto']:,.2f}"
        )
    
        # ── Score de Saúde Financeira (badge) ──
        _sc = score_data
        _score_cls = "badge-green" if _sc["score"] >= 70 else ("badge-yellow" if _sc["score"] >= 50 else "badge-red")
        st.markdown(f"""
        <div style="text-align:center; margin-bottom:1.5rem;">
            <span class="badge {_score_cls}" style="font-size:1.1rem; padding:6px 18px;">
                {_sc["emoji"]} Score: {_sc["score"]}/100 — {_sc["label"]}
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📊 Detalhes do Score Financeiro", expanded=False):
            _PILAR_INFO = {
                "Savings Rate": {
                    "descricao": "Percentual da receita que sobra após todos os gastos.",
                    "valor_atual": f"{savings_rate:.1f}%",
                    "criterios": "≥ 30% → 30pts | ≥ 20% → 20pts | ≥ 10% → 12pts | < 10% → 5pts",
                },
                "Aderência ao Teto": {
                    "descricao": "Quanto do teto de gastos configurado foi utilizado.",
                    "valor_atual": f"{r['pct_teto']:.1f}%",
                    "criterios": "≤ 85% → 25pts | ≤ 95% → 18pts | ≤ 100% → 10pts | > 100% → 3pts",
                },
                "Meta de Aporte": {
                    "descricao": "Se o aporte do ciclo atingiu a meta configurada.",
                    "valor_atual": f"{aporte_label}: R$ {r['aporte_real']:,.2f}",
                    "criterios": "Meta batida → 20pts | Teto ≤ 105% → 12pts | Acima → 5pts",
                },
                "Consistência": {
                    "descricao": "Estabilidade do Savings Rate nos últimos 6 meses (desvio padrão).",
                    "valor_atual": f"σ = {std_sr:.1f}pp",
                    "criterios": "σ < 5pp → 15pts | σ < 10pp → 10pts | σ ≥ 10pp → 5pts",
                },
                "Organização": {
                    "descricao": "Percentual de transações sem categoria definida.",
                    "valor_atual": f"{pct_nao_class:.1f}% sem categoria",
                    "criterios": "< 5% → 10pts | < 15% → 6pts | ≥ 15% → 2pts",
                },
            }
            for pilar, pts in _sc["pilares"].items():
                max_pts = {"Savings Rate": 30, "Aderência ao Teto": 25, "Meta de Aporte": 20, "Consistência": 15, "Organização": 10}
                mx = max_pts.get(pilar, 10)
                pct_pilar = (pts / mx) * 100
                bar_c = "linear-gradient(90deg, #0F766E, #34D399)" if pct_pilar >= 70 else ("linear-gradient(90deg, #B45309, #F59E0B)" if pct_pilar >= 50 else "linear-gradient(90deg, #B42318, #F87171)")
                col_label, col_btn = st.columns([11, 1])
                with col_label:
                    st.markdown(f"""
                    <div class="cat-gauge-label"><span>{pilar}</span><span>{pts}/{mx}</span></div>
                    <div class="progress-outer" style="height:16px; margin-bottom:.8rem;">
                        <div class="progress-inner" style="width:{pct_pilar:.0f}%; background:{bar_c}; font-size:.7rem;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_btn:
                    info = _PILAR_INFO.get(pilar, {})
                    with st.popover("ℹ️"):
                        st.markdown(f"**{pilar}**")
                        st.caption(info.get("descricao", ""))
                        st.markdown(f"**Valor atual:** {info.get('valor_atual', '--')}")
                        st.markdown(f"**Critérios:** {info.get('criterios', '--')}")
                        st.markdown(f"**Pontuação obtida:** {pts}/{mx} pts")

        # ---- Barra de progresso ----
        st.markdown('<p class="section-header">Consumo do Teto</p>', unsafe_allow_html=True)
    
        pct = min(r["pct_teto"], 100)
        if pct >= 90:
            bar_color = "linear-gradient(90deg, #B42318, #F87171)"
        elif pct >= 85:
            bar_color = "linear-gradient(90deg, #B45309, #F59E0B)"
        else:
            bar_color = "linear-gradient(90deg, #0F766E, #34D399)"
    
        st.markdown(f"""
        <div class="progress-outer">
            <div class="progress-inner" style="width:{pct:.1f}%; background:{bar_color};">
                {pct:.1f}%  ·  R$ {r['total_comprometido']:,.2f} / R$ {TETO_GASTOS:,.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
        # ---- Feature B6x: Conciliação de Gastos Fixos ----
        if not r["df_config"].empty:
            df_cartao = r["df_config"][r["df_config"]["Tipo"].astype(str).str.strip().str.lower() == "cartao"]
            if not df_cartao.empty:
                confirmados = df_cartao[df_cartao["Status_Conciliacao"] == "✅ Confirmado"]
                pendentes = df_cartao[df_cartao["Status_Conciliacao"] != "✅ Confirmado"]
                total_c = len(df_cartao)
                qtd_conf = len(confirmados)
                
                with st.expander(f"✅ Conciliação de Gastos Fixos ({qtd_conf}/{total_c})", expanded=not pendentes.empty):
                    st.caption("Este bloco responde à pergunta: o que ainda precisa ser conferido?")
                    if not pendentes.empty:
                        st.markdown("**Pendentes**")
                        st.dataframe(
                            pendentes[["Descricao_Fatura", "Valor", "Status_Conciliacao"]].rename(
                                columns={"Descricao_Fatura": "Descrição", "Status_Conciliacao": "Status"}
                            ).style.format({"Valor": "R$ {:,.2f}"}),
                            use_container_width=True,
                            hide_index=True,
                        )
                    if not confirmados.empty:
                        with st.expander("Ver confirmados", expanded=False):
                            st.dataframe(
                                confirmados[["Descricao_Fatura", "Valor", "Status_Conciliacao"]].rename(
                                    columns={"Descricao_Fatura": "Descrição", "Status_Conciliacao": "Status"}
                                ).style.format({"Valor": "R$ {:,.2f}"}),
                                use_container_width=True,
                                hide_index=True,
                            )
    
        # ---- Resumo ----
        st.markdown('<p class="section-header">Resumo do Orçamento</p>', unsafe_allow_html=True)
    
        tipo_sums = {}
        if not r["df_config"].empty:
            tipos_col = r["df_config"]["Tipo"].astype(str).str.strip()
            for tipo in tipos_col.unique():
                tipo_sums[tipo] = r["df_config"][tipos_col == tipo]["Valor"].sum()
    
        tipo_icons = {"Nao_Cartao": "🏠 Essenciais", "Cartao": "💳 Cartão", "Extra": "⭐ Extras"}

        # Expanders interativos para os Gastos Fixos
        if not r["df_config"].empty:
            for tipo, val in tipo_sums.items():
                label = tipo_icons.get(tipo, f"Fixos — {tipo}")
                with st.expander(f"{label} — **R$ {val:,.2f}**"):
                    df_tipo = r["df_config"][tipos_col == tipo].copy()
                    if not df_tipo.empty:
                        if tipo.strip().lower() == "cartao":
                            qtd_total = len(df_tipo)
                            qtd_confirmados = len(df_tipo[df_tipo["Status_Conciliacao"] == "✅ Confirmado"])
                            qtd_pendentes = qtd_total - qtd_confirmados
                            k1, k2, k3 = st.columns(3)
                            k1.metric("Itens", f"{qtd_total}")
                            k2.metric("Confirmados", f"{qtd_confirmados}")
                            k3.metric("Pendentes", f"{qtd_pendentes}")
                            st.caption("Resumo financeiro dos fixos de cartão. Os detalhes operacionais ficam no bloco de conciliação.")
                        else:
                            df_show = df_tipo[["Descricao_Fatura", "Valor"]].rename(
                                columns={"Descricao_Fatura": "Descrição"}
                            )
                            st.dataframe(
                                df_show.style.format({"Valor": "R$ {:,.2f}"}),
                                use_container_width=True,
                                hide_index=True
                            )

        # Créditos do mês (estornos, IOF, devoluções)
        df_creditos = pd.DataFrame()
        total_creditos = 0.0
        if not r["df_ops"].empty and "Tipo" in r["df_ops"].columns:
            df_creditos = r["df_ops"][r["df_ops"]["Tipo"] == "credito"].copy()
            total_creditos = df_creditos["Valor"].sum()

        # Tabela unificada para o restante do resumo
        table_html = '<table class="summary-table" style="margin-top: 0.15rem;">'
        table_html += '<tbody>'
        table_html += f'<tr><td><strong>Total Fixos</strong></td><td style="text-align:right"><strong>R$ {r["total_fixos"]:,.2f}</strong></td></tr>'
        if total_creditos > 0:
            table_html += f'<tr><td style="color:var(--success);">↩ Créditos/Estornos</td><td style="text-align:right; color:var(--success);">− R$ {total_creditos:,.2f}</td></tr>'
        table_html += f'<tr><td><strong>Total Comprometido</strong></td><td style="text-align:right"><strong>R$ {r["total_comprometido"]:,.2f}</strong></td></tr>'
        table_html += f'<tr><td>Saldo Restante do Teto</td><td style="text-align:right">R$ {r["saldo_teto"]:,.2f}</td></tr>'
        table_html += f'<tr><td>Meta de Aporte</td><td style="text-align:right">R$ {META_APORTE:,.2f}</td></tr>'
        table_html += '</tbody></table>'
    
        st.markdown(table_html, unsafe_allow_html=True)
    
        # ---- Feature 1: Gráficos de Composição (Treemap e Rosca) ----
        if not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
            st.markdown('<p class="section-header">Onde o dinheiro se dilui</p>', unsafe_allow_html=True)
            if "Tipo" in r["df_ops"].columns:
                df_tree = r["df_ops"][(r["df_ops"]["Valor"] > 0) & (r["df_ops"]["Tipo"] == "debito")].copy()
            else:
                df_tree = r["df_ops"][r["df_ops"]["Valor"] > 0].copy()
            if not df_tree.empty:
                # Preenchendo valores nulos para evitar erros nos gráficos
                df_tree["Descricao"] = df_tree["Descricao"].fillna("Desconhecido")
                
                tab_donut, tab_tree = st.tabs(["🍩 Visão Macro (Categorias)", "🗂️ Visão Detalhada (Treemap)"])
                
                with tab_donut:
                    df_cat = df_tree.groupby('Categoria', as_index=False)['Valor'].sum()
                    df_cat = df_cat.sort_values(by='Valor', ascending=False)
                    
                    fig_donut = px.pie(
                        df_cat, 
                        names='Categoria', 
                        values='Valor',
                        hole=0.55,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_donut.update_traces(
                        textinfo="percent+label",
                        texttemplate="<b>%{label}</b><br>%{percent:.1%}",
                        hovertemplate="<b>%{label}</b><br>Gasto: R$ %{value:,.2f}<br>Representa %{percent:.1%} do total<extra></extra>",
                        textposition="outside"
                    )
                    
                    total_var = df_cat['Valor'].sum()
                    fig_donut.update_layout(
                        template=_plotly_tpl,
                        paper_bgcolor=_plotly_bg,
                        plot_bgcolor=_plotly_bg,
                        margin=dict(t=30, b=30, l=10, r=10),
                        height=450,
                        showlegend=False,
                        annotations=[dict(
                            text=f"<b>Variáveis</b><br><span style='font-size: 20px;'>R$ {total_var:,.2f}</span>",
                            x=0.5, y=0.5,
                            font_size=16,
                            showarrow=False
                        )]
                    )
                    st.plotly_chart(fig_donut, use_container_width=True)
                
                with tab_tree:
                    fig_tree = px.treemap(
                        df_tree, 
                        path=[px.Constant("Variáveis"), 'Categoria', 'Descricao'], 
                        values='Valor',
                        color='Categoria',
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_tree.update_traces(
                        textinfo="label+value+percent parent",
                        texttemplate="%{label}<br>R$ %{value:,.2f}<br>%{percentParent:.1%}",
                        hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Representa %{percentParent:.1%} da categoria superior<extra></extra>"
                    )
                    fig_tree.update_layout(
                        template=_plotly_tpl,
                        paper_bgcolor=_plotly_bg,
                        plot_bgcolor=_plotly_bg,
                        margin=dict(t=20, b=20, l=10, r=10),
                        height=500
                    )
                    st.plotly_chart(fig_tree, use_container_width=True)

        # ---- Créditos e Estornos ----
        if not df_creditos.empty:
            with st.expander(f"↩ Créditos e Estornos — **− R$ {total_creditos:,.2f}**"):
                cols_show = [c for c in ["Descricao", "Valor", "Cartao", "Titular"] if c in df_creditos.columns]
                df_cred_show = df_creditos[cols_show].rename(columns={
                    "Descricao": "Descrição", "Valor": "Valor (R$)", "Cartao": "Cartão", "Titular": "Titular"
                })
                st.dataframe(
                    df_cred_show.style.format({"Valor (R$)": "R$ {:,.2f}"}),
                    use_container_width=True,
                    hide_index=True,
                )

        # ---- Gamificação: Radar e Progresso por Categoria ----
        if idx_sel > 0 and not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
            meses_passados = all_meses[:idx_sel]
            qtd_meses = len(meses_passados)
            
            if qtd_meses > 0:
                cat_hist_sums = {}
                for m in meses_passados:
                    df_m = transacoes_data.get(m, [])
                    for t in df_m:
                        c = t.get("Categoria", "Outros")
                        v = float(t.get("Valor", 0))
                        cat_hist_sums[c] = cat_hist_sums.get(c, 0) + v
                
                cat_hist_avg = {c: val / qtd_meses for c, val in cat_hist_sums.items() if val > 0 and c != "Outros"}
                curr_sums = r["df_ops"].groupby("Categoria")["Valor"].sum().to_dict()
                
                categorias_analise = set(cat_hist_avg.keys()).union(set(curr_sums.keys()) - {"Outros"})
                categorias_analise = sorted(list(categorias_analise))
                
                if len(categorias_analise) >= 3:
                    st.markdown('<p class="section-header">Radar de Consumo: Atual vs Média Histórica</p>', unsafe_allow_html=True)
                    
                    vals_atual = [curr_sums.get(c, 0) for c in categorias_analise]
                    vals_hist = [cat_hist_avg.get(c, 0) for c in categorias_analise]
                    
                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals_hist + [vals_hist[0]],
                        theta=categorias_analise + [categorias_analise[0]],
                        fill='toself',
                        name='Média Histórica',
                        line_color='#0F766E',
                        fillcolor='rgba(15, 118, 110, 0.18)'
                    ))
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals_atual + [vals_atual[0]],
                        theta=categorias_analise + [categorias_analise[0]],
                        fill='toself',
                        name=f'Atual ({mes_sel})',
                        line_color='#B45309',
                        fillcolor='rgba(180, 83, 9, 0.28)'
                    ))
                    fig_radar.update_layout(
                        template=_plotly_tpl,
                        paper_bgcolor=_plotly_bg,
                        plot_bgcolor=_plotly_bg,
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, max(max(vals_atual, default=0), max(vals_hist, default=0)) * 1.1],
                                showticklabels=False
                            )
                        ),
                        showlegend=True,
                        height=400,
                        margin=dict(t=40, b=40, l=40, r=40),
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)

                st.markdown('<p class="section-header">Controle de Limites por Categoria</p>', unsafe_allow_html=True)

                # Carregar limites definidos pelo usuário
                _cat_budgets = {}
                _ds = st.session_state.get("data_service")
                if _ds:
                    try:
                        _cat_budgets = _ds.get_category_budgets(perfil_ativo)
                    except Exception:
                        pass

                for c in categorias_analise:
                    val_atual = curr_sums.get(c, 0)
                    # Prioridade: limite definido pelo usuário > média histórica
                    limite = _cat_budgets.get(c, cat_hist_avg.get(c, 0))
                    fonte = "Orçamento" if c in _cat_budgets else "Média Hist."
                    
                    if limite > 0:
                        pct_cat = (val_atual / limite) * 100
                        pct_visual = min(pct_cat, 100)
                        
                        if pct_cat >= 100:
                            bar_color = "linear-gradient(90deg, #B42318, #F87171)" # Estourou
                            status_icon = "🔴"
                        elif pct_cat >= 80:
                            bar_color = "linear-gradient(90deg, #B45309, #F59E0B)" # Alerta
                            status_icon = "🟡"
                        else:
                            bar_color = "linear-gradient(90deg, #0F766E, #34D399)" # Seguro
                            status_icon = "🟢"
                            
                        st.markdown(f"""
                        <div class="cat-gauge-label">
                            <span>{status_icon} <strong>{c}</strong> <small style="opacity:.5">({fonte})</small></span>
                            <span>R$ {val_atual:,.2f} / R$ {limite:,.2f} ({pct_cat:.1f}%)</span>
                        </div>
                        <div class="progress-outer" style="height: 20px; margin-bottom: 1.2rem;">
                            <div class="progress-inner" style="width:{pct_visual:.1f}%; background:{bar_color}; font-size: 0.75rem; padding-right: 8px;">
                                {pct_cat:.0f}%
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    
        # ---- Tabela de lançamentos com busca, anomalias e parcelamentos ----
        st.markdown(f'<p class="section-header">Lançamentos — {mes_sel}</p>', unsafe_allow_html=True)
    
        if r["df_ops"].empty:
            st.info("Nenhum lançamento após aplicação dos filtros.")
        else:
            col_busca, col_filt_cat = st.columns(2)
            with col_busca:
                busca = st.text_input("🔍 Buscar lançamento", key="busca_lancamentos",
                                      placeholder="Ex: UBER, COBASI...")
            with col_filt_cat:
                opcoes_cat = sorted(r["df_ops"]["Categoria"].unique().tolist()) if "Categoria" in r["df_ops"].columns else []
                filtro_cat = st.multiselect("Filtrar por Categoria", options=opcoes_cat, default=None, key="filtro_cat_lanc")
    
            display_cols = [c for c in ["Descricao", "Categoria", "Valor", "Cartao", "Tipo"] if c in r["df_ops"].columns]
            disp = r["df_ops"][display_cols].copy()

            if busca and busca.strip():
                mask_text = disp["Descricao"].str.contains(busca.strip(), case=False, na=False)
                disp = disp[mask_text]

            if filtro_cat:
                disp = disp[disp["Categoria"].isin(filtro_cat)]

            # Captura índices de crédito ANTES de qualquer transformação
            credito_idx = set(disp.index[disp["Tipo"] == "credito"].tolist()) if "Tipo" in disp.columns else set()

            # Enriquecer com anomalias e parcelamentos
            if "Categoria" in disp.columns and "Valor" in disp.columns:
                cat_stats = r["df_ops"].groupby("Categoria")["Valor"].agg(["mean", "std"]).to_dict(orient="index")
                flags = []
                for _, row in disp.iterrows():
                    flag_parts = []
                    cat = row.get("Categoria", "")
                    val = row.get("Valor", 0) if isinstance(row.get("Valor"), (int, float)) else 0
                    # Anomalia
                    if cat in cat_stats:
                        mean_c = cat_stats[cat].get("mean", 0)
                        std_c = cat_stats[cat].get("std", 0)
                        if std_c and detectar_anomalia(val, mean_c, std_c, z_threshold=1.8):
                            flag_parts.append("⚠️")
                    # Parcelamento
                    desc = str(row.get("Descricao", ""))
                    parc = detectar_parcelamento(desc)
                    if parc:
                        flag_parts.append(f"📦 {parc[0]}/{parc[1]}")
                    flags.append(" ".join(flag_parts))
                disp.insert(0, "Flags", flags)

            disp["Valor"] = disp["Valor"].map(lambda v: f"R$ {v:,.2f}" if isinstance(v, (int, float)) else v)

            if "Tipo" in disp.columns:
                disp["Tipo"] = disp["Tipo"].map(lambda t: "↩ Crédito" if t == "credito" else "↓ Débito")

            def _highlight_credito(row):
                if row.name in credito_idx:
                    return ["background-color: rgba(21,128,61,.08); color: #15803D; font-weight: 600"] * len(row)
                return [""] * len(row)

            st.dataframe(
                disp.style.apply(_highlight_credito, axis=1).hide(axis="index"),
                use_container_width=True,
            )


    # ──────────────────────────────────────────────
