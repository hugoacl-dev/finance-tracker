import streamlit as st
import pandas as pd
from services.data_engine import processar_mes, dias_ate_fechamento
from services.ocr_gemini import get_gemini_client
from core.utils import mes_sort_key

def sanitize_ai_response(text: str) -> str:
    """
    Escape dollar signs to prevent LaTeX rendering in Streamlit markdown.
    This fixes the issue where R$ currency symbols cause text to be rendered
    as math notation (green text between $ symbols).
    """
    return text.replace('$', r'\$')

def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    gemini_client = get_gemini_client()
    
    all_meses = sorted(list(transacoes_data.keys()), key=mes_sort_key)
    
    # Resolvendo dependencias de escopo global legado
    RECEITA_BASE = cfg.get("Receita_Base", 0)
    META_APORTE = cfg.get("Meta_Aporte", 0)
    TETO_GASTOS = cfg.get("Teto_Gastos", 0)
    DIA_FECHAMENTO = int(cfg.get("Dia_Fechamento", 13))
    GEMINI_MODEL = cfg.get("Gemini_Model", "gemini-2.5-flash")
    GEMINI_VISION_MODEL = cfg.get("Gemini_Vision_Model", "gemini-3.1-pro-preview")
    CARTOES_ACEITOS   = cfg.get("Cartoes_Aceitos")
    CARTOES_EXCLUIDOS = cfg.get("Cartoes_Excluidos")
    
    st.markdown('<p class="section-header">🤖 Consultoria Financeira com IA</p>', unsafe_allow_html=True)
    
    if not all_meses:
        st.info("Nenhum mês cadastrado com dados para análise.")
    else:
        mes_insight = st.selectbox("Selecione o mês para a Consultoria", all_meses, index=len(all_meses) - 1, key="mes_insight_sel")
        
        if not gemini_client:
            st.warning("⚠️ API do Gemini não configurada. Adicione GEMINI_API_KEY no secrets do Streamlit.")
        else:
            # ---- Feature 3: Chatbot Financeiro ----
            st.caption("Gere um diagnóstico base ou converse livremente com a IA sobre o seu orçamento.")
            
            # Inicializa o histórico do chat
            chat_key = f"chat_history_{mes_insight}"
            if chat_key not in st.session_state:
                st.session_state[chat_key] = []
            
            # --- Prompt Editável para Diagnóstico Inicial ---
            default_prompt = (
                "Você é um CFP® (Certified Financial Planner) com especialização em Behavioral Finance "
                "e 20 anos de experiência com jovens profissionais de alta renda. Você combina rigor analítico "
                "com empatia — nunca julga, mas nunca mente.\n\n"
                "ESTILO DE COMUNICAÇÃO:\n"
                "- Tom de conversa entre mentor e mentorado — direto, sem ser frio\n"
                "- Use analogias do cotidiano para tornar conceitos financeiros tangíveis\n"
                "- Números sempre em R$ formatados (R$ 1.234,56)\n"
                "- Markdown limpo com emojis como marcadores visuais, sem exagero\n\n"
                "ESTRUTURA DA ANÁLISE:\n\n"
                "## 🩺 Diagnóstico Financeiro\n"
                "Avalie a saúde do ciclo em UMA frase-resumo (tipo \"nota do médico\"). Depois detalhe:\n"
                "- Relação Comprometido vs Teto: estourou? Por quanto? Se não, quão próximo ficou?\n"
                "- Composição Fixos vs Variáveis: qual % da renda cada um consome? A proporção é sustentável "
                "para quem quer construir patrimônio?\n"
                "- Compare com a regra 50/30/20 adaptada ao perfil do cliente\n\n"
                "## 🔍 Raio-X dos Gastos Variáveis\n"
                "Analise como um detetive financeiro:\n"
                "- Identifique os 3 maiores \"ralos\" (categorias que mais consumiram)\n"
                "- Para cada um, classifique: 🟢 Necessário | 🟡 Questionável | 🔴 Inflação de Estilo de Vida\n"
                "- Destaque um padrão comportamental (ex: \"gastos com delivery concentrados nos finais de semana "
                "sugere compra emocional por cansaço\")\n\n"
                "## 📊 Patrimônio: Estou Enriquecendo?\n"
                "Esta é a seção mais importante — o cliente quer saber se está ficando mais rico:\n"
                "- Savings Rate deste ciclo: X%. Benchmark: ≥30% excelente, 20-30% bom, <20% risco\n"
                "- Aporte Real vs Meta: bateu? Se não, quanto faltou em R$ e em % da meta?\n"
                "- Projeção de impacto: \"Se mantiver esse ritmo por 12 meses, isso representa R$ X a menos "
                "no patrimônio vs o planejado\"\n\n"
                "## 🎯 Prescrição (Máx. 3 Ações)\n"
                "Liste EXATAMENTE 2 ou 3 ações cirúrgicas para os próximos dias. Cada ação deve ter:\n"
                "- O QUE fazer (específico, não genérico)\n"
                "- QUANTO economiza (estimativa em R$)\n"
                "- IMPACTO no aporte (ex: \"isso eleva seu Savings Rate de 22% para 28%\")\n\n"
                "Encerre com UMA frase motivacional curta e genuína — não clichê."
            )
    
            with st.expander("⚙️ Personalizar Prompt do Consultor", expanded=False):
                master_prompt = st.text_area(
                    "Edite as diretrizes de avaliação da IA:",
                    value=default_prompt,
                    height=300,
                    key="master_prompt_area"
                )
                
            if st.button("🪄 Gerar Diagnóstico Financeiro Completo", use_container_width=True):
                df_c_i = pd.DataFrame(mensal_data.get(mes_insight, []))
                df_o_i = pd.DataFrame(transacoes_data.get(mes_insight, []))
                r = processar_mes(df_c_i, df_o_i, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)

                # Métricas derivadas
                aporte_real = r['aporte_real']
                savings_rate = (aporte_real / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
                pct_fixos = (r['total_fixos'] / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
                pct_var = (r['total_variaveis'] / RECEITA_BASE * 100) if RECEITA_BASE > 0 else 0
                delta_meta = aporte_real - META_APORTE
                dias_restantes = dias_ate_fechamento(DIA_FECHAMENTO)

                context = f"\n\n--- DADOS FINANCEIROS DO CICLO ({mes_insight}) ---\n"
                context += f"Receita Base: R$ {RECEITA_BASE:,.2f}\n"
                context += f"Meta de Aporte: R$ {META_APORTE:,.2f}\n"
                context += f"Teto de Gastos: R$ {TETO_GASTOS:,.2f}\n"
                context += f"Dias até fechamento: {dias_restantes}\n\n"
                context += f"--- RESUMO DO CICLO ---\n"
                context += f"Total Fixos: R$ {r['total_fixos']:,.2f} ({pct_fixos:.1f}% da receita)\n"
                context += f"Total Variáveis: R$ {r['total_variaveis']:,.2f} ({pct_var:.1f}% da receita)\n"
                context += f"Total Comprometido: R$ {r['total_comprometido']:,.2f}\n"
                context += f"Saldo Restante do Teto: R$ {r['saldo_teto']:,.2f}\n"
                context += f"Aporte Real Projetado: R$ {aporte_real:,.2f}\n"
                context += f"Δ vs Meta: R$ {delta_meta:+,.2f}\n"
                context += f"Savings Rate: {savings_rate:.1f}%\n"
                
                if not r['df_ops'].empty:
                    gastos_por_cat = r['df_ops'].groupby("Categoria")["Valor"].sum().sort_values(ascending=False)
                    context += "\n--- GASTOS VARIÁVEIS POR CATEGORIA ---\n"
                    for cat, val in gastos_por_cat.items():
                        pct_cat = (val / r['total_variaveis'] * 100) if r['total_variaveis'] > 0 else 0
                        context += f"- {cat}: R$ {val:,.2f} ({pct_cat:.1f}% dos variáveis)\n"
                    
                    top5 = r['df_ops'].nlargest(5, "Valor")
                    context += "\nTop 5 Maiores Gastos Individuais:\n"
                    for _, row in top5.iterrows():
                        cat_str = row.get('Categoria', 'Outros')
                        context += f"- {row['Descricao']} ({cat_str}): R$ {row['Valor']:,.2f}\n"
                        
                full_analysis_prompt = master_prompt + context
                
                # Adiciona ao chat a indicação de que o usuário solicitou o relatório longo
                st.session_state[chat_key].append({"role": "user", "content": "*(Solicitou Geração do Diagnóstico Financeiro Completo)*"})
                
                with st.spinner("Elaborando diagnóstico minucioso..."):
                    try:
                        response = gemini_client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=full_analysis_prompt,
                        )
                        st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                        st.rerun() # Atualiza a tela para exibir a resposta no chat
                    except Exception as e:
                        st.error(f"Erro na geração do relatório: {e}")
            
            st.markdown("---")
            # --- Chatbot interativo abaixo do expander ---
            # Exibe o histórico de mensagens
            for msg in st.session_state[chat_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(sanitize_ai_response(msg["content"]))
            
            # Caixa de texto (chat input)
            if prompt_text := st.chat_input("Pergunte algo ao seu consultor financeiro..."):
                # Adiciona a mensagem do usuário na tela
                with st.chat_message("user"):
                    st.markdown(prompt_text)
                st.session_state[chat_key].append({"role": "user", "content": prompt_text})
                
                # Monta o contexto para a LLM
                df_c_i = pd.DataFrame(mensal_data.get(mes_insight, []))
                df_o_i = pd.DataFrame(transacoes_data.get(mes_insight, []))
                r = processar_mes(df_c_i, df_o_i, perfil_ativo, TETO_GASTOS, RECEITA_BASE, META_APORTE, CARTOES_ACEITOS, CARTOES_EXCLUIDOS)
                context = f"Análise do mês: {mes_insight}\n"
                context += f"Receita Base: R$ {RECEITA_BASE:.2f} | Meta: R$ {META_APORTE:.2f} | Teto: R$ {TETO_GASTOS:.2f}\n"
                context += f"Comprometido Atual: R$ {r['total_comprometido']:.2f} (Fixos: R$ {r['total_fixos']:.2f}, Variáveis: R$ {r['total_variaveis']:.2f})\n"
                context += f"Saldo p/ Variáveis Restante: R$ {r['saldo_teto']:.2f}\n"
                if not r['df_ops'].empty:
                    gastos_por_cat = r['df_ops'].groupby("Categoria")["Valor"].sum()
                    context += "Gastos Variáveis por Categoria:\n"
                    for cat, val in gastos_por_cat.items():
                        context += f"- {cat}: R$ {val:.2f}\n"
    
                # Histórico no prompt
                historico_llm = ""
                for m in st.session_state[chat_key][:-1]:
                    historico_llm += f"{'Usuário' if m['role']=='user' else 'Consultor'}: {m['content']}\n"
                
                full_prompt = f"Você é um consultor financeiro incisivo e direto do projeto 'Finance Tracker'.\n"
                full_prompt += f"DADOS ATUAIS DO USUÁRIO:\n{context}\n\n"
                full_prompt += f"HISTÓRICO DA CONVERSA:\n{historico_llm}\n"
                full_prompt += f"Usuário: {prompt_text}\n\nResponda diretamente (use Markdown, negritos e emojis):"
                
                with st.chat_message("assistant"):
                    with st.spinner("Analisando..."):
                        try:
                            response = gemini_client.models.generate_content(
                                model=GEMINI_MODEL,
                                contents=full_prompt,
                            )
                            st.markdown(sanitize_ai_response(response.text))
                            st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                        except Exception as e:
                            st.error(f"Erro na IA: {e}")
    
    # ──────────────────────────────────────────────
    
