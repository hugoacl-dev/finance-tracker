"""
Implementação Supabase do DataService.
Conecta ao PostgreSQL via Supabase Python Client.
"""
from supabase import create_client, Client
from typing import List, Dict, Optional
import streamlit as st
from services.data_service import DataService


class SupabaseAdapter(DataService):
    """Implementação Supabase do DataService"""
    
    def __init__(self):
        """Inicializa conexão com Supabase"""
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        self.client: Client = create_client(url, key)
        self._profile_cache = {}
    
    def _get_profile_id(self, profile_name: str) -> str:
        """Helper para obter ID do perfil com cache"""
        if profile_name in self._profile_cache:
            return self._profile_cache[profile_name]["id"]
        
        result = self.client.table("profiles").select("id").eq("name", profile_name).execute()
        if not result.data:
            raise ValueError(f"Perfil '{profile_name}' não encontrado no banco de dados")
        
        profile_id = result.data[0]["id"]
        self._profile_cache[profile_name] = {"id": profile_id}
        return profile_id
    
    # ===== PROFILES =====
    
    def get_profile_config(self, profile_name: str) -> Dict:
        """Retorna configuração de um perfil"""
        if profile_name in self._profile_cache and "config" in self._profile_cache[profile_name]:
            return self._profile_cache[profile_name]["config"]
        
        result = self.client.table("profiles").select("*").eq("name", profile_name).execute()
        
        if not result.data:
            # Inserir perfil apenas se realmente não existe — NÃO faz update para evitar
            # sobrescrever dados em caso de falha transiente de conexão
            from core.config import DEFAULTS
            try:
                self.client.table("profiles").insert({"name": profile_name, **{
                    "receita_base": DEFAULTS.get("Receita_Base"),
                    "meta_aporte": DEFAULTS.get("Meta_Aporte"),
                    "teto_gastos": DEFAULTS.get("Teto_Gastos"),
                    "dia_fechamento": DEFAULTS.get("Dia_Fechamento"),
                    "gemini_model": DEFAULTS.get("Gemini_Model"),
                    "gemini_vision_model": DEFAULTS.get("Gemini_Vision_Model"),
                }}).execute()
            except Exception:
                pass  # Ignorar se já existe (race condition)
            return DEFAULTS.copy()
        
        config = result.data[0]
        profile_id = config["id"]  # Salvar ID antes de remover
        
        # Remover campos internos do banco
        config.pop("id", None)
        config.pop("created_at", None)
        config.pop("updated_at", None)
        config.pop("name", None)
        
        # Converter snake_case para PascalCase (compatibilidade com código existente)
        config_formatted = {
            "Receita_Base": config.get("receita_base"),
            "Meta_Aporte": config.get("meta_aporte"),
            "Teto_Gastos": config.get("teto_gastos"),
            "Dia_Fechamento": config.get("dia_fechamento"),
            "Gemini_Model": config.get("gemini_model"),
            "Gemini_Vision_Model": config.get("gemini_vision_model"),
            "Regras_IA": config.get("regras_ia"),
            "Ultima_Importacao": config.get("ultima_importacao"),
            "Cartoes_Aceitos": config.get("cartoes_aceitos"),
            "Cartoes_Excluidos": config.get("cartoes_excluidos"),
        }
        # Remove chaves cujo valor é None para não poluir o dict
        config_formatted = {k: v for k, v in config_formatted.items() if v is not None}
        
        self._profile_cache[profile_name] = {"id": profile_id, "config": config_formatted}
        return config_formatted
    
    def update_profile_config(self, profile_name: str, config: Dict) -> None:
        """Atualiza apenas os campos presentes em config para o perfil"""
        # Converter formato de data brasileiro para ISO se necessário
        ultima_importacao = config.get("Ultima_Importacao")
        if ultima_importacao and isinstance(ultima_importacao, str):
            try:
                from datetime import datetime
                if " às " in ultima_importacao:
                    dt = datetime.strptime(ultima_importacao, "%d/%m/%Y às %H:%M:%S")
                    ultima_importacao = dt.isoformat()
            except:
                ultima_importacao = None
        
        # Mapeamento PascalCase -> snake_case (somente campos presentes no dict)
        field_map = {
            "Receita_Base":       "receita_base",
            "Meta_Aporte":        "meta_aporte",
            "Teto_Gastos":        "teto_gastos",
            "Dia_Fechamento":     "dia_fechamento",
            "Gemini_Model":       "gemini_model",
            "Gemini_Vision_Model":"gemini_vision_model",
            "Regras_IA":          "regras_ia",
            "Ultima_Importacao":  "ultima_importacao",
            "Cartoes_Aceitos":    "cartoes_aceitos",
            "Cartoes_Excluidos":  "cartoes_excluidos",
        }
        
        # Constrói payload apenas com os campos que vieram no config (update seletivo)
        db_updates = {}
        for pascal_key, snake_key in field_map.items():
            if pascal_key not in config:
                continue  # Não tocar em campos que não foram passados
            value = ultima_importacao if pascal_key == "Ultima_Importacao" else config[pascal_key]
            if value is not None:
                db_updates[snake_key] = value
        
        if not db_updates:
            return
        
        # Tenta UPDATE primeiro; se não existir, faz INSERT com defaults
        result = self.client.table("profiles").update(db_updates).eq("name", profile_name).execute()
        if not result.data:
            # Perfil não existe ainda — cria com os campos fornecidos
            from core.config import DEFAULTS
            insert_payload = {"name": profile_name}
            for pascal_key, snake_key in field_map.items():
                default_val = DEFAULTS.get(pascal_key)
                saved_val = db_updates.get(snake_key, default_val)
                if saved_val is not None:
                    insert_payload[snake_key] = saved_val
            try:
                self.client.table("profiles").insert(insert_payload).execute()
            except Exception:
                pass
        
        # Limpar cache do perfil para forçar releitura do banco
        if profile_name in self._profile_cache:
            self._profile_cache[profile_name].pop("config", None)
    
    # ===== GASTOS FIXOS =====
    
    def get_gastos_fixos(self, profile_name: str, mes: str) -> List[Dict]:
        """Retorna gastos fixos de um perfil/mês"""
        profile_id = self._get_profile_id(profile_name)
        
        result = self.client.table("gastos_fixos")\
            .select("*")\
            .eq("profile_id", profile_id)\
            .eq("mes", mes)\
            .execute()
        
        # Remover campos internos e converter para formato esperado
        gastos = []
        for g in result.data:
            gasto = {
                "Descricao_Fatura": g.get("descricao_fatura"),
                "Valor": float(g.get("valor", 0)),
                "Tipo": g.get("tipo"),
                "Status_Conciliacao": g.get("status_conciliacao"),
            }
            gastos.append(gasto)
        
        return gastos
    
    def save_gastos_fixos(self, profile_name: str, mes: str, gastos: List[Dict]) -> None:
        """Salva gastos fixos (substitui todos do mês)"""
        profile_id = self._get_profile_id(profile_name)
        
        # Delete existentes
        self.delete_gastos_fixos_mes(profile_name, mes)
        
        # Insert novos
        if gastos:
            import math
            records = []
            for gasto in gastos:
                # Validar e limpar valor
                valor = gasto.get("Valor", 0)
                try:
                    valor = float(valor)
                    if math.isnan(valor) or math.isinf(valor):
                        valor = 0.0
                except (ValueError, TypeError):
                    valor = 0.0
                
                record = {
                    "profile_id": str(profile_id),  # Converter UUID para string
                    "mes": str(mes),
                    "descricao_fatura": str(gasto.get("Descricao_Fatura", "")),
                    "valor": valor,
                    "tipo": str(gasto.get("Tipo", "Nao_Cartao")),
                    "status_conciliacao": str(gasto.get("Status_Conciliacao", "")) if gasto.get("Status_Conciliacao") else None,
                }
                records.append(record)
            
            self.client.table("gastos_fixos").insert(records).execute()
    
    def delete_gastos_fixos_mes(self, profile_name: str, mes: str) -> None:
        """Deleta todos gastos fixos de um mês"""
        profile_id = self._get_profile_id(profile_name)
        
        self.client.table("gastos_fixos")\
            .delete()\
            .eq("profile_id", profile_id)\
            .eq("mes", mes)\
            .execute()
    
    # ===== TRANSAÇÕES =====
    
    def get_transacoes(self, profile_name: str, mes: str) -> List[Dict]:
        """Retorna transações de um perfil/mês"""
        profile_id = self._get_profile_id(profile_name)
        
        result = self.client.table("transacoes")\
            .select("*")\
            .eq("profile_id", profile_id)\
            .eq("mes", mes)\
            .order("created_at", desc=False)\
            .execute()
        
        # Converter para formato esperado
        transacoes = []
        for t in result.data:
            trans = {
                "Descricao": t.get("descricao"),
                "Valor": float(t.get("valor", 0)),
                "Cartao": t.get("cartao"),
                "Titular": t.get("titular"),
                "Categoria": t.get("categoria"),
            }
            transacoes.append(trans)
        
        return transacoes
    
    def add_transacao(self, profile_name: str, mes: str, transacao: Dict) -> str:
        """Adiciona uma transação e retorna o ID"""
        profile_id = self._get_profile_id(profile_name)
        
        record = {
            "profile_id": profile_id,
            "mes": mes,
            "descricao": transacao.get("Descricao"),
            "valor": float(transacao.get("Valor", 0)),
            "cartao": transacao.get("Cartao"),
            "titular": transacao.get("Titular", "Sistema"),
            "categoria": transacao.get("Categoria", "Outros"),
        }
        
        result = self.client.table("transacoes").insert(record).execute()
        return result.data[0]["id"]
    
    def add_transacoes_batch(self, profile_name: str, mes: str, transacoes: List[Dict]) -> List[str]:
        """Adiciona múltiplas transações em lote"""
        if not transacoes:
            return []
        
        profile_id = self._get_profile_id(profile_name)
        
        records = []
        for trans in transacoes:
            # Validar e limpar valor
            valor = trans.get("Valor", 0)
            try:
                valor = float(valor)
                # Verificar se é um número válido (não NaN, não Infinity)
                import math
                if math.isnan(valor) or math.isinf(valor):
                    valor = 0.0
            except (ValueError, TypeError):
                valor = 0.0
            
            record = {
                "profile_id": str(profile_id),  # Converter UUID para string
                "mes": str(mes),
                "descricao": str(trans.get("Descricao", "")),
                "valor": valor,
                "cartao": str(trans.get("Cartao", "")),
                "titular": str(trans.get("Titular", "Sistema")),
                "categoria": str(trans.get("Categoria", "Outros")),
            }
            records.append(record)
        
        result = self.client.table("transacoes").insert(records).execute()
        return [r["id"] for r in result.data]
    
    def update_transacao(self, transacao_id: str, updates: Dict) -> None:
        """Atualiza campos de uma transação"""
        db_updates = {}
        if "Descricao" in updates:
            db_updates["descricao"] = updates["Descricao"]
        if "Valor" in updates:
            db_updates["valor"] = float(updates["Valor"])
        if "Cartao" in updates:
            db_updates["cartao"] = updates["Cartao"]
        if "Titular" in updates:
            db_updates["titular"] = updates["Titular"]
        if "Categoria" in updates:
            db_updates["categoria"] = updates["Categoria"]
        
        self.client.table("transacoes")\
            .update(db_updates)\
            .eq("id", transacao_id)\
            .execute()
    
    def delete_transacao(self, transacao_id: str) -> None:
        """Deleta uma transação"""
        self.client.table("transacoes").delete().eq("id", transacao_id).execute()
    
    def save_transacoes(self, profile_name: str, mes: str, transacoes: List[Dict]) -> None:
        """Salva todas transações de um mês (substitui)"""
        # Delete existentes
        self.delete_transacoes_mes(profile_name, mes)
        
        # Insert novas
        if transacoes:
            self.add_transacoes_batch(profile_name, mes, transacoes)
    
    def delete_transacoes_mes(self, profile_name: str, mes: str) -> None:
        """Deleta todas transações de um mês"""
        profile_id = self._get_profile_id(profile_name)
        
        self.client.table("transacoes")\
            .delete()\
            .eq("profile_id", profile_id)\
            .eq("mes", mes)\
            .execute()
    
    def search_transacoes(self, profile_name: str, mes: str,
                         descricao: Optional[str] = None,
                         categorias: Optional[List[str]] = None,
                         cartao: Optional[str] = None) -> List[Dict]:
        """Busca transações com filtros"""
        profile_id = self._get_profile_id(profile_name)
        
        query = self.client.table("transacoes")\
            .select("*")\
            .eq("profile_id", profile_id)\
            .eq("mes", mes)
        
        if descricao:
            # Full-text search em português
            query = query.textSearch("descricao", f"'{descricao}'", config="portuguese")
        
        if categorias:
            query = query.in_("categoria", categorias)
        
        if cartao:
            query = query.eq("cartao", cartao)
        
        result = query.execute()
        
        # Converter para formato esperado
        transacoes = []
        for t in result.data:
            trans = {
                "Descricao": t.get("descricao"),
                "Valor": float(t.get("valor", 0)),
                "Cartao": t.get("cartao"),
                "Titular": t.get("titular"),
                "Categoria": t.get("categoria"),
            }
            transacoes.append(trans)
        
        return transacoes
    
    # ===== MESES =====
    
    def get_all_meses(self, profile_name: str) -> List[str]:
        """Retorna lista de todos os meses cadastrados"""
        profile_id = self._get_profile_id(profile_name)
        
        # Union de meses de gastos_fixos e transacoes
        fixos = self.client.table("gastos_fixos")\
            .select("mes")\
            .eq("profile_id", profile_id)\
            .execute()
        
        trans = self.client.table("transacoes")\
            .select("mes")\
            .eq("profile_id", profile_id)\
            .execute()
        
        meses = set()
        for r in fixos.data:
            meses.add(r["mes"])
        for r in trans.data:
            meses.add(r["mes"])
        
        return sorted(list(meses))
    
    def create_mes(self, profile_name: str, mes: str, 
                   copiar_fixos_de: Optional[str] = None) -> None:
        """Cria um novo mês, opcionalmente copiando fixos"""
        if copiar_fixos_de:
            # Copiar gastos fixos do mês anterior
            gastos_anteriores = self.get_gastos_fixos(profile_name, copiar_fixos_de)
            if gastos_anteriores:
                self.save_gastos_fixos(profile_name, mes, gastos_anteriores)
    
    def delete_mes(self, profile_name: str, mes: str) -> None:
        """Deleta um mês completo (fixos + transações)"""
        self.delete_gastos_fixos_mes(profile_name, mes)
        self.delete_transacoes_mes(profile_name, mes)
    
    # ===== DADOS AGREGADOS =====
    
    def get_mensal_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        """Retorna todos gastos fixos agrupados por mês"""
        profile_id = self._get_profile_id(profile_name)
        
        result = self.client.table("gastos_fixos")\
            .select("*")\
            .eq("profile_id", profile_id)\
            .execute()
        
        # Agrupar por mês
        mensal_data = {}
        for g in result.data:
            mes = g["mes"]
            if mes not in mensal_data:
                mensal_data[mes] = []
            
            gasto = {
                "Descricao_Fatura": g.get("descricao_fatura"),
                "Valor": float(g.get("valor", 0)),
                "Tipo": g.get("tipo"),
                "Status_Conciliacao": g.get("status_conciliacao"),
            }
            mensal_data[mes].append(gasto)
        
        return mensal_data
    
    def get_transacoes_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        """Retorna todas transações agrupadas por mês"""
        profile_id = self._get_profile_id(profile_name)
        
        result = self.client.table("transacoes")\
            .select("*")\
            .eq("profile_id", profile_id)\
            .order("created_at", desc=False)\
            .execute()
        
        # Agrupar por mês
        transacoes_data = {}
        for t in result.data:
            mes = t["mes"]
            if mes not in transacoes_data:
                transacoes_data[mes] = []
            
            trans = {
                "Descricao": t.get("descricao"),
                "Valor": float(t.get("valor", 0)),
                "Cartao": t.get("cartao"),
                "Titular": t.get("titular"),
                "Categoria": t.get("categoria"),
            }
            transacoes_data[mes].append(trans)
        
        return transacoes_data

    # ===== GOALS (Metas de Longo Prazo) =====

    def get_goals(self, profile_name: str) -> List[Dict]:
        """Retorna todas as metas do perfil."""
        profile_id = self._get_profile_id(profile_name)
        result = self.client.table("goals").select("*").eq("profile_id", profile_id).order("created_at").execute()
        goals = []
        for g in result.data:
            goals.append({
                "id": g["id"],
                "titulo": g.get("titulo", ""),
                "valor_alvo": float(g.get("valor_alvo", 0)),
                "prazo_meses": int(g.get("prazo_meses", 12)),
                "created_at": g.get("created_at"),
            })
        return goals

    def save_goal(self, profile_name: str, goal: Dict) -> str:
        """Cria ou atualiza uma meta. Retorna o ID."""
        profile_id = self._get_profile_id(profile_name)
        payload = {
            "profile_id": profile_id,
            "titulo": goal["titulo"],
            "valor_alvo": goal["valor_alvo"],
            "prazo_meses": goal.get("prazo_meses", 12),
        }
        if "id" in goal and goal["id"]:
            # Update
            result = self.client.table("goals").update(payload).eq("id", goal["id"]).execute()
            return goal["id"]
        else:
            # Insert
            result = self.client.table("goals").insert(payload).execute()
            return result.data[0]["id"] if result.data else ""

    def delete_goal(self, goal_id: str) -> None:
        """Deleta uma meta pelo ID."""
        self.client.table("goals").delete().eq("id", goal_id).execute()

    # ===== CATEGORY BUDGETS (Orçamento por Categoria) =====

    def get_category_budgets(self, profile_name: str) -> Dict[str, float]:
        """Retorna dict {categoria: limite} do perfil."""
        profile_id = self._get_profile_id(profile_name)
        result = self.client.table("category_budgets").select("categoria, limite").eq("profile_id", profile_id).execute()
        return {row["categoria"]: float(row["limite"]) for row in result.data}

    def save_category_budgets(self, profile_name: str, budgets: Dict[str, float]) -> None:
        """Salva limites por categoria (upsert)."""
        profile_id = self._get_profile_id(profile_name)
        for categoria, limite in budgets.items():
            payload = {
                "profile_id": profile_id,
                "categoria": categoria,
                "limite": limite,
            }
            self.client.table("category_budgets").upsert(
                payload, on_conflict="profile_id,categoria"
            ).execute()

    def delete_category_budget(self, profile_name: str, categoria: str) -> None:
        """Remove o limite de uma categoria."""
        profile_id = self._get_profile_id(profile_name)
        self.client.table("category_budgets").delete().eq(
            "profile_id", profile_id
        ).eq("categoria", categoria).execute()

