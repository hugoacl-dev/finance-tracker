import pandas as pd
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
import difflib
import unicodedata
import re


def normalize_text(t: Optional[str]) -> str:
    if not t: return ""
    t = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII')
    return "".join([char for char in t if char.isalnum()]).upper()

def is_similar(t1: str, t2: str, threshold: float = 0.8) -> bool:
    if t1 == t2: return True
    return difflib.SequenceMatcher(None, normalize_text(t1), normalize_text(t2)).ratio() >= threshold

def dias_ate_fechamento(dia_fechamento: int) -> int:
    fuso_br = timezone(timedelta(hours=-3))
    hoje = datetime.now(fuso_br).date()
    
    if hoje.day > dia_fechamento:
        if hoje.month == 12:
            prox = date(hoje.year + 1, 1, dia_fechamento)
        else:
            prox = date(hoje.year, hoje.month + 1, dia_fechamento)
    else:
        prox = date(hoje.year, hoje.month, dia_fechamento)
    
    # +1 para incluir o dia de hoje E o dia do fechamento no cálculo de dias restantes
    return (prox - hoje).days + 1

def filtro_titularidade(
    df: pd.DataFrame,
    perfil_ativo: str,
    cartoes_aceitos: list[str] | None = None,
    cartoes_excluidos: list[str] | None = None,
) -> pd.DataFrame:
    if "Cartao" not in df.columns or df.empty:
        return df

    cartao_str = df["Cartao"].astype(str).str.strip().str.lower()

    # Excluir cartões marcados para exclusão neste perfil
    if cartoes_excluidos:
        for exc in cartoes_excluidos:
            mask_exc = cartao_str.str.contains(exc.lower(), na=False)
            df = df[~mask_exc].copy()
            cartao_str = df["Cartao"].astype(str).str.strip().str.lower()

    # Filtrar apenas cartões aceitos (se configurado)
    if cartoes_aceitos:
        aceitos_lower = [a.lower() for a in cartoes_aceitos]
        mask_vazio = (cartao_str == "") | (cartao_str == "nan") | (cartao_str == "none")
        mask_aceito = cartao_str.apply(lambda c: any(a in c for a in aceitos_lower))
        df = df[mask_vazio | mask_aceito].copy()

    return df

def filtro_dedup_fixos(df_ops: pd.DataFrame, df_config: pd.DataFrame) -> pd.DataFrame:
    if "Status_Conciliacao" not in df_config.columns:
        df_config["Status_Conciliacao"] = ""

    if df_config.empty or df_ops.empty:
        return df_ops

    mask_cartao = df_config["Tipo"].astype(str).str.strip().str.lower() == "cartao"
    df_config.loc[mask_cartao, "Status_Conciliacao"] = "⏳ Pendente"

    fixos_cartao = df_config[mask_cartao]
    if fixos_cartao.empty:
        return df_ops

    indices_to_drop = set()

    def get_keyword(text: str) -> str:
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).strip()
        words = clean.split()
        if not words:
            return text.strip().lower()
        for w in words:
            if len(w) > 2:
                return w.lower()
        return words[0].lower() if words else text.strip().lower()

    for i_fixo, fixo in fixos_cartao.iterrows():
        kw_f = get_keyword(str(fixo.get("Descricao_Fatura", "")))
        v_f = float(fixo.get("Valor", 0))

        encontrou = False
        for i_op, op in df_ops.iterrows():
            if i_op in indices_to_drop:
                continue

            desc_op = str(op.get("Descricao", "")).lower()
            v_op = float(op.get("Valor", 0))

            if kw_f in desc_op and abs(v_f - v_op) < 0.05:
                indices_to_drop.add(i_op)
                encontrou = True
                break

        if encontrou:
            df_config.at[i_fixo, "Status_Conciliacao"] = "✅ Confirmado"

    if indices_to_drop:
        df_ops = df_ops.drop(index=list(indices_to_drop)).reset_index(drop=True)

    return df_ops

def processar_mes(
    df_config: pd.DataFrame,
    df_ops: pd.DataFrame,
    perfil_ativo: str,
    teto_gastos: float,
    receita_base: float,
    meta_aporte: float,
    cartoes_aceitos: list[str] | None = None,
    cartoes_excluidos: list[str] | None = None,
) -> dict[str, Any]:
    total_fixos = df_config["Valor"].sum() if not df_config.empty else 0.0
    limite_base_var = teto_gastos - total_fixos

    df_ops = filtro_titularidade(df_ops, perfil_ativo, cartoes_aceitos, cartoes_excluidos)
    df_ops = filtro_dedup_fixos(df_ops, df_config)

    total_variaveis = df_ops["Valor"].sum() if not df_ops.empty else 0.0
    total_comprometido = total_fixos + total_variaveis
    saldo_variaveis = limite_base_var - total_variaveis
    saldo_teto = teto_gastos - total_comprometido
    pct_teto = (total_comprometido / teto_gastos) * 100 if teto_gastos > 0 else 0
    aporte_real = receita_base - total_comprometido
    meta_ameacada = aporte_real < meta_aporte

    return {
        "df_config": df_config,
        "df_ops": df_ops,
        "total_fixos": total_fixos,
        "limite_base_var": limite_base_var,
        "total_variaveis": total_variaveis,
        "saldo_variaveis": saldo_variaveis,
        "total_comprometido": total_comprometido,
        "saldo_teto": saldo_teto,
        "pct_teto": pct_teto,
        "aporte_real": aporte_real,
        "meta_ameacada": meta_ameacada,
    }

def process_idempotency_pass(
    trans_lista: list[dict],
    buffers: dict[str, list[dict]],
    cond_match_func: Any,
) -> None:
    for t in trans_lista:
        if t.get('is_dupe') or t.get('dest_profile', '').startswith('Ign'):
            continue
            
        c = str(t.get("Cartao", "")).strip()
        c = c.zfill(4) if c.isdigit() else c
        d = str(t.get("Descricao", "")).strip()
        v = float(t.get("Valor", 0))
        
        prof = t.get('dest_profile', 'Principal')
        
        if prof not in buffers:
            continue
            
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


# ═══════════════════════════════════════
# SCORE DE SAÚDE FINANCEIRA (Wave 2.1)
# ═══════════════════════════════════════
def calcular_score_financeiro(
    savings_rate: float,
    pct_teto: float,
    meta_batida: bool,
    consistencia_std: float,
    pct_nao_classificados: float,
) -> dict[str, Any]:
    """
    Calcula score de saúde financeira (0-100) com 5 pilares:
    1. Savings Rate (30pts)
    2. Aderência ao Teto (25pts)
    3. Meta de Aporte (20pts)
    4. Consistência (15pts)
    5. Organização (10pts)
    """
    # Pilar 1: Savings Rate (30pts)
    if savings_rate >= 30:
        p1 = 30
    elif savings_rate >= 20:
        p1 = 20
    elif savings_rate >= 10:
        p1 = 12
    else:
        p1 = 5

    # Pilar 2: Aderência ao Teto (25pts)
    if pct_teto <= 85:
        p2 = 25
    elif pct_teto <= 95:
        p2 = 18
    elif pct_teto <= 100:
        p2 = 10
    else:
        p2 = 3

    # Pilar 3: Meta de Aporte (20pts)
    if meta_batida:
        p3 = 20
    elif pct_teto <= 105:
        p3 = 12
    else:
        p3 = 5

    # Pilar 4: Consistência (15pts) — stddev do SR nos últimos meses
    if consistencia_std < 5:
        p4 = 15
    elif consistencia_std < 10:
        p4 = 10
    else:
        p4 = 5

    # Pilar 5: Organização (10pts) — % não classificados
    if pct_nao_classificados < 5:
        p5 = 10
    elif pct_nao_classificados < 15:
        p5 = 6
    else:
        p5 = 2

    total = p1 + p2 + p3 + p4 + p5

    if total >= 85:
        label = "Excelente"
        emoji = "🏆"
    elif total >= 70:
        label = "Bom"
        emoji = "✅"
    elif total >= 50:
        label = "Regular"
        emoji = "⚠️"
    else:
        label = "Crítico"
        emoji = "🚨"

    return {
        "score": total,
        "label": label,
        "emoji": emoji,
        "pilares": {
            "Savings Rate": p1,
            "Aderência ao Teto": p2,
            "Meta de Aporte": p3,
            "Consistência": p4,
            "Organização": p5,
        }
    }


# ═══════════════════════════════════════
# DETECÇÃO DE PARCELAMENTOS (Wave 2.3)
# ═══════════════════════════════════════
def detectar_parcelamento(descricao: str) -> Optional[tuple]:
    """
    Detecta padrão de parcelamento na descrição.
    Exemplos válidos: 'LOJA PARC 3/12', 'MAGAZINE 03/12', 'ITEM 3 DE 12'
    Exemplos INVÁLIDOS: '01/03 PAGUE MENOS' (data), '12/11 FARMACIA' (data)
    Retorna (parcela_atual, total_parcelas) ou None.
    """
    if not descricao:
        return None

    # Estratégia 1: buscar keyword explícita (PARC, PARCELA) — alta confiança
    match_kw = re.search(r'(?:PARC(?:ELA)?)\s*(\d{1,2})\s*[/dDeE]+\s*(\d{1,2})', descricao, re.IGNORECASE)
    if match_kw:
        atual, total = int(match_kw.group(1)), int(match_kw.group(2))
        if 1 <= atual <= total <= 48 and total > 1:
            return (atual, total)

    # Estratégia 2: padrão X/Y, mas NÃO no início da string (evita datas DD/MM)
    match = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})', descricao)
    if match and match.start() > 0:
        atual, total = int(match.group(1)), int(match.group(2))
        # Filtro extra: se total <= 12 e atual <= 31, pode ser data — exigir total > 12
        # OU atual <= total (regra normal de parcela)
        if 1 <= atual <= total <= 48 and total > 1:
            # Se parece data (atual <= 31, total <= 12), rejeitar
            if atual <= 31 and total <= 12:
                return None
            return (atual, total)

    return None


# ═══════════════════════════════════════
# DETECÇÃO DE ANOMALIAS (Wave 3.2)
# ═══════════════════════════════════════
def detectar_anomalia(
    valor: float,
    media: float,
    std: float,
    z_threshold: float = 2.0,
) -> bool:
    """Detecção de anomalia via z-score."""
    if std == 0:
        return valor > media * 2
    return ((valor - media) / std) > z_threshold

