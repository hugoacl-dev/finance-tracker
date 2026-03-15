def mes_sort_key(m: str) -> tuple[int, int]:
    """Converte 'MM/YYYY' em (ano, mês) para ordenação cronológica."""
    try:
        mes, ano = m.split("/")
        return (int(ano), int(mes))
    except (ValueError, AttributeError):
        return (0, 0)
