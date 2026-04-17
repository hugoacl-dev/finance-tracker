"""
Factory para criar instância do DataService.
Retorna implementação Supabase configurada.
"""
from services.data_service import DataService
from services.local_adapter import LocalDataService
from services.runtime_secrets import has_supabase_credentials
from services.supabase_adapter import SupabaseAdapter

_data_service_instance = None


def get_data_service() -> DataService:
    """
    Factory que retorna a implementação Supabase do DataService.
    Usa singleton pattern para reutilizar a mesma conexão.
    
    Returns:
        DataService: Instância do SupabaseAdapter
    """
    global _data_service_instance
    
    if _data_service_instance is None:
        _data_service_instance = SupabaseAdapter() if has_supabase_credentials() else LocalDataService()
    
    return _data_service_instance
