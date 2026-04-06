from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from core.utils import mes_sort_key
from services.data_engine import dias_ate_fechamento, processar_mes
from services.ocr_gemini import get_gemini_client


FIXED_SUGGESTED_QUESTIONS = [
    "Quais foram os grandes diferenciais desta fatura em relacao ao mes passado?",
    "Onde estao os maiores ralos financeiros deste mes?",
    "Se eu precisar cortar gastos agora, por onde devo comecar?",
    "Estou acima do meu padrao historico ou este mes esta dentro do normal?",
]

MAX_HISTORY_MONTHS_IN_PROMPT = 6
MAX_CONVERSATION_MESSAGES_IN_PROMPT = 10


def sanitize_ai_response(text: str) -> str:
    """
    Escape dollar signs to prevent LaTeX rendering in Streamlit markdown.
    This fixes the issue where R$ currency symbols cause text to be rendered
    as math notation (green text between $ symbols).
    """
    return text.replace("$", r"\$")


def _format_currency(value: float) -> str:
    return f"R$ {value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def _get_signed_category_totals(df_ops: pd.DataFrame) -> pd.Series:
    if df_ops.empty or "Categoria" not in df_ops.columns or "Valor" not in df_ops.columns:
        return pd.Series(dtype="float64")

    df_work = df_ops.copy()
    if "Tipo" in df_work.columns:
        signal = df_work["Tipo"].apply(lambda item: -1.0 if item == "credito" else 1.0)
        df_work["Valor_Ajustado"] = df_work["Valor"] * signal
    else:
        df_work["Valor_Ajustado"] = df_work["Valor"]

    return df_work.groupby("Categoria")["Valor_Ajustado"].sum().sort_values(ascending=False)


def build_month_snapshot(
    mes: str,
    mensal_data: dict[str, list[dict]],
    transacoes_data: dict[str, list[dict]],
    perfil_ativo: str,
    teto_gastos: float,
    receita_base: float,
    meta_aporte: float,
    cartoes_aceitos: list[str] | None,
    cartoes_excluidos: list[str] | None,
    category_budgets_data: dict[str, float],
) -> dict[str, Any]:
    df_config = pd.DataFrame(mensal_data.get(mes, []))
    df_ops = pd.DataFrame(transacoes_data.get(mes, []))
    result = processar_mes(
        df_config,
        df_ops,
        perfil_ativo,
        teto_gastos,
        receita_base,
        meta_aporte,
        cartoes_aceitos,
        cartoes_excluidos,
    )

    category_totals = _get_signed_category_totals(result["df_ops"])
    budget_overruns = []
    for categoria, limite in category_budgets_data.items():
        gasto_real = float(category_totals.get(categoria, 0.0))
        excesso = gasto_real - float(limite)
        if excesso > 0:
            budget_overruns.append(
                {
                    "categoria": categoria,
                    "limite": float(limite),
                    "gasto": gasto_real,
                    "excesso": excesso,
                }
            )

    budget_overruns.sort(key=lambda item: item["excesso"], reverse=True)
    top_categories = [(categoria, float(valor)) for categoria, valor in category_totals.head(5).items()]

    savings_rate = (result["aporte_real"] / receita_base * 100) if receita_base > 0 else 0.0
    pct_teto = (result["total_comprometido"] / teto_gastos * 100) if teto_gastos > 0 else 0.0

    alerts = []
    if result["saldo_teto"] < 0:
        alerts.append("Teto estourado")
    if result["meta_ameacada"]:
        alerts.append("Meta de aporte ameacada")
    if result["saldo_variaveis"] < 0:
        alerts.append("Saldo negativo para variaveis")
    if budget_overruns:
        alerts.append("Categorias acima do orcamento")

    return {
        "mes": mes,
        "result": result,
        "category_totals": category_totals,
        "top_categories": top_categories,
        "budget_overruns": budget_overruns,
        "savings_rate": savings_rate,
        "pct_teto": pct_teto,
        "alerts": alerts,
    }


def build_history_snapshots(
    all_meses: list[str],
    mensal_data: dict[str, list[dict]],
    transacoes_data: dict[str, list[dict]],
    perfil_ativo: str,
    teto_gastos: float,
    receita_base: float,
    meta_aporte: float,
    cartoes_aceitos: list[str] | None,
    cartoes_excluidos: list[str] | None,
    category_budgets_data: dict[str, float],
) -> list[dict[str, Any]]:
    ordered_months = sorted(all_meses, key=mes_sort_key)
    return [
        build_month_snapshot(
            mes,
            mensal_data,
            transacoes_data,
            perfil_ativo,
            teto_gastos,
            receita_base,
            meta_aporte,
            cartoes_aceitos,
            cartoes_excluidos,
            category_budgets_data,
        )
        for mes in ordered_months
    ]


def get_previous_month(mes_insight: str, ordered_months: list[str]) -> str | None:
    try:
        idx = ordered_months.index(mes_insight)
    except ValueError:
        return None
    if idx <= 0:
        return None
    return ordered_months[idx - 1]


def build_month_comparison(
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not previous_snapshot:
        return None

    current_result = current_snapshot["result"]
    previous_result = previous_snapshot["result"]
    current_categories = current_snapshot["category_totals"]
    previous_categories = previous_snapshot["category_totals"]

    all_categories = set(current_categories.index).union(set(previous_categories.index))
    category_deltas = []
    for categoria in all_categories:
        atual = float(current_categories.get(categoria, 0.0))
        anterior = float(previous_categories.get(categoria, 0.0))
        delta = atual - anterior
        category_deltas.append(
            {
                "categoria": categoria,
                "atual": atual,
                "anterior": anterior,
                "delta": delta,
            }
        )

    increases = sorted(
        [item for item in category_deltas if item["delta"] > 0],
        key=lambda item: item["delta"],
        reverse=True,
    )[:3]
    decreases = sorted(
        [item for item in category_deltas if item["delta"] < 0],
        key=lambda item: item["delta"],
    )[:3]

    return {
        "current_month": current_snapshot["mes"],
        "previous_month": previous_snapshot["mes"],
        "delta_comprometido": current_result["total_comprometido"] - previous_result["total_comprometido"],
        "delta_fixos": current_result["total_fixos"] - previous_result["total_fixos"],
        "delta_variaveis": current_result["total_variaveis"] - previous_result["total_variaveis"],
        "increases": increases,
        "decreases": decreases,
    }


def _build_focus_month_block(
    snapshot: dict[str, Any],
    receita_base: float,
    meta_aporte: float,
    teto_gastos: float,
    dia_fechamento: int,
) -> str:
    result = snapshot["result"]
    lines = [
        f"--- MES EM FOCO ({snapshot['mes']}) ---",
        f"Receita Base: {_format_currency(receita_base)}",
        f"Meta de Aporte: {_format_currency(meta_aporte)}",
        f"Teto de Gastos: {_format_currency(teto_gastos)}",
        f"Dias ate fechamento: {dias_ate_fechamento(dia_fechamento)}",
        "",
        "--- RESUMO DO CICLO ---",
        f"Total Fixos: {_format_currency(result['total_fixos'])}",
        f"Total Variaveis: {_format_currency(result['total_variaveis'])}",
        f"Total Comprometido: {_format_currency(result['total_comprometido'])}",
        f"Saldo Restante do Teto: {_format_currency(result['saldo_teto'])}",
        f"Aporte Real Projetado: {_format_currency(result['aporte_real'])}",
        f"Delta vs Meta: {_format_currency(result['aporte_real'] - meta_aporte)}",
        f"Savings Rate: {_format_pct(snapshot['savings_rate'])}",
        f"Percentual do Teto Consumido: {_format_pct(snapshot['pct_teto'])}",
    ]

    if snapshot["alerts"]:
        lines.extend(["", "Alertas:", *[f"- {alerta}" for alerta in snapshot["alerts"]]])

    if not result["df_config"].empty:
        lines.extend(["", "--- GASTOS FIXOS ---"])
        for _, row in result["df_config"].iterrows():
            tipo = row.get("Tipo", "")
            tipo_str = f" [{tipo}]" if tipo else ""
            lines.append(f"- {row['Descricao_Fatura']}{tipo_str}: {_format_currency(float(row['Valor']))}")

    if snapshot["top_categories"]:
        lines.extend(["", "--- GASTOS VARIAVEIS POR CATEGORIA ---"])
        for categoria, valor in snapshot["top_categories"]:
            lines.append(f"- {categoria}: {_format_currency(valor)}")

    if snapshot["budget_overruns"]:
        lines.extend(["", "--- LIMITES ESTOURADOS ---"])
        for item in snapshot["budget_overruns"][:5]:
            lines.append(
                f"- {item['categoria']}: gasto {_format_currency(item['gasto'])} vs limite "
                f"{_format_currency(item['limite'])} (excesso {_format_currency(item['excesso'])})"
            )

    if not result["df_ops"].empty:
        lines.extend(["", "--- MAIORES TRANSACOES DO MES ---"])
        df_sorted = result["df_ops"].copy()
        if "Tipo" in df_sorted.columns:
            signal = df_sorted["Tipo"].apply(lambda item: -1.0 if item == "credito" else 1.0)
            df_sorted["Valor_Ajustado"] = df_sorted["Valor"] * signal
            df_sorted = df_sorted.sort_values("Valor_Ajustado", ascending=False)
        else:
            df_sorted = df_sorted.sort_values("Valor", ascending=False)
        for _, row in df_sorted.head(8).iterrows():
            categoria = row.get("Categoria", "Outros")
            tipo = row.get("Tipo", "debito")
            lines.append(
                f"- {row['Descricao']} ({categoria}, {tipo}): {_format_currency(float(row['Valor']))}"
            )

    return "\n".join(lines)


def _build_history_block(history_snapshots: list[dict[str, Any]]) -> str:
    lines = ["--- HISTORICO COMPLETO DO PERFIL ---"]
    for snapshot in history_snapshots:
        result = snapshot["result"]
        lines.append(
            f"{snapshot['mes']}: comprometido {_format_currency(result['total_comprometido'])}, "
            f"fixos {_format_currency(result['total_fixos'])}, "
            f"variaveis {_format_currency(result['total_variaveis'])}"
        )
        if snapshot["top_categories"]:
            top_text = ", ".join(
                f"{categoria} {_format_currency(valor)}" for categoria, valor in snapshot["top_categories"][:3]
            )
            lines.append(f"Top categorias: {top_text}")
        lines.append("")
    return "\n".join(lines).strip()


def _build_comparison_block(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return (
            "--- COMPARACAO COM O MES ANTERIOR ---\n"
            "Nao existe mes anterior carregado antes do mes em foco. Se o usuario pedir comparacao, "
            "explique isso sem negar acesso ao sistema atual."
        )

    lines = [
        "--- COMPARACAO COM O MES ANTERIOR ---",
        f"Mes atual: {comparison['current_month']}",
        f"Mes anterior: {comparison['previous_month']}",
        f"Delta comprometido: {_format_currency(comparison['delta_comprometido'])}",
        f"Delta fixos: {_format_currency(comparison['delta_fixos'])}",
        f"Delta variaveis: {_format_currency(comparison['delta_variaveis'])}",
    ]

    if comparison["increases"]:
        lines.extend(["", "Categorias que mais subiram:"])
        for item in comparison["increases"]:
            lines.append(
                f"- {item['categoria']}: {_format_currency(item['anterior'])} -> "
                f"{_format_currency(item['atual'])} ({_format_currency(item['delta'])})"
            )

    if comparison["decreases"]:
        lines.extend(["", "Categorias que mais cairam:"])
        for item in comparison["decreases"]:
            lines.append(
                f"- {item['categoria']}: {_format_currency(item['anterior'])} -> "
                f"{_format_currency(item['atual'])} ({_format_currency(item['delta'])})"
            )

    return "\n".join(lines)


def _build_goals_block(goals_data: list[dict]) -> str:
    if not goals_data:
        return ""

    lines = ["--- METAS DE LONGO PRAZO ---"]
    for goal in goals_data:
        prazo = int(goal.get("prazo_meses", 0) or 0)
        valor_alvo = float(goal.get("valor_alvo", 0) or 0)
        aporte_necessario = valor_alvo / prazo if prazo > 0 else 0
        lines.append(
            f"- {goal['titulo']}: alvo {_format_currency(valor_alvo)} em {prazo} meses "
            f"(aporte necessario {_format_currency(aporte_necessario)}/mes)"
        )
    return "\n".join(lines)


def _build_conversation_history(
    chat_history: list[dict],
    max_messages: int = MAX_CONVERSATION_MESSAGES_IN_PROMPT,
) -> str:
    if not chat_history:
        return "Ainda nao houve conversa anterior."

    visible_history = chat_history[-max_messages:] if max_messages > 0 else chat_history
    lines = []
    for item in visible_history:
        role = "Usuario" if item["role"] == "user" else "Consultor"
        lines.append(f"{role}: {item['content']}")
    return "\n".join(lines)


def _select_history_snapshots_for_prompt(
    history_snapshots: list[dict[str, Any]],
    mes_insight: str,
    previous_month: str | None,
    max_months: int = MAX_HISTORY_MONTHS_IN_PROMPT,
) -> list[dict[str, Any]]:
    if max_months <= 0 or len(history_snapshots) <= max_months:
        return history_snapshots

    snapshot_by_month = {snapshot["mes"]: snapshot for snapshot in history_snapshots}
    selected = {snapshot["mes"]: snapshot for snapshot in history_snapshots[-max_months:]}

    for month in [mes_insight, previous_month]:
        if month and month in snapshot_by_month:
            selected[month] = snapshot_by_month[month]

    return sorted(selected.values(), key=lambda snapshot: mes_sort_key(snapshot["mes"]))


def build_consultant_context(
    master_prompt: str,
    mes_insight: str,
    current_snapshot: dict[str, Any],
    history_snapshots: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    receita_base: float,
    meta_aporte: float,
    teto_gastos: float,
    dia_fechamento: int,
    goals_data: list[dict],
    regras_ia: str,
    conversation_history: str = "",
    user_message: str = "",
    mode: str = "chat",
) -> str:
    previous_month = comparison["previous_month"] if comparison else None
    prompt_history = _select_history_snapshots_for_prompt(history_snapshots, mes_insight, previous_month)

    system_prompt = (
        "Voce e o consultor financeiro do projeto Finance Tracker. "
        "Voce tem acesso ao historico financeiro carregado do sistema para o perfil ativo. "
        "Nunca diga que nao tem acesso ao sistema ou aos meses ja fornecidos no contexto. "
        "Quando o usuario pedir comparacao, diferenca, evolucao, mudanca, tendencia ou mencionar "
        "'mes passado', compare automaticamente o mes em foco com o mes cronologicamente anterior, "
        "se ele existir no historico carregado. "
        "Se nao existir mes anterior, diga apenas que nao ha historico anterior disponivel antes do mes em foco. "
        "Para meses anteriores ao mes em foco, trate como totalmente confiaveis apenas os totais observados "
        "de fixos, variaveis, comprometido e categorias. Nao inferira retrospectivamente metas, teto, "
        "savings rate ou cumprimento de orcamento sem dados explicitos. "
        "Use Markdown, seja concreto com numeros e priorize analise financeira acionavel."
    )

    blocks = [
        system_prompt,
        "",
        master_prompt,
        "",
        _build_focus_month_block(current_snapshot, receita_base, meta_aporte, teto_gastos, dia_fechamento),
        "",
        _build_comparison_block(comparison),
        "",
        _build_history_block(prompt_history),
    ]

    goals_block = _build_goals_block(goals_data)
    if goals_block:
        blocks.extend(["", goals_block])

    if regras_ia:
        blocks.extend(["", f"--- REGRAS PERSONALIZADAS DO USUARIO ---\n{regras_ia}"])

    if conversation_history:
        blocks.extend(["", f"--- HISTORICO DA CONVERSA ---\n{conversation_history}"])

    if mode == "diagnostic":
        blocks.extend(
            [
                "",
                "Tarefa: gere um diagnostico financeiro completo do mes em foco usando o historico do perfil "
                "como contexto comparativo. Destaque mudancas contra o mes anterior quando existirem.",
            ]
        )
    else:
        blocks.extend(
            [
                "",
                "Tarefa: responda a pergunta do usuario usando o mes em foco como base e o historico como apoio. "
                "Se houver comparacao pedida, use os dados historicos do sistema.",
            ]
        )

    if user_message:
        blocks.extend(["", f"Usuario: {user_message}"])

    blocks.append("")
    blocks.append("Responda diretamente em portugues do Brasil.")
    return "\n".join(blocks)


def get_suggested_questions(
    current_snapshot: dict[str, Any],
    comparison: dict[str, Any] | None,
    history_snapshots: list[dict[str, Any]],
    goals_data: list[dict],
) -> list[str]:
    dynamic_questions: list[str] = []

    if comparison:
        dynamic_questions.append("Quais categorias mais pesaram em relacao ao mes passado?")

    if current_snapshot["result"]["saldo_teto"] < 0:
        dynamic_questions.append("O que precisa ser cortado para eu voltar ao teto ainda neste ciclo?")

    if current_snapshot["result"]["meta_ameacada"]:
        dynamic_questions.append("O que me impediu de bater a meta de aporte neste mes?")

    if current_snapshot["budget_overruns"]:
        dynamic_questions.append("Quais categorias passaram do limite e como corrigir isso no proximo ciclo?")

    if comparison and comparison["increases"]:
        categoria = comparison["increases"][0]["categoria"]
        dynamic_questions.append(f"Por que {categoria} cresceu tanto neste mes?")

    if len(history_snapshots) < 2:
        dynamic_questions.append("O que ja da para concluir do meu comportamento com o historico disponivel?")

    if goals_data:
        dynamic_questions.append("Estou acelerando ou atrasando minhas metas patrimoniais?")

    if not dynamic_questions:
        dynamic_questions.append("Qual categoria eu deveria monitorar com mais rigor no proximo ciclo?")

    deduped_dynamic = []
    seen = set(FIXED_SUGGESTED_QUESTIONS)
    for question in dynamic_questions:
        if question not in seen:
            deduped_dynamic.append(question)
            seen.add(question)

    contextual_fillers = [
        "Quais despesas parecem recorrentes, mas merecem renegociacao?",
        "O que nesta fatura parece necessidade real e o que parece inflacao de estilo de vida?",
        "Se eu repetir este comportamento por 6 meses, qual o impacto no meu patrimonio?",
        "Qual ajuste simples teria o melhor efeito no meu aporte mensal?",
    ]
    for question in contextual_fillers:
        if len(deduped_dynamic) >= 4:
            break
        if question not in seen:
            deduped_dynamic.append(question)
            seen.add(question)

    return FIXED_SUGGESTED_QUESTIONS + deduped_dynamic[:4]


def submit_consultant_message(
    gemini_client,
    model_name: str,
    chat_key: str,
    prompt_text: str,
    full_prompt: str,
) -> None:
    with st.chat_message("user"):
        st.markdown(prompt_text)
    st.session_state[chat_key].append({"role": "user", "content": prompt_text})

    with st.chat_message("assistant"):
        with st.spinner("Analisando..."):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                st.markdown(sanitize_ai_response(response.text))
                st.session_state[chat_key].append({"role": "assistant", "content": response.text})
            except Exception as exc:
                st.error(f"Erro na IA: {exc}")


def render_page():
    cfg = st.session_state.get("cfg", {})
    transacoes_data = st.session_state.get("transacoes_data", {})
    mensal_data = st.session_state.get("mensal_data", {})
    goals_data = st.session_state.get("goals_data", [])
    category_budgets_data = st.session_state.get("category_budgets_data", {})
    perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
    gemini_client = get_gemini_client()

    all_meses = sorted(set(mensal_data.keys()) | set(transacoes_data.keys()), key=mes_sort_key)

    receita_base = float(cfg.get("Receita_Base", 0) or 0)
    meta_aporte = float(cfg.get("Meta_Aporte", 0) or 0)
    teto_gastos = float(cfg.get("Teto_Gastos", 0) or 0)
    dia_fechamento = int(cfg.get("Dia_Fechamento", 13))
    gemini_model = cfg.get("Gemini_Model", "gemini-2.5-flash")
    cartoes_aceitos = cfg.get("Cartoes_Aceitos")
    cartoes_excluidos = cfg.get("Cartoes_Excluidos")
    regras_ia = cfg.get("Regras_IA", "")

    st.markdown('<p class="section-header">Consultoria Financeira com IA</p>', unsafe_allow_html=True)

    if not all_meses:
        st.info("Nenhum mes cadastrado com dados para analise.")
        return

    mes_insight = st.selectbox(
        "Selecione o mes para a Consultoria",
        all_meses,
        index=len(all_meses) - 1,
        key="mes_insight_sel",
    )

    chat_key = f"chat_history_{mes_insight}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    history_snapshots = build_history_snapshots(
        all_meses,
        mensal_data,
        transacoes_data,
        perfil_ativo,
        teto_gastos,
        receita_base,
        meta_aporte,
        cartoes_aceitos,
        cartoes_excluidos,
        category_budgets_data,
    )
    snapshot_by_month = {snapshot["mes"]: snapshot for snapshot in history_snapshots}
    ordered_months = [snapshot["mes"] for snapshot in history_snapshots]
    current_snapshot = snapshot_by_month[mes_insight]
    previous_month = get_previous_month(mes_insight, ordered_months)
    previous_snapshot = snapshot_by_month.get(previous_month) if previous_month else None
    comparison = build_month_comparison(current_snapshot, previous_snapshot)

    default_prompt = (
        "Voce e um CFP (Certified Financial Planner) com especializacao em Behavioral Finance "
        "e 20 anos de experiencia com jovens profissionais de alta renda. Voce combina rigor analitico "
        "com empatia, sem mascarar diagnosticos.\n\n"
        "ESTILO DE COMUNICACAO:\n"
        "- Tom direto, sem ser frio\n"
        "- Use analogias do cotidiano quando ajudarem\n"
        "- Numeros sempre em R$ formatados\n"
        "- Markdown limpo\n\n"
        "ESTRUTURA DA ANALISE:\n\n"
        "## Diagnostico Financeiro\n"
        "- Avalie a saude do ciclo em uma frase-resumo\n"
        "- Explique comprometido vs teto e o quanto sobrou ou estourou\n"
        "- Explique a composicao de fixos vs variaveis\n\n"
        "## Raio-X dos Gastos Variaveis\n"
        "- Identifique os 3 maiores ralos\n"
        "- Classifique necessidade vs exagero\n"
        "- Se houver limites por categoria, diga onde estourou\n\n"
        "## Patrimonio\n"
        "- Avalie o savings rate do mes em foco\n"
        "- Compare aporte real vs meta\n"
        "- Projete impacto patrimonial se o padrao continuar\n\n"
        "## Metas de Longo Prazo\n"
        "- Avalie se o ritmo atual sustenta as metas\n\n"
        "## Prescricao\n"
        "- Liste exatamente 2 ou 3 acoes praticas\n"
        "- Cada acao deve dizer o que fazer, quanto economiza e o impacto no aporte"
    )

    with st.expander("Personalizar Prompt do Consultor", expanded=False):
        st.text_area(
            "Edite as diretrizes de avaliacao da IA:",
            value=default_prompt,
            height=300,
            key="master_prompt_area",
        )

    current_master = st.session_state.get("master_prompt_area", default_prompt)

    if not gemini_client:
        st.warning("API do Gemini nao configurada. Adicione GEMINI_API_KEY no secrets do Streamlit.")
        gerar_clicked = False
        copiar_clicked = st.button("Copiar Prompt", use_container_width=True)
    else:
        st.caption("Gere um diagnostico base ou converse livremente com a IA sobre o seu orcamento.")
        col_gerar, col_copiar = st.columns([3, 2])
        with col_gerar:
            gerar_clicked = st.button("Gerar Diagnostico Financeiro Completo", use_container_width=True)
        with col_copiar:
            copiar_clicked = st.button("Copiar Prompt", use_container_width=True)

    diagnostic_prompt = build_consultant_context(
        current_master,
        mes_insight,
        current_snapshot,
        history_snapshots,
        comparison,
        receita_base,
        meta_aporte,
        teto_gastos,
        dia_fechamento,
        goals_data,
        regras_ia,
        conversation_history=_build_conversation_history(st.session_state[chat_key]),
        mode="diagnostic",
    )

    if gerar_clicked:
        st.session_state[chat_key].append(
            {"role": "user", "content": "*(Solicitou Geracao do Diagnostico Financeiro Completo)*"}
        )
        with st.spinner("Elaborando diagnostico minucioso..."):
            try:
                response = gemini_client.models.generate_content(
                    model=gemini_model,
                    contents=diagnostic_prompt,
                )
                st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as exc:
                st.error(f"Erro na geracao do relatorio: {exc}")

    if copiar_clicked:
        st.session_state[f"claude_prompt_{mes_insight}"] = diagnostic_prompt

    claude_prompt_key = f"claude_prompt_{mes_insight}"
    if claude_prompt_key in st.session_state:
        st.caption(
            "Clique no icone de copia no canto do bloco abaixo, depois cole em qualquer assistente "
            "de IA externo para obter uma analise adicional."
        )
        st.code(st.session_state[claude_prompt_key], language=None)

    if not gemini_client:
        return

    st.markdown("---")
    st.caption("Perguntas sugeridas")
    suggested_questions = get_suggested_questions(current_snapshot, comparison, history_snapshots, goals_data)
    selected_prompt = None
    for row_start in range(0, len(suggested_questions), 4):
        columns = st.columns(4)
        for idx, question in enumerate(suggested_questions[row_start : row_start + 4]):
            with columns[idx]:
                if st.button(
                    question,
                    key=f"suggested_question_{mes_insight}_{row_start + idx}",
                    use_container_width=True,
                ):
                    selected_prompt = question

    for message in st.session_state[chat_key]:
        with st.chat_message(message["role"]):
            st.markdown(sanitize_ai_response(message["content"]))

    typed_prompt = st.chat_input("Pergunte algo ao seu consultor financeiro...")
    prompt_text = selected_prompt or typed_prompt

    if prompt_text:
        conversation_history = _build_conversation_history(st.session_state[chat_key])
        full_prompt = build_consultant_context(
            current_master,
            mes_insight,
            current_snapshot,
            history_snapshots,
            comparison,
            receita_base,
            meta_aporte,
            teto_gastos,
            dia_fechamento,
            goals_data,
            regras_ia,
            conversation_history=conversation_history,
            user_message=prompt_text,
            mode="chat",
        )
        submit_consultant_message(
            gemini_client,
            gemini_model,
            chat_key,
            prompt_text,
            full_prompt,
        )
