"""
Módulo de previsão e análise de séries temporais financeiras.
Wave 3.1 — Previsão de Gastos (EMA)
Wave 3.3 — Clustering de Descrições
Wave 3.4 — Sazonalidade
"""
from typing import Optional
import difflib
from services.data_engine import normalize_text


# ═══════════════════════════════════════
# PREVISÃO DE GASTOS (EMA)
# ═══════════════════════════════════════
def prever_gastos_categoria(
    historico: list[float],
    alpha: float = 0.3,
) -> float:
    """
    Média Móvel Exponencial (EMA) para previsão de gastos.
    Alpha alto (0.5) = mais peso nos meses recentes.
    Alpha baixo (0.1) = mais suave, menos reativo.
    """
    if not historico:
        return 0.0
    ema = historico[0]
    for val in historico[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return round(ema, 2)


def calcular_tendencia(historico: list[float]) -> str:
    """Retorna ↑, ↓ ou → baseado nos últimos 3 meses."""
    if len(historico) < 2:
        return "→"
    ultimos = historico[-3:] if len(historico) >= 3 else historico
    delta = ultimos[-1] - ultimos[0]
    media = sum(ultimos) / len(ultimos) if ultimos else 1
    pct = (delta / media * 100) if media != 0 else 0
    if pct > 10:
        return "↑"
    elif pct < -10:
        return "↓"
    return "→"


# ═══════════════════════════════════════
# CLUSTERING DE DESCRIÇÕES
# ═══════════════════════════════════════
def agrupar_descricoes(
    descricoes: list[str],
    threshold: float = 0.65,
) -> dict[str, list[str]]:
    """
    Agrupa descrições similares usando SequenceMatcher.
    Ex: ['UBER TRIP', 'UBER EATS', 'UBER BR'] → {'UBER TRIP': ['UBER EATS', 'UBER BR']}
    """
    if not descricoes:
        return {}

    clusters: dict[str, list[str]] = {}
    normalized_cache: dict[str, str] = {}

    for desc in descricoes:
        if not desc or not desc.strip():
            continue

        norm = normalize_text(desc)
        normalized_cache[desc] = norm

        melhor_match: Optional[str] = None
        melhor_score = 0.0

        for centroid in clusters:
            score = difflib.SequenceMatcher(
                None, norm, normalized_cache.get(centroid, normalize_text(centroid))
            ).ratio()
            if score > melhor_score and score >= threshold:
                melhor_score = score
                melhor_match = centroid

        if melhor_match:
            clusters[melhor_match].append(desc)
        else:
            clusters[desc] = []

    return clusters


# ═══════════════════════════════════════
# SAZONALIDADE
# ═══════════════════════════════════════
def analisar_sazonalidade(
    historico_por_mes: dict[str, float],
) -> dict[str, dict]:
    """
    Analisa padrões sazonais nos gastos.
    Identifica meses tipicamente mais caros/baratos.

    Args:
        historico_por_mes: {'01/25': 10500, '02/25': 9800, '12/24': 15200}

    Returns:
        {'12': {'media': 15200, 'label': 'Dezembro é historicamente seu mês mais caro', ...}}
    """
    if not historico_por_mes:
        return {}

    # Agrupar por mês do ano (1-12)
    por_mes_ano: dict[int, list[float]] = {}
    for key, valor in historico_por_mes.items():
        try:
            mes_str = key.split("/")[0]
            mes_num = int(mes_str)
            if mes_num not in por_mes_ano:
                por_mes_ano[mes_num] = []
            por_mes_ano[mes_num].append(valor)
        except (ValueError, IndexError):
            continue

    if not por_mes_ano:
        return {}

    # Média global
    todos_valores = [v for vals in por_mes_ano.values() for v in vals]
    media_global = sum(todos_valores) / len(todos_valores) if todos_valores else 0

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    resultado = {}
    for mes_num, valores in por_mes_ano.items():
        media_mes = sum(valores) / len(valores)
        delta_pct = ((media_mes / media_global) - 1) * 100 if media_global > 0 else 0
        nome = meses_nomes.get(mes_num, str(mes_num))

        if delta_pct > 15:
            label = f"{nome} é historicamente seu mês mais caro (+{delta_pct:.0f}% vs média)"
            tipo = "alto"
        elif delta_pct < -15:
            label = f"{nome} é historicamente seu mês mais econômico ({delta_pct:.0f}% vs média)"
            tipo = "baixo"
        else:
            label = f"{nome} está na média histórica"
            tipo = "normal"

        resultado[str(mes_num).zfill(2)] = {
            "nome": nome,
            "media": round(media_mes, 2),
            "delta_pct": round(delta_pct, 1),
            "label": label,
            "tipo": tipo,
            "amostras": len(valores),
        }

    return resultado
