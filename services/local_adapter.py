"""
Adaptador local em memoria para desenvolvimento sem Supabase.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional
from uuid import uuid4

from core.config import DEFAULTS
from services.data_service import DataService


def _new_id() -> str:
    return uuid4().hex


class LocalDataService(DataService):
    """Implementacao local para validacao de UI quando nao ha credenciais."""

    mode = "local"

    def __init__(self):
        self._profiles: Dict[str, Dict] = {}
        self._mensal: Dict[str, Dict[str, List[Dict]]] = {}
        self._transacoes: Dict[str, Dict[str, List[Dict]]] = {}
        self._goals: Dict[str, List[Dict]] = {}
        self._budgets: Dict[str, Dict[str, float]] = {}
        self._bootstrap_demo_data()

    def _bootstrap_demo_data(self) -> None:
        self._profiles = {
            "Principal": {
                **DEFAULTS,
                "Receita_Base": 18500.0,
                "Meta_Aporte": 6500.0,
                "Teto_Gastos": 12000.0,
                "Dia_Fechamento": 21,
                "Gemini_Model": "gemini-2.5-flash",
                "Gemini_Vision_Model": "gemini-2.5-flash",
                "Regras_IA": "Classifique iFood e restaurantes como Alimentação. Foque em consistência de aporte.",
                "onboarding_done": True,
            },
            "Dependente": {
                **DEFAULTS,
                "Receita_Base": 9200.0,
                "Meta_Aporte": 2200.0,
                "Teto_Gastos": 6400.0,
                "Dia_Fechamento": 21,
                "Gemini_Model": "gemini-2.5-flash",
                "Gemini_Vision_Model": "gemini-2.5-flash",
                "Regras_IA": "",
                "onboarding_done": True,
            },
        }

        self._mensal = {
            "Principal": {
                "02/26": [
                    self._fixo("Aluguel", 3200.0, "Nao_Cartao"),
                    self._fixo("Internet Fibra", 129.9, "Nao_Cartao"),
                    self._fixo("Academia Prime", 189.9, "Cartao"),
                    self._fixo("Streaming Familia", 59.9, "Cartao"),
                    self._fixo("Seguro Auto", 420.0, "Extra"),
                ],
                "03/26": [
                    self._fixo("Aluguel", 3200.0, "Nao_Cartao"),
                    self._fixo("Internet Fibra", 129.9, "Nao_Cartao"),
                    self._fixo("Academia Prime", 189.9, "Cartao"),
                    self._fixo("Streaming Familia", 59.9, "Cartao"),
                    self._fixo("Curso Inglês", 249.9, "Cartao"),
                    self._fixo("Seguro Auto", 420.0, "Extra"),
                ],
                "04/26": [
                    self._fixo("Aluguel", 3200.0, "Nao_Cartao"),
                    self._fixo("Internet Fibra", 129.9, "Nao_Cartao"),
                    self._fixo("Academia Prime", 189.9, "Cartao"),
                    self._fixo("Streaming Familia", 59.9, "Cartao"),
                    self._fixo("Curso Inglês", 249.9, "Cartao"),
                    self._fixo("Seguro Auto", 420.0, "Extra"),
                ],
            },
            "Dependente": {
                "03/26": [
                    self._fixo("Aluguel", 1800.0, "Nao_Cartao"),
                    self._fixo("Internet Fibra", 99.9, "Nao_Cartao"),
                    self._fixo("Academia", 119.9, "Cartao"),
                ],
                "04/26": [
                    self._fixo("Aluguel", 1800.0, "Nao_Cartao"),
                    self._fixo("Internet Fibra", 99.9, "Nao_Cartao"),
                    self._fixo("Academia", 119.9, "Cartao"),
                ],
            },
        }

        self._transacoes = {
            "Principal": {
                "02/26": [
                    self._tx("02/02 Supermercado Bom Preco", 915.4, "5544", "Principal", "Supermercado"),
                    self._tx("05/02 Academia Prime", 189.9, "5544", "Principal", "Assinatura"),
                    self._tx("07/02 Uber", 82.4, "5544", "Principal", "Transporte"),
                    self._tx("10/02 Farmácia Vida", 114.3, "5544", "Principal", "Saúde"),
                    self._tx("13/02 Restaurante Porto", 162.8, "1122", "Principal", "Alimentação"),
                    self._tx("16/02 Pet Feliz", 138.9, "5544", "Principal", "Pet"),
                    self._tx("18/02 Cinema Recife", 88.0, "1122", "Principal", "Lazer"),
                    self._tx("21/02 Casa e Mesa", 224.0, "5544", "Principal", "Casa"),
                    self._tx("23/02 Posto BR", 286.0, "5544", "Principal", "Combustível"),
                    self._tx("24/02 Estorno Loja Centro", 54.9, "5544", "Principal", "Compras", "credito"),
                    self._tx("26/02 Streaming Familia", 59.9, "5544", "Principal", "Assinatura"),
                ],
                "03/26": [
                    self._tx("03/03 Supermercado Bom Preco", 1034.8, "5544", "Principal", "Supermercado"),
                    self._tx("05/03 Academia Prime", 189.9, "5544", "Principal", "Assinatura"),
                    self._tx("06/03 Uber", 94.2, "5544", "Principal", "Transporte"),
                    self._tx("09/03 Farmácia Vida", 132.4, "5544", "Principal", "Saúde"),
                    self._tx("10/03 Restaurante Porto", 186.0, "1122", "Principal", "Alimentação"),
                    self._tx("14/03 Pet Feliz", 148.9, "5544", "Principal", "Pet"),
                    self._tx("17/03 Cinema Recife", 92.0, "1122", "Principal", "Lazer"),
                    self._tx("19/03 Casa e Mesa", 265.0, "5544", "Principal", "Casa"),
                    self._tx("22/03 Posto BR", 310.0, "5544", "Principal", "Combustível"),
                    self._tx("24/03 Estorno Loja Centro", 69.9, "5544", "Principal", "Compras", "credito"),
                    self._tx("27/03 Streaming Familia", 59.9, "5544", "Principal", "Assinatura"),
                ],
                "04/26": [
                    self._tx("02/04 Supermercado Bom Preco", 1389.4, "5544", "Principal", "Supermercado"),
                    self._tx("04/04 Academia Prime", 189.9, "5544", "Principal", "Assinatura"),
                    self._tx("06/04 Uber", 121.0, "5544", "Principal", "Transporte"),
                    self._tx("08/04 iFood Noite", 178.2, "1122", "Principal", "Alimentação"),
                    self._tx("09/04 Consulta Clínica", 310.0, "5544", "Principal", "Saúde"),
                    self._tx("11/04 Shopping Casa", 410.0, "5544", "Principal", "Compras"),
                    self._tx("13/04 Mercado Pet", 96.0, "5544", "Principal", "Pet"),
                    self._tx("14/04 Streaming Familia", 59.9, "5544", "Principal", "Assinatura"),
                    self._tx("15/04 PIX Desconhecido", 149.0, "5544", "Principal", "Outros"),
                    self._tx("16/04 Estorno Taxa", 35.0, "5544", "Principal", "Outros", "credito"),
                ],
            },
            "Dependente": {
                "03/26": [
                    self._tx("04/03 Mercado Bairro", 420.0, "7788", "Dependente", "Supermercado"),
                    self._tx("08/03 Academia", 119.9, "7788", "Dependente", "Assinatura"),
                    self._tx("12/03 Uber", 56.0, "7788", "Dependente", "Transporte"),
                ],
                "04/26": [
                    self._tx("04/04 Mercado Bairro", 468.0, "7788", "Dependente", "Supermercado"),
                    self._tx("08/04 Academia", 119.9, "7788", "Dependente", "Assinatura"),
                    self._tx("12/04 Uber", 61.0, "7788", "Dependente", "Transporte"),
                    self._tx("14/04 Restaurante", 94.0, "7788", "Dependente", "Alimentação"),
                ],
            },
        }

        self._goals = {
            "Principal": [
                {"id": _new_id(), "titulo": "Reserva de Emergência", "valor_alvo": 60000.0, "prazo_meses": 18},
                {"id": _new_id(), "titulo": "Viagem Internacional", "valor_alvo": 18000.0, "prazo_meses": 12},
            ],
            "Dependente": [
                {"id": _new_id(), "titulo": "Reserva Inicial", "valor_alvo": 12000.0, "prazo_meses": 10},
            ],
        }

        self._budgets = {
            "Principal": {
                "Alimentação": 900.0,
                "Supermercado": 1200.0,
                "Transporte": 450.0,
                "Saúde": 550.0,
                "Assinatura": 300.0,
                "Lazer": 700.0,
                "Pet": 320.0,
                "Compras": 700.0,
                "Casa": 750.0,
                "Combustível": 350.0,
            },
            "Dependente": {
                "Alimentação": 500.0,
                "Supermercado": 700.0,
                "Transporte": 220.0,
                "Assinatura": 150.0,
            },
        }

    def _fixo(self, descricao: str, valor: float, tipo: str, status: str = "") -> Dict:
        return {
            "id": _new_id(),
            "Descricao_Fatura": descricao,
            "Valor": valor,
            "Tipo": tipo,
            "Status_Conciliacao": status,
        }

    def _tx(
        self,
        descricao: str,
        valor: float,
        cartao: str,
        titular: str,
        categoria: str,
        tipo: str = "debito",
    ) -> Dict:
        return {
            "id": _new_id(),
            "Descricao": descricao,
            "Valor": valor,
            "Cartao": cartao,
            "Titular": titular,
            "Categoria": categoria,
            "Tipo": tipo,
        }

    def _ensure_profile(self, profile_name: str) -> None:
        if profile_name not in self._profiles:
            self._profiles[profile_name] = {**DEFAULTS, "onboarding_done": False}
        self._mensal.setdefault(profile_name, {})
        self._transacoes.setdefault(profile_name, {})
        self._goals.setdefault(profile_name, [])
        self._budgets.setdefault(profile_name, {})

    def get_profile_config(self, profile_name: str) -> Dict:
        self._ensure_profile(profile_name)
        return deepcopy(self._profiles[profile_name])

    def update_profile_config(self, profile_name: str, config: Dict) -> None:
        self._ensure_profile(profile_name)
        self._profiles[profile_name].update(deepcopy(config))

    def get_gastos_fixos(self, profile_name: str, mes: str) -> List[Dict]:
        self._ensure_profile(profile_name)
        return deepcopy(self._mensal[profile_name].get(mes, []))

    def save_gastos_fixos(self, profile_name: str, mes: str, gastos: List[Dict]) -> None:
        self._ensure_profile(profile_name)
        payload = []
        for gasto in deepcopy(gastos):
            gasto.setdefault("id", _new_id())
            payload.append(gasto)
        self._mensal[profile_name][mes] = payload

    def delete_gastos_fixos_mes(self, profile_name: str, mes: str) -> None:
        self._ensure_profile(profile_name)
        self._mensal[profile_name].pop(mes, None)

    def get_transacoes(self, profile_name: str, mes: str) -> List[Dict]:
        self._ensure_profile(profile_name)
        return deepcopy(self._transacoes[profile_name].get(mes, []))

    def add_transacao(self, profile_name: str, mes: str, transacao: Dict) -> str:
        self._ensure_profile(profile_name)
        payload = deepcopy(transacao)
        payload.setdefault("id", _new_id())
        payload.setdefault("Tipo", "debito")
        self._transacoes[profile_name].setdefault(mes, []).append(payload)
        return payload["id"]

    def add_transacoes_batch(self, profile_name: str, mes: str, transacoes: List[Dict]) -> List[str]:
        ids = []
        for transacao in transacoes:
            ids.append(self.add_transacao(profile_name, mes, transacao))
        return ids

    def update_transacao(self, transacao_id: str, updates: Dict) -> None:
        for meses in self._transacoes.values():
            for transacoes in meses.values():
                for transacao in transacoes:
                    if transacao.get("id") == transacao_id:
                        transacao.update(deepcopy(updates))
                        return

    def delete_transacao(self, transacao_id: str) -> None:
        for meses in self._transacoes.values():
            for mes, transacoes in meses.items():
                meses[mes] = [t for t in transacoes if t.get("id") != transacao_id]

    def save_transacoes(self, profile_name: str, mes: str, transacoes: List[Dict]) -> None:
        self._ensure_profile(profile_name)
        payload = []
        for transacao in deepcopy(transacoes):
            transacao.setdefault("id", _new_id())
            transacao.setdefault("Tipo", "debito")
            payload.append(transacao)
        self._transacoes[profile_name][mes] = payload

    def delete_transacoes_mes(self, profile_name: str, mes: str) -> None:
        self._ensure_profile(profile_name)
        self._transacoes[profile_name].pop(mes, None)

    def search_transacoes(
        self,
        profile_name: str,
        mes: str,
        descricao: Optional[str] = None,
        categorias: Optional[List[str]] = None,
        cartao: Optional[str] = None,
    ) -> List[Dict]:
        itens = self.get_transacoes(profile_name, mes)
        resultado = []
        for transacao in itens:
            if descricao and descricao.lower() not in str(transacao.get("Descricao", "")).lower():
                continue
            if categorias and transacao.get("Categoria") not in categorias:
                continue
            if cartao and str(transacao.get("Cartao", "")) != str(cartao):
                continue
            resultado.append(transacao)
        return resultado

    def get_all_meses(self, profile_name: str) -> List[str]:
        self._ensure_profile(profile_name)
        meses = set(self._mensal[profile_name].keys()) | set(self._transacoes[profile_name].keys())
        return sorted(meses)

    def create_mes(self, profile_name: str, mes: str, copiar_fixos_de: Optional[str] = None) -> None:
        self._ensure_profile(profile_name)
        self._transacoes[profile_name].setdefault(mes, [])
        if copiar_fixos_de and copiar_fixos_de in self._mensal[profile_name]:
            copia = deepcopy(self._mensal[profile_name][copiar_fixos_de])
            for gasto in copia:
                gasto["id"] = _new_id()
            self._mensal[profile_name][mes] = copia
        else:
            self._mensal[profile_name].setdefault(mes, [])

    def delete_mes(self, profile_name: str, mes: str) -> None:
        self._ensure_profile(profile_name)
        self._mensal[profile_name].pop(mes, None)
        self._transacoes[profile_name].pop(mes, None)

    def get_mensal_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        self._ensure_profile(profile_name)
        return deepcopy(self._mensal[profile_name])

    def get_transacoes_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        self._ensure_profile(profile_name)
        return deepcopy(self._transacoes[profile_name])

    def get_goals(self, profile_name: str) -> List[Dict]:
        self._ensure_profile(profile_name)
        return deepcopy(self._goals[profile_name])

    def save_goal(self, profile_name: str, goal: Dict) -> str:
        self._ensure_profile(profile_name)
        payload = deepcopy(goal)
        goal_id = payload.get("id") or _new_id()
        payload["id"] = goal_id

        for idx, existing in enumerate(self._goals[profile_name]):
            if existing.get("id") == goal_id:
                self._goals[profile_name][idx] = payload
                return goal_id

        self._goals[profile_name].append(payload)
        return goal_id

    def delete_goal(self, goal_id: str) -> None:
        for profile_name in self._goals:
            self._goals[profile_name] = [goal for goal in self._goals[profile_name] if goal.get("id") != goal_id]

    def get_category_budgets(self, profile_name: str) -> Dict[str, float]:
        self._ensure_profile(profile_name)
        return deepcopy(self._budgets[profile_name])

    def save_category_budgets(self, profile_name: str, budgets: Dict[str, float]) -> None:
        self._ensure_profile(profile_name)
        self._budgets[profile_name].update(deepcopy(budgets))

    def delete_category_budget(self, profile_name: str, categoria: str) -> None:
        self._ensure_profile(profile_name)
        self._budgets[profile_name].pop(categoria, None)
