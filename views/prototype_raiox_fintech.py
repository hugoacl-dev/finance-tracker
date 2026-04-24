import html
import statistics

import pandas as pd
import streamlit as st

from core.utils import mes_sort_key
from services.data_engine import calcular_score_financeiro, processar_mes
from services.local_adapter import LocalDataService


def _money(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {formatted}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _escape(value: object) -> str:
    return html.escape(str(value))


def _inject_styles() -> None:
    st.html(
        """
        <style>
        .proto-raiox-shell {
            --proto-bg: #F5F6F1;
            --proto-surface: #FFFFFF;
            --proto-surface-soft: #EFF3EC;
            --proto-text: #171A1F;
            --proto-muted: #697386;
            --proto-border: rgba(20, 27, 34, 0.10);
            --proto-green: #087F5B;
            --proto-green-2: #12B886;
            --proto-blue: #245B7A;
            --proto-amber: #B7791F;
            --proto-red: #B42318;
            --proto-ink: #101418;
            color: var(--proto-text);
            font-variant-numeric: tabular-nums lining-nums;
            max-width: 100%;
            overflow-x: hidden;
        }

        .proto-raiox-shell * {
            box-sizing: border-box;
            min-width: 0;
        }

        .proto-raiox-stage {
            display: grid;
            gap: 1rem;
            padding: 0.25rem 0 1rem;
        }

        .proto-raiox-topline {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
            align-items: center;
            color: var(--proto-muted);
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0;
        }

        .proto-raiox-kicker,
        .proto-raiox-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid var(--proto-border);
            border-radius: 999px;
            padding: 0.3rem 0.65rem;
            background: rgba(255,255,255,0.72);
            color: var(--proto-muted);
            white-space: normal;
        }

        .proto-raiox-hero {
            border: 1px solid var(--proto-border);
            border-radius: 18px;
            background: var(--proto-surface);
            box-shadow: 0 16px 42px rgba(16, 24, 40, 0.08);
            overflow: hidden;
        }

        .proto-raiox-hero-inner {
            display: grid;
            gap: 1rem;
            padding: clamp(1rem, 4vw, 1.55rem);
        }

        .proto-raiox-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }

        .proto-raiox-grid-2 {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1rem;
        }

        .proto-raiox-title {
            margin: 0;
            color: var(--proto-text);
            font-size: clamp(1.6rem, 7vw, 3.4rem);
            line-height: 1.02;
            font-weight: 850;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }

        .proto-raiox-headline-value {
            margin: 0.35rem 0 0;
            color: var(--proto-green);
            font-size: clamp(2.15rem, 12vw, 4.5rem);
            line-height: 0.98;
            font-weight: 900;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }

        .proto-raiox-copy {
            margin: 0.55rem 0 0;
            color: var(--proto-muted);
            font-size: 0.98rem;
            line-height: 1.5;
            max-width: 62ch;
            overflow-wrap: anywhere;
        }

        .proto-raiox-card,
        .proto-raiox-panel,
        .proto-raiox-mini {
            border: 1px solid var(--proto-border);
            border-radius: 16px;
            background: var(--proto-surface);
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.05);
        }

        .proto-raiox-card {
            padding: 0.95rem;
        }

        .proto-raiox-panel {
            padding: 1rem;
        }

        .proto-raiox-label {
            color: var(--proto-muted);
            font-size: 0.76rem;
            font-weight: 800;
            margin-bottom: 0.28rem;
        }

        .proto-raiox-value {
            color: var(--proto-text);
            font-size: clamp(1.1rem, 5vw, 1.75rem);
            font-weight: 850;
            line-height: 1.1;
        }

        .proto-raiox-delta {
            color: var(--proto-muted);
            font-size: 0.78rem;
            margin-top: 0.35rem;
            line-height: 1.35;
        }

        .proto-raiox-section-title {
            margin: 1.1rem 0 0.55rem;
            color: var(--proto-muted);
            font-size: 0.88rem;
            font-weight: 850;
            letter-spacing: 0;
        }

        .proto-raiox-bar {
            height: 12px;
            border-radius: 999px;
            background: #E5E8DF;
            overflow: hidden;
        }

        .proto-raiox-bar > span {
            display: block;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--proto-green), var(--proto-green-2));
        }

        .proto-raiox-bar.is-alert > span {
            background: linear-gradient(90deg, var(--proto-amber), #F59E0B);
        }

        .proto-raiox-bar.is-danger > span {
            background: linear-gradient(90deg, var(--proto-red), #EF4444);
        }

        .proto-raiox-row {
            display: grid;
            gap: 0.4rem;
            padding: 0.72rem 0;
            border-bottom: 1px solid var(--proto-border);
        }

        .proto-raiox-row:last-child {
            border-bottom: 0;
        }

        .proto-raiox-row-head {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 0.75rem;
            color: var(--proto-text);
            font-size: 0.9rem;
            font-weight: 800;
        }

        .proto-raiox-row-meta {
            color: var(--proto-muted);
            font-size: 0.78rem;
            line-height: 1.35;
        }

        .proto-raiox-status-good {
            color: var(--proto-green);
        }

        .proto-raiox-status-warn {
            color: var(--proto-amber);
        }

        .proto-raiox-status-danger {
            color: var(--proto-red);
        }

        .proto-raiox-impact .proto-raiox-hero {
            background:
                linear-gradient(135deg, rgba(18, 184, 134, 0.18), rgba(36, 91, 122, 0.12)),
                #111814;
            color: #F8FAF7;
            border-color: rgba(255,255,255,0.10);
        }

        .proto-raiox-impact .proto-raiox-title,
        .proto-raiox-impact .proto-raiox-headline-value,
        .proto-raiox-impact .proto-raiox-copy {
            color: #F8FAF7;
        }

        .proto-raiox-impact .proto-raiox-headline-value {
            color: #63E6BE;
        }

        .proto-raiox-impact .proto-raiox-mini {
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.12);
            padding: 0.9rem;
        }

        .proto-raiox-impact .proto-raiox-label,
        .proto-raiox-impact .proto-raiox-delta {
            color: rgba(248,250,247,0.72);
        }

        .proto-raiox-impact .proto-raiox-value {
            color: #FFFFFF;
        }

        .proto-raiox-minimal .proto-raiox-hero,
        .proto-raiox-minimal .proto-raiox-card,
        .proto-raiox-minimal .proto-raiox-panel {
            box-shadow: none;
            border-radius: 10px;
        }

        .proto-raiox-step {
            display: grid;
            grid-template-columns: 2.25rem minmax(0, 1fr);
            gap: 0.8rem;
            padding: 0.9rem 0;
            border-bottom: 1px solid var(--proto-border);
        }

        .proto-raiox-step:last-child {
            border-bottom: 0;
        }

        .proto-raiox-step-number {
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 999px;
            display: grid;
            place-items: center;
            background: var(--proto-surface-soft);
            color: var(--proto-green);
            font-weight: 900;
        }

        .proto-raiox-list {
            display: grid;
            gap: 0.65rem;
        }

        .proto-raiox-tx {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--proto-border);
            font-size: 0.88rem;
        }

        .proto-raiox-tx:last-child {
            border-bottom: 0;
        }

        .proto-raiox-tx strong,
        .proto-raiox-tx span {
            min-width: 0;
        }

        @media (min-width: 781px) {
            .proto-raiox-topline {
                display: flex;
                justify-content: space-between;
            }

            .proto-raiox-pill {
                white-space: nowrap;
            }

            .proto-raiox-grid {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }

            .proto-raiox-grid-2 {
                grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
            }
        }

        @media (max-width: 780px) {
            .proto-raiox-card {
                padding: 0.85rem;
            }

            .proto-raiox-row-head,
            .proto-raiox-tx {
                align-items: flex-start;
                flex-direction: column;
            }
        }
        </style>
        """
    )


def _build_context() -> dict:
    service = LocalDataService()
    perfil = "Principal"
    cfg = service.get_profile_config(perfil)
    mensal_data = service.get_mensal_data(perfil)
    transacoes_data = service.get_transacoes_data(perfil)
    budgets = service.get_category_budgets(perfil)
    meses = sorted(set(mensal_data) | set(transacoes_data), key=mes_sort_key)
    mes = meses[-1]

    df_c = pd.DataFrame(mensal_data.get(mes, []))
    df_o = pd.DataFrame(transacoes_data.get(mes, []))
    r = processar_mes(
        df_c,
        df_o,
        perfil,
        cfg.get("Teto_Gastos", 0),
        cfg.get("Receita_Base", 0),
        cfg.get("Meta_Aporte", 0),
        cfg.get("Cartoes_Aceitos"),
        cfg.get("Cartoes_Excluidos"),
    )

    receita = float(cfg.get("Receita_Base", 0) or 0)
    savings_rate = (r["aporte_real"] / receita * 100) if receita > 0 else 0
    sr_history = []
    for m in meses[-6:]:
        rm = processar_mes(
            pd.DataFrame(mensal_data.get(m, [])),
            pd.DataFrame(transacoes_data.get(m, [])),
            perfil,
            cfg.get("Teto_Gastos", 0),
            receita,
            cfg.get("Meta_Aporte", 0),
            cfg.get("Cartoes_Aceitos"),
            cfg.get("Cartoes_Excluidos"),
        )
        sr_history.append((rm["aporte_real"] / receita * 100) if receita > 0 else 0)
    std_sr = statistics.stdev(sr_history) if len(sr_history) > 1 else 0

    qtd_outros = 0
    total_ops = 0
    if not r["df_ops"].empty and "Categoria" in r["df_ops"].columns:
        df_debitos = r["df_ops"][r["df_ops"].get("Tipo", "debito") != "credito"]
        total_ops = len(df_debitos)
        qtd_outros = len(df_debitos[df_debitos["Categoria"] == "Outros"])
    pct_nao_class = (qtd_outros / total_ops * 100) if total_ops else 0
    score = calcular_score_financeiro(
        savings_rate=savings_rate,
        pct_teto=r["pct_teto"],
        meta_batida=not r["meta_ameacada"],
        consistencia_std=std_sr,
        pct_nao_classificados=pct_nao_class,
    )

    df_debitos = pd.DataFrame()
    if not r["df_ops"].empty:
        df_debitos = r["df_ops"].copy()
        if "Tipo" in df_debitos.columns:
            df_debitos = df_debitos[df_debitos["Tipo"] != "credito"]
    categorias = []
    if not df_debitos.empty and "Categoria" in df_debitos.columns:
        df_cat = (
            df_debitos.groupby("Categoria", as_index=False)["Valor"]
            .sum()
            .sort_values("Valor", ascending=False)
        )
        total_cat = float(df_cat["Valor"].sum())
        for _, row in df_cat.iterrows():
            categoria = str(row["Categoria"])
            valor = float(row["Valor"])
            limite = float(budgets.get(categoria, 0) or 0)
            pct_limite = (valor / limite * 100) if limite > 0 else 0
            categorias.append(
                {
                    "categoria": categoria,
                    "valor": valor,
                    "share": (valor / total_cat * 100) if total_cat else 0,
                    "limite": limite,
                    "pct_limite": pct_limite,
                }
            )

    pendentes = []
    if not r["df_config"].empty and "Tipo" in r["df_config"].columns:
        df_cartao = r["df_config"][r["df_config"]["Tipo"].astype(str).str.lower() == "cartao"]
        if "Status_Conciliacao" in df_cartao.columns:
            pendentes = df_cartao[df_cartao["Status_Conciliacao"] != "✅ Confirmado"].to_dict("records")

    return {
        "perfil": perfil,
        "cfg": cfg,
        "mes": mes,
        "resultado": r,
        "score": score,
        "savings_rate": savings_rate,
        "categorias": categorias,
        "pendentes": pendentes,
        "transacoes": df_debitos.head(6).to_dict("records") if not df_debitos.empty else [],
    }


def _hero_copy(ctx: dict) -> tuple[str, str, str]:
    r = ctx["resultado"]
    mes = ctx["mes"]
    if r["saldo_teto"] >= 0:
        return (
            f"Ciclo {mes} encerrado com folga",
            _money(r["saldo_teto"]),
            "O teto foi respeitado e o aporte ficou preservado. O foco agora é entender o que mais puxou o consumo.",
        )
    return (
        f"Ciclo {mes} acima do teto",
        _money(abs(r["saldo_teto"])),
        "O ciclo fechou acima do planejado. Priorize categorias fora da curva e despesas recorrentes.",
    )


def _score_badge(score: dict) -> str:
    cls = "proto-raiox-status-good"
    if score["score"] < 70:
        cls = "proto-raiox-status-warn"
    if score["score"] < 50:
        cls = "proto-raiox-status-danger"
    return f'<span class="proto-raiox-pill {cls}">Score {score["score"]}/100 · {_escape(score["label"])}</span>'


def _metric(label: str, value: str, detail: str = "") -> str:
    return f"""
    <div class="proto-raiox-card">
        <div class="proto-raiox-label">{_escape(label)}</div>
        <div class="proto-raiox-value">{_escape(value)}</div>
        <div class="proto-raiox-delta">{_escape(detail)}</div>
    </div>
    """


def _bar_row(label: str, value: float, pct: float, meta: str = "") -> str:
    danger_cls = " is-danger" if pct >= 100 else (" is-alert" if pct >= 80 else "")
    return f"""
    <div class="proto-raiox-row">
        <div class="proto-raiox-row-head">
            <span>{_escape(label)}</span>
            <span>{_money(value)}</span>
        </div>
        <div class="proto-raiox-bar{danger_cls}"><span style="width:{min(pct, 100):.1f}%"></span></div>
        <div class="proto-raiox-row-meta">{_pct(pct)}{_escape(meta)}</div>
    </div>
    """


def _category_rows(ctx: dict, use_limit: bool = False) -> str:
    rows = []
    categorias = ctx["categorias"][:6]
    if use_limit:
        categorias = sorted(ctx["categorias"], key=lambda item: item["pct_limite"], reverse=True)[:6]
    for cat in categorias:
        pct = cat["pct_limite"] if use_limit and cat["limite"] > 0 else cat["share"]
        meta = f" do limite de {_money(cat['limite'])}" if use_limit and cat["limite"] > 0 else " dos variáveis"
        rows.append(_bar_row(cat["categoria"], cat["valor"], pct, meta))
    return "\n".join(rows)


def _render_tx_list(ctx: dict) -> str:
    rows = []
    for tx in ctx["transacoes"]:
        rows.append(
            f"""
            <div class="proto-raiox-tx">
                <strong>{_escape(tx.get("Descricao", ""))}</strong>
                <span>{_escape(tx.get("Categoria", "Outros"))} · {_money(float(tx.get("Valor", 0) or 0))}</span>
            </div>
            """
        )
    return "\n".join(rows)


def _render_premium(ctx: dict) -> None:
    r = ctx["resultado"]
    cfg = ctx["cfg"]
    title, value, copy = _hero_copy(ctx)
    st.html(
        f"""
        <div class="proto-raiox-shell proto-raiox-premium">
            <div class="proto-raiox-stage">
                <div class="proto-raiox-topline">
                    <span class="proto-raiox-kicker">Premium sóbria · protótipo</span>
                    <span class="proto-raiox-pill">Perfil {ctx["perfil"]} · Ciclo {ctx["mes"]}</span>
                </div>
                <div class="proto-raiox-hero">
                    <div class="proto-raiox-hero-inner">
                        <div>{_score_badge(ctx["score"])}</div>
                        <div>
                            <div class="proto-raiox-title">{_escape(title)}</div>
                            <p class="proto-raiox-headline-value">{_escape(value)}</p>
                            <p class="proto-raiox-copy">{_escape(copy)}</p>
                        </div>
                        <div class="proto-raiox-grid">
                            {_metric("Gasto total", _money(r["total_comprometido"]), f'{_pct(r["pct_teto"])} do teto')}
                            {_metric("Variáveis", _money(r["total_variaveis"]), "Após deduplicar fixos")}
                            {_metric("Aporte", _money(r["aporte_real"]), f'Savings rate {_pct(ctx["savings_rate"])}')}
                            {_metric("Meta", _money(cfg["Meta_Aporte"]), "Referência do ciclo")}
                        </div>
                    </div>
                </div>
                <div class="proto-raiox-grid-2">
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Gastos por categoria</div>
                        {_category_rows(ctx)}
                    </div>
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Categorias em atencao</div>
                        {_category_rows(ctx, use_limit=True)}
                    </div>
                </div>
                <div class="proto-raiox-grid-2">
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Conferencia do ciclo</div>
                        {_bar_row("Consumo do teto", r["total_comprometido"], r["pct_teto"], f' de {_money(cfg["Teto_Gastos"])}')}
                        {_bar_row("Fixos", r["total_fixos"], (r["total_fixos"] / cfg["Teto_Gastos"] * 100), " do teto")}
                    </div>
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Lançamentos recentes</div>
                        {_render_tx_list(ctx)}
                    </div>
                </div>
            </div>
        </div>
        """
    )


def _render_impact(ctx: dict) -> None:
    r = ctx["resultado"]
    cfg = ctx["cfg"]
    title, value, copy = _hero_copy(ctx)
    top_cat = ctx["categorias"][0] if ctx["categorias"] else {"categoria": "Sem categoria", "valor": 0, "share": 0}
    pending_text = f"{len(ctx['pendentes'])} fixo pendente" if ctx["pendentes"] else "Fixos conciliados"
    st.html(
        f"""
        <div class="proto-raiox-shell proto-raiox-impact">
            <div class="proto-raiox-stage">
                <div class="proto-raiox-topline">
                    <span class="proto-raiox-kicker">Impactante visual · protótipo</span>
                    <span class="proto-raiox-pill">Abrir, entender, agir</span>
                </div>
                <div class="proto-raiox-hero">
                    <div class="proto-raiox-hero-inner">
                        <div class="proto-raiox-grid-2">
                            <div>
                                <div class="proto-raiox-title">{_escape(title)}</div>
                                <p class="proto-raiox-headline-value">{_escape(value)}</p>
                                <p class="proto-raiox-copy">{_escape(copy)}</p>
                            </div>
                            <div class="proto-raiox-list">
                                <div class="proto-raiox-mini">
                                    <div class="proto-raiox-label">Saúde financeira</div>
                                    <div class="proto-raiox-value">{ctx["score"]["score"]}/100</div>
                                    <div class="proto-raiox-delta">{_escape(ctx["score"]["label"])}</div>
                                </div>
                                <div class="proto-raiox-mini">
                                    <div class="proto-raiox-label">Maior categoria</div>
                                    <div class="proto-raiox-value">{_escape(top_cat["categoria"])}</div>
                                    <div class="proto-raiox-delta">{_money(top_cat["valor"])} · {_pct(top_cat["share"])} dos variáveis</div>
                                </div>
                                <div class="proto-raiox-mini">
                                    <div class="proto-raiox-label">Revisão</div>
                                    <div class="proto-raiox-value">{_escape(pending_text)}</div>
                                    <div class="proto-raiox-delta">Antes de tomar decisão final</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="proto-raiox-grid">
                    {_metric("Teto usado", _pct(r["pct_teto"]), f'{_money(r["total_comprometido"])} de {_money(cfg["Teto_Gastos"])}')}
                    {_metric("Folga", _money(r["saldo_teto"]), "Contra o teto do ciclo")}
                    {_metric("Aporte", _money(r["aporte_real"]), f'Meta {_money(cfg["Meta_Aporte"])}')}
                    {_metric("Savings rate", _pct(ctx["savings_rate"]), "Resultado do ciclo")}
                </div>
                <div class="proto-raiox-grid-2">
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">O que mais moveu o ciclo</div>
                        {_category_rows(ctx)}
                    </div>
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Riscos e limites</div>
                        {_category_rows(ctx, use_limit=True)}
                    </div>
                </div>
                <div class="proto-raiox-panel">
                    <div class="proto-raiox-section-title">Extrato essencial</div>
                    {_render_tx_list(ctx)}
                </div>
            </div>
        </div>
        """
    )


def _render_minimal(ctx: dict) -> None:
    r = ctx["resultado"]
    cfg = ctx["cfg"]
    title, value, copy = _hero_copy(ctx)
    top_cat = ctx["categorias"][0] if ctx["categorias"] else {"categoria": "Sem categoria", "valor": 0, "share": 0}
    st.html(
        f"""
        <div class="proto-raiox-shell proto-raiox-minimal">
            <div class="proto-raiox-stage">
                <div class="proto-raiox-topline">
                    <span class="proto-raiox-kicker">Minimalista extrema · protótipo</span>
                    <span class="proto-raiox-pill">Ciclo {ctx["mes"]}</span>
                </div>
                <div class="proto-raiox-hero">
                    <div class="proto-raiox-hero-inner">
                        <div class="proto-raiox-title">{_escape(title)}</div>
                        <p class="proto-raiox-headline-value">{_escape(value)}</p>
                        <p class="proto-raiox-copy">{_escape(copy)}</p>
                    </div>
                </div>
                <div class="proto-raiox-panel">
                    <div class="proto-raiox-step">
                        <div class="proto-raiox-step-number">1</div>
                        <div>
                            <div class="proto-raiox-row-head"><span>Resultado</span><span>{_money(r["saldo_teto"])}</span></div>
                            <div class="proto-raiox-row-meta">Saldo contra o teto de {_money(cfg["Teto_Gastos"])}.</div>
                        </div>
                    </div>
                    <div class="proto-raiox-step">
                        <div class="proto-raiox-step-number">2</div>
                        <div>
                            <div class="proto-raiox-row-head"><span>Principal causa</span><span>{_escape(top_cat["categoria"])}</span></div>
                            <div class="proto-raiox-row-meta">{_money(top_cat["valor"])} em gastos variáveis, {_pct(top_cat["share"])} do total.</div>
                        </div>
                    </div>
                    <div class="proto-raiox-step">
                        <div class="proto-raiox-step-number">3</div>
                        <div>
                            <div class="proto-raiox-row-head"><span>Saúde financeira</span><span>{ctx["score"]["score"]}/100</span></div>
                            <div class="proto-raiox-row-meta">{_escape(ctx["score"]["label"])} · savings rate de {_pct(ctx["savings_rate"])}.</div>
                        </div>
                    </div>
                    <div class="proto-raiox-step">
                        <div class="proto-raiox-step-number">4</div>
                        <div>
                            <div class="proto-raiox-row-head"><span>Próxima revisão</span><span>{len(ctx["pendentes"])} pendente(s)</span></div>
                            <div class="proto-raiox-row-meta">Checar fixos de cartão e lançamentos recentes antes de encerrar a análise.</div>
                        </div>
                    </div>
                </div>
                <div class="proto-raiox-grid-2">
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Categorias</div>
                        {_category_rows(ctx)}
                    </div>
                    <div class="proto-raiox-panel">
                        <div class="proto-raiox-section-title">Lançamentos</div>
                        {_render_tx_list(ctx)}
                    </div>
                </div>
            </div>
        </div>
        """
    )


def render_page() -> None:
    _inject_styles()
    ctx = _build_context()

    st.caption("Protótipo isolado · não usa Supabase · não altera a Raio-X atual")
    variant = st.radio(
        "Direção visual",
        ["Premium sóbria", "Impactante visual", "Minimalista extrema"],
        horizontal=True,
        key="proto_raiox_variant",
    )

    if variant == "Premium sóbria":
        _render_premium(ctx)
    elif variant == "Impactante visual":
        _render_impact(ctx)
    else:
        _render_minimal(ctx)
