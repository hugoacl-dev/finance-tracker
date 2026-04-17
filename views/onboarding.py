"""
Onboarding Wizard — Guia de introdução ao FTracker.
Ativado na primeira visita (sem meses cadastrados e sem flag onboarding_done).
"""
import streamlit as st


def render_onboarding() -> None:
    """
    Renderiza o wizard de onboarding em 4 passos.
    Renderiza o onboarding e controla a navegação via session_state.
    """
    if "onboarding_step" not in st.session_state:
        st.session_state["onboarding_step"] = 1

    step = st.session_state["onboarding_step"]
    total_steps = 4

    # ── Progress dots ──
    dots = ""
    for i in range(1, total_steps + 1):
        dots += "● " if i == step else "○ "

    st.markdown(f"""
    <div style="text-align:center; padding: 2rem 0 1rem 0;">
        <span style="font-size: 2.5rem;">💰</span>
        <h2 style="margin: .5rem 0 .2rem 0;">Bem-vindo ao Finance Tracker!</h2>
        <p style="opacity:.6; font-size:.95rem;">Vamos configurar tudo em {total_steps} passos rápidos</p>
        <p style="font-size:1.3rem; letter-spacing:6px;">{dots}</p>
    </div>
    """, unsafe_allow_html=True)

    data_service = st.session_state.get("data_service")
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    cfg = st.session_state.get("cfg", {})

    # ═══════════════════════════════════════
    # PASSO 1: Parâmetros
    # ═══════════════════════════════════════
    if step == 1:
        st.markdown("### 📊 Passo 1 — Seus Parâmetros Financeiros")
        st.caption("Esses valores definem o coração do seu planejamento.")

        receita = st.number_input(
            "💵 Receita Base (líquida mensal)",
            min_value=0.0, value=float(cfg.get("Receita_Base", 0)),
            step=500.0, format="%.2f",
            help="Sua renda líquida mensal total."
        )
        meta = st.number_input(
            "🎯 Meta de Aporte (investir por mês)",
            min_value=0.0, value=float(cfg.get("Meta_Aporte", 0)),
            step=500.0, format="%.2f",
            help="Quanto você quer investir todo mês."
        )
        teto = st.number_input(
            "🚧 Teto de Gastos (máximo mensal)",
            min_value=0.0, value=float(cfg.get("Teto_Gastos", 0)),
            step=500.0, format="%.2f",
            help="Limite total que você permite gastar."
        )
        dia_fech = st.number_input(
            "📅 Dia do Fechamento da Fatura",
            min_value=1, max_value=28, value=int(cfg.get("Dia_Fechamento", 13)),
            help="O dia em que seu ciclo de fatura vira."
        )

        if receita > 0 and meta > 0 and teto > 0:
            sr = (meta / receita) * 100
            st.info(f"Com esses parâmetros, seu Savings Rate alvo é **{sr:.0f}%**. "
                    f"{'🟢 Excelente!' if sr >= 30 else '🟡 Bom, mas mire em 30%+.' if sr >= 20 else '🔴 Considere aumentar sua meta.'}")

        col_back, col_next = st.columns(2)
        with col_next:
            if st.button("Próximo →", use_container_width=True, type="primary"):
                if receita > 0 and teto > 0:
                    new_cfg = {
                        "Receita_Base": receita,
                        "Meta_Aporte": meta,
                        "Teto_Gastos": teto,
                        "Dia_Fechamento": dia_fech,
                    }
                    if data_service:
                        data_service.update_profile_config(perfil_ativo, new_cfg)
                    cfg.update(new_cfg)
                    st.session_state["cfg"] = cfg
                    st.session_state["onboarding_step"] = 2
                    st.rerun()
                else:
                    st.error("Preencha Receita Base e Teto de Gastos.")

    # ═══════════════════════════════════════
    # PASSO 2: Criar Primeiro Mês
    # ═══════════════════════════════════════
    elif step == 2:
        st.markdown("### 📅 Passo 2 — Crie seu Primeiro Ciclo")
        st.caption("Cada ciclo representa um mês de fatura.")

        from datetime import date
        hoje = date.today()
        meses_pt = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
                    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
                    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
        sugestao = f"{hoje.month:02d}/{str(hoje.year)[2:]}"

        nome_mes = st.text_input(
            "Nome do ciclo (formato MM/AA)",
            value=sugestao,
            help="Ex: 03/25 para Março de 2025"
        )

        st.info(f"💡 Dica: Use o formato **MM/AA** (ex: {sugestao}) para consistência.")

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Voltar", use_container_width=True):
                st.session_state["onboarding_step"] = 1
                st.rerun()
        with col_next:
            if st.button("Próximo →", use_container_width=True, type="primary"):
                if nome_mes and nome_mes.strip():
                    if data_service:
                        data_service.create_mes(perfil_ativo, nome_mes.strip())
                    st.session_state["onboarding_mes"] = nome_mes.strip()
                    st.session_state["onboarding_step"] = 3
                    st.rerun()
                else:
                    st.error("Informe o nome do ciclo.")

    # ═══════════════════════════════════════
    # PASSO 3: Gastos Fixos
    # ═══════════════════════════════════════
    elif step == 3:
        mes = st.session_state.get("onboarding_mes", "")
        st.markdown(f"### 🏠 Passo 3 — Gastos Fixos Recorrentes ({mes})")
        st.caption("Adicione gastos que se repetem todo mês: aluguel, plano de saúde, etc.")

        if "onboarding_fixos" not in st.session_state:
            st.session_state["onboarding_fixos"] = []

        TIPO_LABELS = {
            "Nao_Cartao": "Não Cartão (débito/PIX)",
            "Cartao": "Cartão de Crédito",
            "Extra": "Extra / Eventual",
        }
        TIPO_OPTIONS = list(TIPO_LABELS.keys())
        TIPO_DISPLAY = list(TIPO_LABELS.values())

        # Formulário para adicionar
        with st.form("add_fixo_form", clear_on_submit=True):
            f_cols = st.columns([3, 2, 2])
            with f_cols[0]:
                desc = st.text_input("Descrição", placeholder="Ex: Aluguel")
            with f_cols[1]:
                tipo_idx = st.selectbox("Tipo", range(len(TIPO_OPTIONS)),
                                        format_func=lambda i: TIPO_DISPLAY[i])
            with f_cols[2]:
                valor = st.number_input("Valor (R$)", min_value=0.0, step=50.0, format="%.2f")

            if st.form_submit_button("➕ Adicionar", use_container_width=True):
                if desc and valor > 0:
                    st.session_state["onboarding_fixos"].append({
                        "Descricao_Fatura": desc,
                        "Tipo": TIPO_OPTIONS[tipo_idx],
                        "Valor": valor,
                    })

        # Mostrar fixos adicionados
        if st.session_state["onboarding_fixos"]:
            total = sum(f["Valor"] for f in st.session_state["onboarding_fixos"])
            st.markdown(f"**{len(st.session_state['onboarding_fixos'])} gastos fixos** · Total: **R\\$ {total:,.2f}**")
            for i, f in enumerate(st.session_state["onboarding_fixos"]):
                row_cols = st.columns([4, 3, 2, 1])
                row_cols[0].text(f["Descricao_Fatura"])
                row_cols[1].text(TIPO_LABELS.get(f["Tipo"], f["Tipo"]))
                row_cols[2].text(f"R$ {f['Valor']:,.2f}")
                if row_cols[3].button("✕", key=f"rm_fixo_{i}"):
                    st.session_state["onboarding_fixos"].pop(i)
                    st.rerun()

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Voltar", use_container_width=True):
                st.session_state["onboarding_step"] = 2
                st.rerun()
        with col_next:
            if st.button("Próximo →", use_container_width=True, type="primary"):
                mes = st.session_state.get("onboarding_mes", "")
                if data_service and st.session_state["onboarding_fixos"]:
                    data_service.save_gastos_fixos(
                        perfil_ativo, mes, st.session_state["onboarding_fixos"]
                    )
                st.session_state["onboarding_step"] = 4
                st.rerun()

    # ═══════════════════════════════════════
    # PASSO 4: Concluir
    # ═══════════════════════════════════════
    elif step == 4:
        st.markdown("### 🚀 Passo 4 — Tudo Pronto!")

        st.markdown("""
        Seu Finance Tracker está configurado! Aqui está o que você pode fazer agora:

        - **🔬 Raio-X do Ciclo** — Veja o resumo financeiro do mês
        - **📈 Evolução Histórica** — Acompanhe seu progresso ao longo do tempo
        - **🤖 Insights IA** — Importe sua fatura e receba diagnóstico inteligente
        - **⚙️ Configurações** — Ajuste parâmetros e importe dados

        💡 **Próximo passo:** Vá na aba **🤖 Insights IA** e importe a foto da sua fatura do cartão!
        """)

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Voltar", use_container_width=True):
                st.session_state["onboarding_step"] = 3
                st.rerun()
        with col_next:
            if st.button("🎉 Começar a usar!", use_container_width=True, type="primary"):
                if data_service:
                    data_service.update_profile_config(perfil_ativo, {"onboarding_done": True})
                st.session_state["onboarding_done"] = True
                # Reload data
                mensal = data_service.get_mensal_data(perfil_ativo) if data_service else {}
                transacoes = data_service.get_transacoes_data(perfil_ativo) if data_service else {}
                st.session_state["mensal_data"] = mensal
                st.session_state["transacoes_data"] = transacoes
                st.rerun()

    return
