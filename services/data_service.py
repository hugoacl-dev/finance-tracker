"""
Interface abstrata para operações de dados.
Permite trocar implementação (Supabase, Firebase, etc) sem alterar código das views.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class DataService(ABC):
    """Interface abstrata para operações de dados"""
    
    # ===== PROFILES =====
    
    @abstractmethod
    def get_profile_config(self, profile_name: str) -> Dict:
        """
        Retorna configuração de um perfil.
        
        Args:
            profile_name: Nome do perfil ('Principal' ou 'Dependente')
            
        Returns:
            Dict com configurações (Receita_Base, Meta_Aporte, etc)
        """
        pass
    
    @abstractmethod
    def update_profile_config(self, profile_name: str, config: Dict) -> None:
        """
        Atualiza configuração de um perfil.
        
        Args:
            profile_name: Nome do perfil
            config: Dict com configurações a atualizar
        """
        pass
    
    # ===== GASTOS FIXOS =====
    
    @abstractmethod
    def get_gastos_fixos(self, profile_name: str, mes: str) -> List[Dict]:
        """
        Retorna gastos fixos de um perfil/mês.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês no formato 'Abril 25' ou '04/2025'
            
        Returns:
            Lista de dicts com gastos fixos
        """
        pass
    
    @abstractmethod
    def save_gastos_fixos(self, profile_name: str, mes: str, gastos: List[Dict]) -> None:
        """
        Salva gastos fixos (substitui todos do mês).
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            gastos: Lista de gastos fixos
        """
        pass
    
    @abstractmethod
    def delete_gastos_fixos_mes(self, profile_name: str, mes: str) -> None:
        """
        Deleta todos gastos fixos de um mês.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
        """
        pass
    
    # ===== TRANSAÇÕES =====
    
    @abstractmethod
    def get_transacoes(self, profile_name: str, mes: str) -> List[Dict]:
        """
        Retorna transações de um perfil/mês.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            
        Returns:
            Lista de dicts com transações
        """
        pass
    
    @abstractmethod
    def add_transacao(self, profile_name: str, mes: str, transacao: Dict) -> str:
        """
        Adiciona uma transação e retorna o ID.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            transacao: Dict com dados da transação
            
        Returns:
            ID da transação criada
        """
        pass
    
    @abstractmethod
    def add_transacoes_batch(self, profile_name: str, mes: str, transacoes: List[Dict]) -> List[str]:
        """
        Adiciona múltiplas transações em lote.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            transacoes: Lista de transações
            
        Returns:
            Lista de IDs das transações criadas
        """
        pass
    
    @abstractmethod
    def update_transacao(self, transacao_id: str, updates: Dict) -> None:
        """
        Atualiza campos de uma transação.
        
        Args:
            transacao_id: ID da transação
            updates: Dict com campos a atualizar
        """
        pass
    
    @abstractmethod
    def delete_transacao(self, transacao_id: str) -> None:
        """
        Deleta uma transação.
        
        Args:
            transacao_id: ID da transação
        """
        pass
    
    @abstractmethod
    def save_transacoes(self, profile_name: str, mes: str, transacoes: List[Dict]) -> None:
        """
        Salva todas transações de um mês (substitui).
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            transacoes: Lista de transações
        """
        pass
    
    @abstractmethod
    def delete_transacoes_mes(self, profile_name: str, mes: str) -> None:
        """
        Deleta todas transações de um mês.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
        """
        pass
    
    @abstractmethod
    def search_transacoes(self, profile_name: str, mes: str, 
                         descricao: Optional[str] = None,
                         categorias: Optional[List[str]] = None,
                         cartao: Optional[str] = None) -> List[Dict]:
        """
        Busca transações com filtros.
        
        Args:
            profile_name: Nome do perfil
            mes: Mês
            descricao: Texto para buscar na descrição (opcional)
            categorias: Lista de categorias para filtrar (opcional)
            cartao: Número do cartão para filtrar (opcional)
            
        Returns:
            Lista de transações que atendem os filtros
        """
        pass
    
    # ===== MESES =====
    
    @abstractmethod
    def get_all_meses(self, profile_name: str) -> List[str]:
        """
        Retorna lista de todos os meses cadastrados.
        
        Args:
            profile_name: Nome do perfil
            
        Returns:
            Lista de meses (strings)
        """
        pass
    
    @abstractmethod
    def create_mes(self, profile_name: str, mes: str, 
                   copiar_fixos_de: Optional[str] = None) -> None:
        """
        Cria um novo mês, opcionalmente copiando fixos.
        
        Args:
            profile_name: Nome do perfil
            mes: Nome do novo mês
            copiar_fixos_de: Mês de onde copiar gastos fixos (opcional)
        """
        pass
    
    @abstractmethod
    def delete_mes(self, profile_name: str, mes: str) -> None:
        """
        Deleta um mês completo (fixos + transações).
        
        Args:
            profile_name: Nome do perfil
            mes: Mês a deletar
        """
        pass
    
    # ===== DADOS AGREGADOS =====
    
    @abstractmethod
    def get_mensal_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        """
        Retorna todos gastos fixos agrupados por mês.
        
        Args:
            profile_name: Nome do perfil
            
        Returns:
            Dict {mes: [gastos_fixos]}
        """
        pass
    
    @abstractmethod
    def get_transacoes_data(self, profile_name: str) -> Dict[str, List[Dict]]:
        """
        Retorna todas transações agrupadas por mês.
        
        Args:
            profile_name: Nome do perfil
            
        Returns:
            Dict {mes: [transacoes]}
        """
        pass

    # ===== GOALS (Metas de Longo Prazo) =====

    @abstractmethod
    def get_goals(self, profile_name: str) -> List[Dict]:
        """Retorna todas as metas do perfil."""
        pass

    @abstractmethod
    def save_goal(self, profile_name: str, goal: Dict) -> str:
        """Cria ou atualiza uma meta. Retorna o ID."""
        pass

    @abstractmethod
    def delete_goal(self, goal_id: str) -> None:
        """Deleta uma meta pelo ID."""
        pass

    # ===== CATEGORY BUDGETS (Orçamento por Categoria) =====

    @abstractmethod
    def get_category_budgets(self, profile_name: str) -> Dict[str, float]:
        """Retorna dict {categoria: limite} do perfil."""
        pass

    @abstractmethod
    def save_category_budgets(self, profile_name: str, budgets: Dict[str, float]) -> None:
        """Salva limites por categoria (upsert)."""
        pass

    @abstractmethod
    def delete_category_budget(self, profile_name: str, categoria: str) -> None:
        """Remove o limite de uma categoria."""
        pass

