import json
import streamlit as st
import pandas as pd
from services.data_engine import process_idempotency_pass, is_similar, normalize_text
from services.ocr_gemini import get_gemini_client
from core.utils import mes_sort_key
import PIL.Image
import re
import time
import difflib

def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    cfg_raw = st.session_state.get("cfg_raw", {})
    gemini_client = get_gemini_client()
    data_service = st.session_state.get("data_service")  # Obter data_service do session_state
    
    all_meses = sorted(list(transacoes_data.keys()), key=mes_sort_key)
    
    # Resolvendo dependencias de escopo global legado
    RECEITA_BASE = cfg.get("Receita_Base", 0)
    META_APORTE = cfg.get("Meta_Aporte", 0)
    TETO_GASTOS = cfg.get("Teto_Gastos", 0)
    DIA_FECHAMENTO = int(cfg.get("Dia_Fechamento", 13))
    GEMINI_MODEL = cfg.get("Gemini_Model", "gemini-2.5-flash")
    GEMINI_VISION_MODEL = cfg.get("Gemini_Vision_Model", "gemini-3.1-pro-preview")
    meses_trans = sorted(set(list(mensal_data.keys()) + list(transacoes_data.keys())))
    
    if meses_trans:
        if "trans_mes_edit" not in st.session_state or st.session_state["trans_mes_edit"] not in meses_trans:
            st.session_state["trans_mes_edit"] = meses_trans[-1]
        mes_trans = st.selectbox("Selecione o mês desejado", meses_trans,
                                 key="trans_mes_edit")
    
        # ── Importação em Lote ──
        st.markdown("---")
        st.markdown('<p class="section-header">Importação em Lote</p>', unsafe_allow_html=True)
        
        ultima_imp = cfg_raw.get("Ultima_Importacao", "Ainda não realizada") if cfg_raw else "Ainda não realizada"
        st.caption(f"🕒 **Última importação confirmada:** {ultima_imp}")
        
        todas_trans_mes = transacoes_data.get(mes_trans, [])
        if todas_trans_mes:
            ultimas_por_cartao = {}
            for t in todas_trans_mes:
                cartao_nome = t.get("Cartao", "Desconhecido").strip()
                if cartao_nome:
                    ultimas_por_cartao[cartao_nome] = t
            
            if ultimas_por_cartao:
                msg_alert = "**📌 Último lançamento salvo por cartão neste mês:**\n"
                for c, t in ultimas_por_cartao.items():
                    desc = t.get('Descricao', '')
                    valor = float(t.get('Valor', 0))
                    msg_alert += f"- **{c}**: {desc} (R$ {valor:,.2f})\n"
                st.info(msg_alert)
    
        tipo_lote = st.radio("Método de Importação", ["📸 Imagem Inteligente", "📝 Texto"], horizontal=True, label_visibility="collapsed")
    
        if tipo_lote == "📝 Texto":
            st.caption("Cole as linhas no formato: `Descrição` **TAB** `Valor` (uma por linha)")
    
            col_lote1, col_lote2 = st.columns([3, 1])
            with col_lote2:
                cartao_lote = st.text_input("Cartão genérico para o lote",
                                            value="", key="cartao_lote",
                                            placeholder="Ex: 1234, Nubank",
                                            help="Ex: 1234, Nubank, Itau")
    
            if st.session_state.get("clear_lote"):
                st.session_state["texto_lote"] = ""
                del st.session_state["clear_lote"]
    
            with col_lote1:
                texto_lote = st.text_area(
                    "Cole os lançamentos aqui",
                    height=200,
                    placeholder="12/02 IFD BR\tR$ 5,95\n13/02 RESORT JARDIM ATLANTIC\tR$ 236,50\n13/02 OTICKET\tR$ 180,00",
                    key="texto_lote",
                )
        else:
            texto_lote = ""
            
            if "uploader_key" not in st.session_state:
                st.session_state["uploader_key"] = 1
                
            if st.session_state.get("clear_lote"):
                st.session_state["uploader_key"] += 1
                del st.session_state["clear_lote"]
                
            imagem_lote = st.file_uploader("Upload da Fatura", type=["png", "jpg", "jpeg"], key=f"img_lote_{st.session_state['uploader_key']}")
    
        def parse_valor_br(v: str) -> float:
            s = str(v).strip()
            s = re.sub(r"^R\$\s*", "", s)
            s = s.replace(" ", "")
            if "," in s:
                s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return 0.0
    
        # Mostrar mensagem de sucesso de importação anterior
        if st.session_state.get("lote_success_msg"):
            st.success(st.session_state.pop("lote_success_msg"))
    
        if "lote_pendente" not in st.session_state and "lote_ignorados" not in st.session_state and "lote_roteamento_img" not in st.session_state:
            if tipo_lote == "📝 Texto":
                if st.button("📥 Importar e Classificar", use_container_width=True, key="importar_lote_txt"):
                    if not texto_lote or not texto_lote.strip():
                        st.warning("Cole os lançamentos na caixa de texto acima.")
                    else:
                        linhas = texto_lote.strip().split("\n")
                        novos = []
                        ignorados = []
                    erros = 0
                    
                    todas_trans_mes_lote = transacoes_data.get(mes_trans, [])
                    cartao_limpo = cartao_lote.strip()
                    buffer_trans = []
                    for t in todas_trans_mes_lote:
                        if t.get("Cartao", "").strip() == cartao_limpo:
                            buffer_trans.append({
                                "Descricao": str(t.get("Descricao", "")).strip(),
                                "Valor": float(t.get("Valor", 0))
                            })
    
                    for linha in linhas:
                        linha = linha.strip()
                        if not linha:
                            continue
                        # Tentar separar por TAB
                        partes = linha.split("\t")
                        if len(partes) >= 2:
                            desc = partes[0].strip()
                            val = parse_valor_br(partes[1])
                        else:
                            # Tentar separar por último espaço antes de R$ ou número
                            match = re.match(r"^(.+?)\s+(R?\$?\s*[\d., ]+)$", linha)
                            if match:
                                desc = match.group(1).strip()
                                val = parse_valor_br(match.group(2))
                            else:
                                erros += 1
                                continue
                        
                        if desc:
                            # Verifica Idempotência com Fuzzy Match
                            is_dupe = False
                            for idx, e_t in enumerate(buffer_trans):
                                if val == e_t["Valor"] and is_similar(desc, e_t["Descricao"], threshold=0.80):
                                    is_dupe = True
                                    buffer_trans.pop(idx)
                                    break
                                    
                            if is_dupe:
                                ignorados.append({"Descricao": desc, "Valor": val, "Cartao": cartao_limpo})
                            else:
                                novos.append({"Descricao": desc, "Valor": val, "Cartao": cartao_limpo})
    
                    if novos or ignorados:
                        if novos:
                            st.session_state["lote_pendente"] = novos
                        if ignorados:
                            st.session_state["lote_ignorados"] = ignorados
                        if erros:
                            st.session_state["lote_erros"] = erros
                        st.rerun()
                    else:
                        st.error("Nenhum lançamento válido encontrado. Verifique o formato.")
            else:
                if st.button("🤖 Ler Imagem Fatura e Classificar", use_container_width=True, key="importar_lote_img", type="primary"):
                    if not imagem_lote:
                        st.warning("Faça o upload de uma imagem primeiro.")
                    elif not gemini_client:
                        st.error("Chave de API do Gemini não configurada.")
                    else:
                        with st.spinner("Analisando faturas com Gemini Vision (isso leva ~10 a 15 segundos)..."):
                            import PIL.Image
                            try:
                                img = PIL.Image.open(imagem_lote)
                                prompt_img = """Você é um extrator de dados financeiros impiedosamente preciso.
    Leia a imagem anexada (fatura de cartão) e extraia TODAS as transações de compra.
    Pule tudo que não for compra explícita.

    [REGRA DE TITULAR E CARTÃO]
    Faturas bancárias geralmente dividem os blocos por titular. Ex: 'Final XXXX - NOME DO TITULAR'.
    Você deve cruzar os dados visuais e injetar o número do CARTÃO (os 4 dígitos finais) e o TITULAR correto em cada transação lida naquele bloco.
    Se não encontrar o nome do titular exposto no cabeçalho do bloco, use "Principal".
    Extraia nas transações apenas dia e mês (ex: 12/02), eliminando o ano.
    Extraia a data agregada (ex: 12/02) DENTRO DA DESCRICAO para ficar "12/02 DESCRICAO".

    Sua resposta DEVE ser um array JSON validado ESTRITO (sem nenhuma outra palavra, e sem a crase de markdown ```json). O output esperado é uma lista pura como:
    [
      {
    "Descricao": "12/02 NOME ESTABELECIMENTO",
    "Valor": 73.89,
    "Cartao": "1234",
    "Titular": "NOME TITULAR"
      }
    ]"""
                                response = gemini_client.models.generate_content(
                                    model=GEMINI_VISION_MODEL,
                                    contents=[prompt_img, img]
                                )
                                raw_json = response.text.strip()
                                if raw_json.startswith("```json"):
                                    raw_json = raw_json[7:-3]
                                elif raw_json.startswith("```"):
                                    raw_json = raw_json[3:-3]
                                raw_json = raw_json.strip()
                                
                                transacoes_img = json.loads(raw_json)
                                
                                if not transacoes_img:
                                    st.warning("O Gemini achou 0 transações na imagem.")
                                else:
                                    trans_img = transacoes_img
                                    novos = []
                                    ignorados = []
                                    
                                    # Pre-load dos dois bancos de dados para verificar idempotência
                                    trans_db = {
                                        "Principal": data_service.get_transacoes_data("Principal"),
                                        "Dependente": data_service.get_transacoes_data("Dependente")
                                    }
                                    
                                    buffer_trans = {"Principal": [], "Dependente": []}
                                    for perf in ["Principal", "Dependente"]:
                                        todas_trans_mes_lote = trans_db.get(perf, {}).get(mes_trans, [])
                                        buffer_trans[perf] = [dict(t) for t in todas_trans_mes_lote]
                                    
                                    for t in trans_img:
                                        tit = t.get("Titular", "Sistema")
                                        
                                        if "LAR" in tit.upper() or "DEP" in tit.upper():
                                            dest_profile = "Dependente"
                                        else:
                                            dest_profile = "Principal"
                                            
                                        t['dest_profile'] = dest_profile
                                        t['is_dupe'] = False
    
                                    def process_idempotency_pass(trans_lista, buffers, cond_match_func):
                                        for t in trans_lista:
                                            if t.get('is_dupe') or t.get('dest_profile', '').startswith('Ign'):
                                                continue
                                                
                                            c = str(t.get("Cartao", "")).strip()
                                            c = c.zfill(4) if c.isdigit() else c
                                            d = str(t.get("Descricao", "")).strip()
                                            v = float(t.get("Valor", 0))
                                            
                                            prof = t['dest_profile']
                                            
                                            for idx, e_t in enumerate(buffers[prof]):
                                                e_c = str(e_t.get("Cartao", "")).strip()
                                                e_c = e_c.zfill(4) if e_c.isdigit() else e_c
                                                e_v = float(e_t.get("Valor", 0))
                                                e_d = str(e_t.get("Descricao", "")).strip()
                                                
                                                if c == e_c:
                                                    similarity = difflib.SequenceMatcher(None, normalize_text(d), normalize_text(e_d)).ratio()
                                                    price_diff = abs(v - e_v)
                                                    if cond_match_func(similarity, price_diff):
                                                        t['is_dupe'] = True
                                                        buffers[prof].pop(idx)
                                                        break
    
                                    process_idempotency_pass(trans_img, buffer_trans, lambda s, pd: s == 1.0 and pd == 0)
                                    process_idempotency_pass(trans_img, buffer_trans, lambda s, pd: s >= 0.80 and pd == 0)
                                    process_idempotency_pass(trans_img, buffer_trans, lambda s, pd: s >= 0.90 and pd <= 0.50)
    
                                    for t in trans_img:
                                        if 'dest_profile' not in t: continue
                                        
                                        c = str(t.get("Cartao", "")).strip()
                                        c = c.zfill(4) if c.isdigit() else c
                                        d = str(t.get("Descricao", "")).strip()
                                        v = float(t.get("Valor", 0))
                                        dest = t['dest_profile']
                                        tit = t.get("Titular", "Sistema")
                                        
                                        if t['is_dupe']:
                                            ignorados.append({"Descricao": d, "Valor": v, "Cartao": c, "Perfil": dest, "Titular": tit})
                                        else:
                                            novos.append({"Descricao": d, "Valor": v, "Cartao": c, "Perfil": dest, "Titular": tit})
                                            
                                    if novos:      st.session_state["lote_pendente"] = novos
                                    if ignorados:  st.session_state["lote_ignorados"] = ignorados
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao processar imagem (certifique-se de que é nítida): {e}")
    
        else:
            st.markdown("### 🤖 Preview e Classificação")
            pendentes = st.session_state.get("lote_pendente", [])
            ignorados = st.session_state.get("lote_ignorados", [])
            erros_count = st.session_state.get("lote_erros", 0)
            
            if ignorados:
                with st.expander(f"⚠️ {len(ignorados)} lançamentos ignorados (Duplicidade detectada)", expanded=False):
                    st.info("O sistema detectou que essas exatas transações já estavam cadastradas no mês para este cartão, ignorando-as para evitar duplicidade.")
                    for t in ignorados:
                        cart_str = f" | 💳 {t.get('Cartao', '')}"
                        tit_str = f" | 👤 {t.get('Titular', '')}" if t.get('Titular') else ""
                        st.markdown(f"- **{t['Descricao']}** (R$ {t['Valor']}){cart_str}{tit_str}")
                        
            if not pendentes:
                st.warning("Todas as transações coladas já existiam no banco de dados. Nenhuma transação nova a ser adicionada.")
                if st.button("Limpar Importação", key="clear_empty_lote"):
                    if "lote_ignorados" in st.session_state: del st.session_state["lote_ignorados"]
                    if "lote_erros" in st.session_state: del st.session_state["lote_erros"]
                    if "lote_pendente" in st.session_state: del st.session_state["lote_pendente"]
                    st.session_state["clear_lote"] = True
                    st.rerun()
                st.stop()
    
            if "lote_classificado" not in st.session_state:
                if gemini_client:
                    with st.spinner("Classificando transações com Gemini..."):
                        prompt = "Classifique cada transação abaixo em uma das categorias: Alimentação, Supermercado, Transporte, Saúde, Assinatura, Lazer, Pet, Compras, Combustível, Casa, Outros. Responda APENAS em JSON no formato: [{\"idx\": <indice_inteiro>, \"categoria\": \"<categoria>\"}]\n\n"
                        
                        regras_ia = cfg_raw.get("Regras_IA", "").strip() if cfg_raw else ""
                        if regras_ia:
                            prompt += f"Regras Específicas do Usuário (Siga estritamente):\n{regras_ia}\n\n"
                            
                        prompt += "Transações:\n"
                        for i, t in enumerate(pendentes):
                            prompt += f"{i}. {t['Descricao']} - R$ {t['Valor']}\n"
                        
                        try:
                            response = gemini_client.models.generate_content(
                                model=GEMINI_MODEL,
                                contents=prompt,
                            )
                            raw_json = response.text.strip()
                            if raw_json.startswith("```json"):
                                raw_json = raw_json[7:-3]
                            elif raw_json.startswith("```"):
                                raw_json = raw_json[3:-3]
                            classfs = json.loads(raw_json)
                            cmap = {c.get("idx"): c.get("categoria", "Outros") for c in classfs}
                            for i, t in enumerate(pendentes):
                                t["Categoria"] = cmap.get(i, "Outros")
                        except Exception as e:
                            st.error(f"Falha ao classificar com Gemini: {e}. Usando 'Outros'.")
                            for t in pendentes:
                                t["Categoria"] = "Outros"
                else:
                    for t in pendentes:
                        t["Categoria"] = "Outros"
                
                st.session_state["lote_classificado"] = True
                st.session_state["lote_pendente"] = pendentes
                st.rerun()
    
            df_pend = pd.DataFrame(pendentes)
            
            # Se for lote de texto, o Perfil é o atual forçado
            if "Perfil" not in df_pend.columns:
                df_pend["Perfil"] = perfil_ativo
                
            edited_pend = st.data_editor(
                df_pend,
                use_container_width=True,
                column_config={
                    "Perfil": st.column_config.SelectboxColumn("Destino", options=["Principal", "Dependente"], required=True),
                    "Categoria": st.column_config.SelectboxColumn("Categoria", options=["Alimentação", "Supermercado", "Transporte", "Saúde", "Assinatura", "Lazer", "Pet", "Compras", "Combustível", "Casa", "Outros"])
                },
                key="editor_pendentes"
            )
    
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar e Salvar Lote", type="primary", use_container_width=True):
                importadas = {"Principal": 0, "Dependente": 0}
                
                # Agrupar transações por perfil
                trans_por_perfil = {"Principal": [], "Dependente": []}
                for row in edited_pend.to_dict(orient="records"):
                    p_dest = row.pop("Perfil", perfil_ativo)
                    if p_dest not in trans_por_perfil:
                        p_dest = perfil_ativo
                    trans_por_perfil[p_dest].append(row)
                
                # Salvar transações em batch para cada perfil
                for perfil, transacoes in trans_por_perfil.items():
                    if transacoes:
                        data_service.add_transacoes_batch(perfil, mes_trans, transacoes)
                        importadas[perfil] = len(transacoes)
                    
                if importadas["Principal"] > 0 or importadas["Dependente"] > 0:
                    import datetime
                    agora = datetime.datetime.now().isoformat()
                    data_service.update_profile_config(perfil_ativo, {"Ultima_Importacao": agora})
                    # Atualizar session_state
                    if cfg_raw:
                        cfg_raw["Ultima_Importacao"] = agora
                        st.session_state["cfg_raw"] = cfg_raw
                
                msg = f"✅ Lote importado com sucesso: {importadas['Principal']} para o Principal e {importadas['Dependente']} para o Dependente!"
                if erros_count:
                    msg += f" ({erros_count} linhas de texto ignoradas por formato inválido)"
                st.session_state["lote_success_msg"] = msg
                
                del st.session_state["lote_pendente"]
                del st.session_state["lote_classificado"]
                if "lote_erros" in st.session_state:
                    del st.session_state["lote_erros"]
                if "lote_ignorados" in st.session_state:
                    del st.session_state["lote_ignorados"]
                st.session_state["clear_lote"] = True
                st.rerun()
                
            if c2.button("❌ Cancelar Importação", use_container_width=True):
                del st.session_state["lote_pendente"]
                if "lote_classificado" in st.session_state:
                    del st.session_state["lote_classificado"]
                if "lote_erros" in st.session_state:
                    del st.session_state["lote_erros"]
                if "lote_ignorados" in st.session_state:
                    del st.session_state["lote_ignorados"]
                st.session_state["clear_lote"] = True
                st.rerun()
    
        # ── Lançamentos (Transações) (Editor Manual) ──
        st.markdown("---")
        st.markdown('<p class="section-header">Editor Manual de Lançamentos</p>',
                    unsafe_allow_html=True)
    
        if mes_trans in transacoes_data and transacoes_data[mes_trans]:
            df_trans = pd.DataFrame(transacoes_data[mes_trans])
        else:
            df_trans = pd.DataFrame(columns=["Descricao", "Valor", "Cartao"])
    
        if df_trans.empty:
            df_trans = pd.DataFrame({"_id": pd.Series(dtype="int"),
                                     "Descricao": pd.Series(dtype="str"),
                                     "Categoria": pd.Series(dtype="str"),
                                     "Valor": pd.Series(dtype="float"),
                                     "Cartao": pd.Series(dtype="str")})
        else:
            df_trans["Valor"] = pd.to_numeric(df_trans["Valor"], errors="coerce").fillna(0.0)
            if "Categoria" not in df_trans.columns:
                df_trans["Categoria"] = "Outros"
            # Injeta ID temporário para rastrear a linha real do JSON, caso não exista
            if "_id" not in df_trans.columns:
                df_trans["_id"] = range(len(df_trans))
    
        # ---- Filtros Visuais ----
        col_busca_conf, col_filt_cat_conf = st.columns(2)
        with col_busca_conf:
            busca_conf = st.text_input("🔍 Buscar lançamento (Edição)", key="busca_conf_edit",
                                  placeholder="Ex: UBER, COBASI...")
        with col_filt_cat_conf:
            opcoes_cat_conf = sorted(df_trans["Categoria"].unique().tolist()) if not df_trans.empty else []
            filtro_cat_conf = st.multiselect("Filtrar por Categoria", options=opcoes_cat_conf, default=None, key="filtro_cat_conf_edit")
    
        df_filtrado = df_trans.copy()
        if busca_conf and busca_conf.strip():
            mask_text = df_filtrado["Descricao"].str.contains(busca_conf.strip(), case=False, na=False)
            df_filtrado = df_filtrado[mask_text]
            
        if filtro_cat_conf:
            df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_cat_conf)]
    
        edited_trans = st.data_editor(
            df_filtrado,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "_id": None, # Esconde o ID interno do usuário
                "Descricao": st.column_config.TextColumn("Descrição", width="medium"),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=["Alimentação", "Supermercado", "Transporte", "Saúde", "Assinatura", "Lazer", "Pet", "Compras", "Combustível", "Casa", "Outros", "Crédito/Estorno"]),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f", min_value=0.0),
                "Cartao": st.column_config.TextColumn("Cartão (ex: 1234, Nubank)"),
            },
            key=f"editor_trans_{mes_trans}",
        )
    
        col_sav1, col_sav2 = st.columns(2)
        with col_sav1:
            if st.button(f"💾 Salvar Lançamentos", use_container_width=True, key="save_trans", type="primary"):
                # O botão deve fundir os dados editados com os originais preservando quem estava oculto pelo filtro
                clean_edited = edited_trans.dropna(subset=["Descricao"]).copy()
                clean_edited["Valor"] = pd.to_numeric(clean_edited["Valor"], errors="coerce").fillna(0.0)
                
                # Identifica os IDs originais que estavam visíveis durante a edição
                visible_ids_filtered = df_filtrado["_id"].dropna().tolist()
                
                ids_mantidos = clean_edited["_id"].dropna().tolist()
                ids_deletados = [vid for vid in visible_ids_filtered if vid not in ids_mantidos]
                
                linhas_finais = []
                
                # 1. Varre o df original iterando nos IDs e checando as deleções/edições
                for _, row in df_trans.iterrows():
                    row_id = row["_id"]
                    if pd.notna(row_id):
                        if row_id in ids_deletados:
                            continue # Usuário deletou esta linha visível
                        elif row_id in ids_mantidos:
                            # Usuário editou ou manteve, puxa os dados do clean_edited
                            nova_row = clean_edited[clean_edited["_id"] == row_id].iloc[0]
                            linhas_finais.append(nova_row.to_dict())
                        else:
                            # Estava filtrado (oculto), mantém original intacto
                            linhas_finais.append(row.to_dict())
                
                # 2. Adiciona as novas linhas geradas que não possuem "_id" ainda (NaN)
                novas_linhas = clean_edited[clean_edited["_id"].isna()]
                for _, row in novas_linhas.iterrows():
                    linhas_finais.append(row.to_dict())
                
                # Remove o campo auxiliar "_id" do payload final
                payload = []
                for ln in linhas_finais:
                    ln.pop("_id", None)
                    payload.append(ln)
    
                transacoes_data[mes_trans] = payload
                data_service.save_transacoes(perfil_ativo, mes_trans, payload)
                st.success(f"Lançamentos de {mes_trans} salvos!")
                time.sleep(1)
                st.rerun()
    
        with col_sav2:
            if gemini_client:
                if st.button(f"🤖 Auto-Classificar Mês", use_container_width=True, key="auto_class_trans"):
                    with st.spinner(f"Classificando com IA..."):
                        todas_trans_class = transacoes_data.get(mes_trans, [])
                        if todas_trans_class:
                            _KW_CREDITO = {"IOF", "ESTORNO", "DEVOLUCAO", "DEVOL", "CASHBACK",
                                           "REEMBOLSO", "CANCELAMENTO", "CANCELAM", "CREDITO"}
                            # Créditos por Tipo ou por palavra-chave recebem categoria fixa
                            # normalize_text remove acentos e espaços — ex: "CRÉDITO" → "CREDITO"
                            for t in todas_trans_class:
                                desc_norm = normalize_text(str(t.get("Descricao", "")))
                                if t.get("Tipo") == "credito" or any(kw in desc_norm for kw in _KW_CREDITO):
                                    t["Tipo"] = "credito"
                                    t["Categoria"] = "Crédito/Estorno"

                            # Remove débitos duplicados que são versão antiga de um crédito
                            # (ex: IOF CAIXA importado como débito antes da correção do OCR)
                            creditos = [t for t in todas_trans_class if t.get("Tipo") == "credito"]
                            indices_obsoletos = set()
                            for i, td in enumerate(todas_trans_class):
                                if td.get("Tipo") != "debito":
                                    continue
                                d_norm = normalize_text(str(td.get("Descricao", "")))
                                v_d = float(td.get("Valor", 0))
                                for tc in creditos:
                                    c_norm = normalize_text(str(tc.get("Descricao", "")))
                                    v_c = float(tc.get("Valor", 0))
                                    sim = difflib.SequenceMatcher(None, d_norm, c_norm).ratio()
                                    if sim >= 0.70 and abs(v_d - v_c) < 0.01:
                                        indices_obsoletos.add(i)
                                        break
                            if indices_obsoletos:
                                todas_trans_class = [t for i, t in enumerate(todas_trans_class) if i not in indices_obsoletos]

                            debitos_class = [(i, t) for i, t in enumerate(todas_trans_class) if t.get("Tipo") != "credito"]

                            prompt = "Classifique cada transação abaixo em uma das categorias: Alimentação, Supermercado, Transporte, Saúde, Assinatura, Lazer, Pet, Compras, Combustível, Casa, Outros. Responda APENAS em JSON no formato: [{\"idx\": <indice_inteiro>, \"categoria\": \"<categoria>\"}]\n\n"

                            regras_ia = cfg_raw.get("Regras_IA", "").strip() if cfg_raw else ""
                            if regras_ia:
                                prompt += f"Regras Específicas do Usuário (Siga estritamente):\n{regras_ia}\n\n"

                            prompt += "Transações:\n"
                            for seq, (i, t) in enumerate(debitos_class):
                                prompt += f"{seq}. {t.get('Descricao', '')} - R$ {t.get('Valor', 0)}\n"

                            try:
                                if debitos_class:
                                    response = gemini_client.models.generate_content(
                                        model=GEMINI_MODEL,
                                        contents=prompt,
                                    )
                                    raw_json = response.text.strip()
                                    if raw_json.startswith("```json"):
                                        raw_json = raw_json[7:-3]
                                    elif raw_json.startswith("```"):
                                        raw_json = raw_json[3:-3]
                                    classfs = json.loads(raw_json)
                                    cmap = {c.get("idx"): c.get("categoria", "Outros") for c in classfs}

                                    for seq, (i, t) in enumerate(debitos_class):
                                        t["Categoria"] = cmap.get(seq, "Outros")
                                    
                                transacoes_data[mes_trans] = todas_trans_class
                                data_service.save_transacoes(perfil_ativo, mes_trans, todas_trans_class)
                                st.success("Atualizado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro na classificação IA: {e}")
                        else:
                            st.info("Nenhuma transação para classificar.")
    
    else:
        st.info("Nenhum mês cadastrado. Crie um mês abaixo.")
    
    # ── Instruções Personalizadas para IA ──
    st.markdown("---")
    st.markdown('<p class="section-header">🤖 Instruções Personalizadas para IA</p>', unsafe_allow_html=True)
    st.write("Ensine a Inteligência Artificial a classificar transações específicas de acordo com seus hábitos.")
    
    regras_atuais = cfg_raw.get("Regras_IA", "") if cfg_raw else ""
    novas_regras = st.text_area(
        "Suas Regras (Ex: BESSA BRASIL é Alimentação; Uber no FDS é Lazer):",
        value=regras_atuais,
        height=150,
        help="Escreva as regras em linguagem natural. A IA lerá essas instruções antes de classificar suas faturas."
    )
    
    if st.button("💾 Salvar Regras da IA", use_container_width=True):
        data_service.update_profile_config(perfil_ativo, {"Regras_IA": novas_regras.strip()})
        # Atualizar session_state
        if cfg_raw:
            cfg_raw["Regras_IA"] = novas_regras.strip()
            st.session_state["cfg_raw"] = cfg_raw
        st.success("Regras salvas e enviadas para a Inteligência Artificial!")
        time.sleep(1)
        st.rerun()
    
    # ── Gastos Fixos Mensais ──
    st.markdown("---")
    st.markdown('<p class="section-header">Gastos Fixos Mensais</p>', unsafe_allow_html=True)
    
    meses_config = sorted(set(list(mensal_data.keys()) + list(transacoes_data.keys())))
    
    if meses_config:
        mes_edit = st.selectbox("Selecione o mês para editar fixos", meses_config,
                                key="config_mes_edit")
    
        if mes_edit in mensal_data and mensal_data[mes_edit]:
            df_edit = pd.DataFrame(mensal_data[mes_edit])
        else:
            df_edit = pd.DataFrame(columns=["Descricao_Fatura", "Valor", "Tipo"])
    
        if df_edit.empty:
            df_edit = pd.DataFrame({"Descricao_Fatura": pd.Series(dtype="str"),
                                    "Valor": pd.Series(dtype="float"),
                                    "Tipo": pd.Series(dtype="str")})
        else:
            df_edit["Valor"] = pd.to_numeric(df_edit["Valor"], errors="coerce").fillna(0.0)
    
        edited_fixos = st.data_editor(
            df_edit,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Descricao_Fatura": st.column_config.TextColumn("Descrição", width="medium"),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f", min_value=0.0),
                "Tipo": st.column_config.SelectboxColumn("Tipo",
                    options=["Nao_Cartao", "Cartao", "Extra"], default="Nao_Cartao"),
            },
            key=f"editor_fixos_{mes_edit}",
        )
    
        if st.button(f"💾 Salvar Fixos — {mes_edit}", use_container_width=True, key="save_mensal"):
            clean = edited_fixos.dropna(subset=["Descricao_Fatura"]).copy()
            clean["Valor"] = pd.to_numeric(clean["Valor"], errors="coerce").fillna(0.0)
            mensal_data[mes_edit] = clean.to_dict(orient="records")
            data_service.save_gastos_fixos(perfil_ativo, mes_edit, mensal_data[mes_edit])
            st.success(f"Fixos de {mes_edit} salvos!")
            st.rerun()
    else:
        st.info("Nenhum mês cadastrado. Crie um mês abaixo.")
    
    # ── Criar Novo Mês ──
    st.markdown("---")
    st.markdown('<p class="section-header">Criar Novo Mês</p>', unsafe_allow_html=True)
    
    # Limpar campo se flag ativa
    if st.session_state.get("clear_novo_mes"):
        st.session_state["novo_mes"] = ""
        del st.session_state["clear_novo_mes"]
    
    # Mostrar mensagem de sucesso
    if st.session_state.get("novo_mes_success"):
        st.success(st.session_state.pop("novo_mes_success"))
    
    col_nm1, col_nm2 = st.columns([3, 1])
    with col_nm1:
        novo_mes = st.text_input("Nome do mês (ex: Abril 25)", key="novo_mes")
    with col_nm2:
        st.markdown("<br>", unsafe_allow_html=True)
    
    # B6: Copiar fixos do mês anterior
    copiar_fixos = st.checkbox("📋 Copiar gastos fixos do mês anterior", value=True, key="copiar_fixos")
    
    if st.button("➕ Criar Mês", use_container_width=True):
        if novo_mes and novo_mes.strip():
            nome = novo_mes.strip()
            if nome not in transacoes_data:
                transacoes_data[nome] = []
                data_service.create_mes(perfil_ativo, nome)
            if nome not in mensal_data:
                # B6: copiar fixos do último mês se checkbox ativo
                if copiar_fixos and all_meses:
                    ultimo_mes = all_meses[-1]
                    mensal_data[nome] = list(mensal_data.get(ultimo_mes, []))
                else:
                    mensal_data[nome] = []
                data_service.save_gastos_fixos(perfil_ativo, nome, mensal_data[nome])
            st.session_state["novo_mes_success"] = f'Mês "{nome}" criado com sucesso!'
            st.session_state["clear_novo_mes"] = True
            st.rerun()
        else:
            st.warning("Informe o nome do mês.")
    
    # ── Excluir Mês ──
    st.markdown("---")
    st.markdown('<p class="section-header">Excluir Mês</p>', unsafe_allow_html=True)
    
    meses_excluir = sorted(set(list(mensal_data.keys()) + list(transacoes_data.keys())), key=mes_sort_key)
    
    if meses_excluir:
        # Mostrar mensagem de sucesso
        if st.session_state.get("excluir_mes_success"):
            st.success(st.session_state.pop("excluir_mes_success"))
    
        mes_del = st.selectbox("Selecione o mês para excluir", meses_excluir, key="mes_excluir")
    
        if st.button(f"🗑️ Excluir mês — {mes_del}", use_container_width=True, type="primary"):
            if mes_del in transacoes_data:
                del transacoes_data[mes_del]
                data_service.delete_transacoes_mes(perfil_ativo, mes_del)
            if mes_del in mensal_data:
                del mensal_data[mes_del]
                data_service.delete_gastos_fixos_mes(perfil_ativo, mes_del)
            st.session_state["excluir_mes_success"] = f'Mês "{mes_del}" excluído com sucesso!'
            st.rerun()
    else:
        st.info("Nenhum mês para excluir.")
    
    # ── Parâmetros Globais ──
    st.markdown("---")
    st.markdown('<p class="section-header">Parâmetros Globais do Sistema</p>',
                unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        new_receita = st.number_input("Receita Base (R$)",
                                      value=cfg["Receita_Base"], step=500.0, format="%.2f")
        new_teto = st.number_input("Teto de Gastos (R$)",
                                   value=cfg["Teto_Gastos"], step=500.0, format="%.2f")
        
        model_options = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-flash-lite-preview", "gemini-3.1-pro-preview"]
        default_idx = model_options.index(GEMINI_MODEL) if GEMINI_MODEL in model_options else 0
        new_model = st.selectbox("Modelo Padrão (Texto/Auto-Categorização)",
                                 options=model_options, index=default_idx)
                                 
    with col_b:
        new_meta = st.number_input("Meta de Aporte (R$)",
                                   value=cfg["Meta_Aporte"], step=500.0, format="%.2f")
        new_dia = st.number_input("Dia de Fechamento",
                                  value=int(cfg["Dia_Fechamento"]), min_value=1, max_value=31, step=1)
                                  
        default_vidx = model_options.index(GEMINI_VISION_MODEL) if GEMINI_VISION_MODEL in model_options else 0
        new_vmodel = st.selectbox("Modelo de Imagem (Leitura de Faturas)",
                                 options=model_options, index=default_vidx)
    
    if st.button("💾 Salvar Parâmetros Globais", use_container_width=True):
        cfg["Receita_Base"] = new_receita
        cfg["Meta_Aporte"] = new_meta
        cfg["Teto_Gastos"] = new_teto
        cfg["Dia_Fechamento"] = int(new_dia)
        cfg["Gemini_Model"] = new_model
        cfg["Gemini_Vision_Model"] = new_vmodel
        
        # Atualizar no Supabase
        data_service.update_profile_config(perfil_ativo, cfg)
        st.success("Parâmetros globais salvos!")
        st.rerun()

    # ═══════════════════════════════════════
    # ORÇAMENTO POR CATEGORIA
    # ═══════════════════════════════════════
    st.markdown("---")
    st.markdown('<p class="section-header">🎯 Limites por Categoria</p>',
                unsafe_allow_html=True)
    st.caption("Defina tetos de gastos por categoria. Categorias sem limite usarão a média histórica como referência.")

    # Carregar limites atuais
    try:
        current_budgets = data_service.get_category_budgets(perfil_ativo)
    except Exception:
        current_budgets = {}

    # Coletar todas as categorias em uso
    all_cats = set()
    for mes_key, ops in transacoes_data.items():
        for t in ops:
            cat = t.get("Categoria", "")
            if cat and cat != "Outros":
                all_cats.add(cat)
    all_cats = sorted(all_cats)

    if all_cats:
        # Editor de limites
        edited_budgets = {}
        cols_per_row = 3
        for i in range(0, len(all_cats), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, cat in enumerate(all_cats[i:i+cols_per_row]):
                with cols[j]:
                    val = current_budgets.get(cat, 0.0)
                    novo_val = st.number_input(
                        f"🏷️ {cat}",
                        min_value=0.0, value=float(val), step=50.0,
                        format="%.2f", key=f"cat_budget_{cat}",
                    )
                    if novo_val > 0:
                        edited_budgets[cat] = novo_val

        if st.button("💾 Salvar Limites por Categoria", use_container_width=True):
            try:
                data_service.save_category_budgets(perfil_ativo, edited_budgets)
                # Remover categorias que foram zeradas
                for cat in all_cats:
                    if cat not in edited_budgets and cat in current_budgets:
                        data_service.delete_category_budget(perfil_ativo, cat)
                st.success(f"Limites salvos para {len(edited_budgets)} categorias!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar limites: {e}")
    else:
        st.info("Importe transações primeiro para que as categorias apareçam aqui.")

    # ═══════════════════════════════════════
    # METAS DE LONGO PRAZO
    # ═══════════════════════════════════════
    st.markdown("---")
    st.markdown('<p class="section-header">🎯 Metas de Longo Prazo</p>',
                unsafe_allow_html=True)
    st.caption("Defina objetivos financeiros e acompanhe o progresso na aba Evolução Histórica.")

    # Carregar metas atuais
    try:
        goals = data_service.get_goals(perfil_ativo)
    except Exception:
        goals = []

    # Mostrar metas existentes
    if goals:
        for g in goals:
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.text(f"🎯 {g['titulo']:30s}  R$ {g['valor_alvo']:>12,.2f}  ({g['prazo_meses']} meses)")
            with col_del:
                if st.button("🗑️", key=f"del_goal_{g['id']}"):
                    try:
                        data_service.delete_goal(g["id"])
                        st.success(f"Meta '{g['titulo']}' removida.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # Formulário para nova meta
    with st.form("new_goal_form", clear_on_submit=True):
        st.markdown("**➕ Nova Meta**")
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            g_titulo = st.text_input("Título", placeholder="Ex: Reserva emergência")
        with gc2:
            g_valor = st.number_input("Valor alvo (R$)", min_value=0.0, step=1000.0, format="%.2f")
        with gc3:
            g_prazo = st.number_input("Prazo (meses)", min_value=1, max_value=120, value=12)

        if st.form_submit_button("💾 Criar Meta", use_container_width=True):
            if g_titulo and g_valor > 0:
                try:
                    data_service.save_goal(perfil_ativo, {
                        "titulo": g_titulo,
                        "valor_alvo": g_valor,
                        "prazo_meses": g_prazo,
                    })
                    st.success(f"Meta '{g_titulo}' criada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            else:
                st.warning("Preencha título e valor.")









