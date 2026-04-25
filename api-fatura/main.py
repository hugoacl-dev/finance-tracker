"""
API de importação de faturas via imagem.
Recebe fotos de faturas do iPhone (via Atalho iOS), extrai transações
com Gemini Vision, classifica categorias e insere no Supabase.
"""

import os
import re
import json
import math
import difflib
import unicodedata
from datetime import date, datetime, timezone
from typing import Optional

import logging

from fastapi import FastAPI, UploadFile, File, Header, HTTPException, BackgroundTasks
from supabase import create_client, Client
from google import genai
from google.genai import types
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="API Fatura", version="1.0.0")

# ── Clients ──

def get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_gemini() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])

API_TOKEN = os.environ.get("API_TOKEN", "")

# ── Helpers ──

def normalize_text(t: Optional[str]) -> str:
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", str(t)).encode("ASCII", "ignore").decode("ASCII")
    return "".join(c for c in t if c.isalnum()).upper()


def get_profile_id(supabase: Client, profile_name: str) -> str:
    result = supabase.table("profiles").select("id").eq("name", profile_name).execute()
    if not result.data:
        raise ValueError(f"Perfil '{profile_name}' não encontrado")
    return result.data[0]["id"]


def get_regras_ia(supabase: Client, profile_name: str) -> str:
    result = supabase.table("profiles").select("regras_ia").eq("name", profile_name).execute()
    if result.data and result.data[0].get("regras_ia"):
        return result.data[0]["regras_ia"]
    return ""


def get_gemini_models(supabase: Client, profile_name: str) -> tuple[str, str]:
    result = (
        supabase.table("profiles")
        .select("gemini_model, gemini_vision_model")
        .eq("name", profile_name)
        .execute()
    )
    if result.data:
        row = result.data[0]
        return (
            row.get("gemini_model") or "gemini-2.5-flash",
            row.get("gemini_vision_model") or "gemini-2.0-flash",
        )
    return "gemini-2.5-flash", "gemini-2.0-flash"


PADRAO_PARCELADO = re.compile(r"\d{2}\s+\d{2}$")


def _is_rotativo(descricao: str) -> bool:
    """Retorna True se a transação é parcelada/rotativa (descrição termina em 'XX YY')."""
    return bool(PADRAO_PARCELADO.search(descricao.strip()))


def inferir_ciclo(transacoes: list[dict], supabase: Client) -> str:
    """Infere o ciclo a partir das datas dos lançamentos e busca o formato existente no banco.

    Transações parceladas/rotativas (descrição termina em 'XX YY') são ignoradas
    na inferência do ciclo — elas entram no ciclo inferido pelas demais transações.

    Regra: dia <= 15 → mês corrente, dia >= 16 → mês seguinte.
    Formato: busca ciclo existente no banco. Se não existir, usa MM/AA.
    """
    padrao = re.compile(r"(\d{2})/(\d{2})")
    max_dia = 0
    max_mes = 0

    for t in transacoes:
        desc = t.get("Descricao", "")
        if _is_rotativo(desc):
            continue
        m = padrao.search(desc)
        if m:
            dia, mes = int(m.group(1)), int(m.group(2))
            if mes > max_mes or (mes == max_mes and dia > max_dia):
                max_dia = dia
                max_mes = mes

    if max_mes == 0:
        hoje = date.today()
        try:
            result = supabase.table("profiles").select("dia_fechamento").execute()
            dia_fechamento = result.data[0]["dia_fechamento"] if result.data else 13
        except Exception:
            dia_fechamento = 13
        if hoje.day > dia_fechamento:
            target_mes = hoje.month + 1
            target_ano = hoje.year
            if target_mes > 12:
                target_mes = 1
                target_ano += 1
        else:
            target_mes = hoje.month
            target_ano = hoje.year
    elif max_dia >= 16:
        target_mes = max_mes + 1
        target_ano = date.today().year
        if target_mes > 12:
            target_mes = 1
            target_ano += 1
    else:
        target_mes = max_mes
        target_ano = date.today().year

    # Buscar ciclo existente no banco que corresponda a esse mês/ano
    return _encontrar_ciclo_existente(supabase, target_mes, target_ano)


MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

def _encontrar_ciclo_existente(supabase: Client, mes: int, ano: int) -> str:
    """Busca no banco um ciclo que corresponda ao mês/ano. Se não existir, gera no formato MM/AA."""
    # Buscar todos os meses distintos
    result = supabase.table("transacoes").select("mes").execute()
    result2 = supabase.table("gastos_fixos").select("mes").execute()

    todos_meses = set()
    for r in result.data:
        todos_meses.add(r["mes"])
    for r in result2.data:
        todos_meses.add(r["mes"])

    ano_2d = str(ano)[2:]  # ex: "26"
    nome_mes = MESES_PT.get(mes, "")

    # Possíveis formatos a procurar
    candidatos = [
        f"{mes:02d}/{ano_2d}",          # "03/26"
        f"{mes:02d}/{ano}",             # "03/2026"
        f"{nome_mes} {ano_2d}",         # "Março 26"
        f"{nome_mes} {ano}",            # "Março 2026"
    ]

    for candidato in candidatos:
        if candidato in todos_meses:
            return candidato

    # Se não existe, criar no formato padrão MM/AA
    return f"{mes:02d}/{ano_2d}"


MESES_PT_REVERSE = {v: k for k, v in MESES_PT.items()}


def _parse_ciclo(ciclo: str) -> tuple[int, int] | None:
    """Parse cycle string to (month, year). Returns None if unparseable."""
    m = re.match(r"(\d{2})/(\d{2,4})$", ciclo)
    if m:
        mes, ano = int(m.group(1)), int(m.group(2))
        if ano < 100:
            ano += 2000
        return (mes, ano)

    parts = ciclo.rsplit(" ", 1)
    if len(parts) == 2 and parts[0] in MESES_PT_REVERSE:
        try:
            ano = int(parts[1])
            if ano < 100:
                ano += 2000
            return (MESES_PT_REVERSE[parts[0]], ano)
        except ValueError:
            pass

    return None


def _copiar_gastos_fixos_se_necessario(supabase: Client, novo_ciclo: str):
    """Se o ciclo não tem gastos fixos, copia do ciclo mais recente."""
    check = supabase.table("gastos_fixos").select("id").eq("mes", novo_ciclo).limit(1).execute()
    if check.data:
        return

    result = supabase.table("gastos_fixos").select(
        "mes, profile_id, descricao_fatura, valor, tipo, status_conciliacao"
    ).execute()
    if not result.data:
        logger.info("Nenhum gasto fixo encontrado para copiar")
        return

    meses = set(r["mes"] for r in result.data)
    parsed = [(p, m) for m in meses if (p := _parse_ciclo(m))]
    if not parsed:
        return

    parsed.sort(key=lambda x: (x[0][1], x[0][0]), reverse=True)
    ciclo_anterior = parsed[0][1]

    anteriores = [r for r in result.data if r["mes"] == ciclo_anterior]
    records = [{
        "profile_id": g["profile_id"],
        "mes": novo_ciclo,
        "descricao_fatura": g["descricao_fatura"],
        "valor": float(g["valor"]),
        "tipo": g["tipo"],
        "status_conciliacao": g.get("status_conciliacao"),
    } for g in anteriores]

    supabase.table("gastos_fixos").insert(records).execute()
    logger.info(f"Copiados {len(records)} gastos fixos de '{ciclo_anterior}' para '{novo_ciclo}'")


def rotear_perfil(titular: str) -> str:
    tit = titular.upper()
    if "LAR" in tit or "DEP" in tit:
        return "Dependente"
    return "Principal"


def _match_cross_imagem(t: dict, vistas: list[dict]) -> bool:
    """Verifica se a transação t é duplicata de alguma em vistas (cross-image).

    Critério conservador: mesmo cartão + mesmo tipo + descrição >= 80% similar + valor exato.
    Não usa tolerância de valor para não eliminar transações legítimas com valores próximos.
    """
    c = str(t.get("Cartao", "")).strip()
    c = c.zfill(4) if c.isdigit() else c
    d = normalize_text(str(t.get("Descricao", "")))
    v = float(t.get("Valor", 0))
    tipo = t.get("Tipo", "debito")

    for s in vistas:
        s_c = str(s.get("Cartao", "")).strip()
        s_c = s_c.zfill(4) if s_c.isdigit() else s_c
        if c != s_c:
            continue
        if tipo != s.get("Tipo", "debito"):
            continue
        s_d = normalize_text(str(s.get("Descricao", "")))
        s_v = float(s.get("Valor", 0))
        sim = difflib.SequenceMatcher(None, d, s_d).ratio()
        if sim >= 0.80 and abs(v - s_v) == 0:
            return True
    return False


def dedup_transacoes(
    novas: list[dict], existentes_por_perfil: dict[str, list[dict]]
) -> tuple[list[dict], list[dict]]:
    """Executa 3 passes de dedup contra o banco. Retorna (novos, ignorados)."""

    buffers = {
        perfil: [dict(t) for t in trans]
        for perfil, trans in existentes_por_perfil.items()
    }

    for t in novas:
        t["is_dupe"] = False

    def pass_dedup(trans_lista, bufs, match_fn):
        for t in trans_lista:
            if t.get("is_dupe"):
                continue
            c = str(t.get("Cartao", "")).strip()
            c = c.zfill(4) if c.isdigit() else c
            d = str(t.get("Descricao", "")).strip()
            v = float(t.get("Valor", 0))
            tipo = t.get("Tipo", "debito")
            prof = t["dest_profile"]

            for idx, e in enumerate(bufs.get(prof, [])):
                e_c = str(e.get("Cartao", "")).strip()
                e_c = e_c.zfill(4) if e_c.isdigit() else e_c
                if c != e_c:
                    continue
                # Tipo deve ser igual: débito ≠ crédito (estorno ≠ compra)
                if tipo != e.get("Tipo", "debito"):
                    continue
                e_d = str(e.get("Descricao", "")).strip()
                e_v = float(e.get("Valor", 0))
                similarity = difflib.SequenceMatcher(
                    None, normalize_text(d), normalize_text(e_d)
                ).ratio()
                price_diff = abs(v - e_v)
                if match_fn(similarity, price_diff, v):
                    t["is_dupe"] = True
                    bufs[prof].pop(idx)
                    break

    # Pass 1: match exato
    pass_dedup(novas, buffers, lambda s, p, v: s == 1.0 and p == 0)
    # Pass 2: descricao >= 80% similar, valor exato
    pass_dedup(novas, buffers, lambda s, p, v: s >= 0.80 and p == 0)
    # Pass 3: descricao >= 90% similar, tolerância dependente do valor
    #   > R$5 → até ±0,50 (absorve erros de OCR em decimais de valores maiores)
    #   ≤ R$5 → exato (evita false-positive em pequenos créditos como IOF)
    pass_dedup(novas, buffers, lambda s, p, v: s >= 0.90 and p <= (0.50 if v > 5.0 else 0.0))

    novos = []
    ignorados = []
    for t in novas:
        item = {
            "Descricao": str(t.get("Descricao", "")).strip(),
            "Valor": float(t.get("Valor", 0)),
            "Cartao": str(t.get("Cartao", "")).strip(),
            "Titular": t.get("Titular", "Sistema"),
            "Categoria": t.get("Categoria", "Outros"),
            "dest_profile": t["dest_profile"],
        }
        c = item["Cartao"]
        item["Cartao"] = c.zfill(4) if c.isdigit() else c

        item["Tipo"] = t.get("Tipo", "debito")

        if t["is_dupe"]:
            ignorados.append(item)
        else:
            novos.append(item)

    return novos, ignorados


# ── Gemini: OCR ──

PROMPT_OCR = """Você é um extrator de dados financeiros impiedosamente preciso.
Leia a imagem anexada (fatura de cartão) e extraia TODOS os lançamentos com valor monetário: compras, tarifas, anuidades, encargos, parcelas, estornos, créditos e quaisquer outros lançamentos.
Pule apenas totais, subtotais, cabeçalhos e linhas sem valor monetário.

[REGRA DE TITULAR E CARTÃO]
Faturas bancárias geralmente dividem os blocos por titular. Ex: 'Final XXXX - NOME DO TITULAR'.
Você deve cruzar os dados visuais e injetar o número do CARTÃO (os 4 dígitos finais) e o TITULAR correto em cada transação lida naquele bloco.
Se não encontrar o nome do titular exposto no cabeçalho do bloco, use "Principal".
Extraia nas transações apenas dia e mês (ex: 12/02), eliminando o ano.
Extraia a data agregada (ex: 12/02) DENTRO DA DESCRICAO para ficar "12/02 DESCRICAO".

[REGRA DE TIPO]
Cada lançamento é débito (gasto) ou crédito (redução na fatura). Siga esta ordem de prioridade:

1. COR DO TEXTO/LINHA (critério principal e definitivo):
   - Texto ou valor em VERDE → "Tipo": "credito" (sem exceção)
   - Texto ou valor em PRETO, CINZA, BRANCO ou qualquer outra cor → "Tipo": "debito"

2. SINAL NEGATIVO (quando a cor não for identificável):
   - Valor precedido de sinal negativo (−) → "Tipo": "credito"

3. PALAVRAS-CHAVE NA DESCRIÇÃO (fallback final):
   - Contém "ESTORNO", "CREDITO", "IOF ZERO", "DEVOLUCAO" ou equivalentes → "Tipo": "credito"
   - Demais lançamentos → "Tipo": "debito"

O campo "Valor" é sempre positivo (sem sinal); o campo "Tipo" determina se o lançamento reduz ou aumenta o gasto.

Sua resposta DEVE ser um array JSON validado ESTRITO (sem nenhuma outra palavra, e sem a crase de markdown ```json). O output esperado é uma lista pura como:
[
  {
"Descricao": "12/02 NOME ESTABELECIMENTO",
"Valor": 73.89,
"Cartao": "1234",
"Titular": "NOME TITULAR",
"Tipo": "debito"
  },
  {
"Descricao": "16/03 IOF ZERO CAIXA VISA",
"Valor": 0.18,
"Cartao": "1234",
"Titular": "NOME TITULAR",
"Tipo": "credito"
  }
]"""


def ocr_imagem(client: genai.Client, model: str, image_bytes: bytes, mime_type: str) -> list[dict]:
    img = Image.open(io.BytesIO(image_bytes))
    response = client.models.generate_content(
        model=model,
        contents=[PROMPT_OCR, img],
    )
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:-3]
    elif raw.startswith("```"):
        raw = raw[3:-3]
    return json.loads(raw.strip())


# ── Gemini: Classificação ──

def classificar_transacoes(
    client: genai.Client, model: str, transacoes: list[dict], regras_ia: str
) -> list[dict]:
    if not transacoes:
        return transacoes

    prompt = (
        "Classifique cada transação abaixo em uma das categorias: "
        "Alimentação, Supermercado, Transporte, Saúde, Odontologia, Assinatura, Lazer, Pet, "
        "Compras, Combustível, Casa, Outros. "
        'Responda APENAS em JSON no formato: [{"idx": <indice_inteiro>, "categoria": "<categoria>"}]\n\n'
    )
    if regras_ia:
        prompt += f"Regras Específicas do Usuário (Siga estritamente):\n{regras_ia}\n\n"
    prompt += "Transações:\n"
    for i, t in enumerate(transacoes):
        prompt += f"{i}. {t['Descricao']} - R$ {t['Valor']}\n"

    response = client.models.generate_content(model=model, contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:-3]
    elif raw.startswith("```"):
        raw = raw[3:-3]

    classifs = json.loads(raw)
    cmap = {c.get("idx"): c.get("categoria", "Outros") for c in classifs}
    for i, t in enumerate(transacoes):
        t["Categoria"] = cmap.get(i, "Outros")

    return transacoes


# ── Processamento em background ──

def processar_faturas(images_data: list[tuple[bytes, str]], x_mes: Optional[str]):
    """Processa as imagens em background após resposta imediata ao iPhone."""
    try:
        supabase = get_supabase()
        gemini = get_gemini()
        gemini_model, gemini_vision_model = get_gemini_models(supabase, "Principal")
        regras_ia = get_regras_ia(supabase, "Principal")

        # 1. OCR de todas as imagens (com dedup cross-imagem)
        # Cada imagem é deduplicada contra as transações já vistas nas imagens anteriores
        # do mesmo upload, evitando duplicatas por sobreposição de fotos de páginas adjacentes.
        todas_transacoes = []
        for image_bytes, mime in images_data:
            try:
                extraidas = ocr_imagem(gemini, gemini_vision_model, image_bytes, mime)
                novas_imagem = [t for t in extraidas if not _match_cross_imagem(t, todas_transacoes)]
                removidos = len(extraidas) - len(novas_imagem)
                if removidos:
                    logger.info(f"Dedup cross-imagem: {removidos} transação(ões) removida(s)")
                todas_transacoes.extend(novas_imagem)
                logger.info(f"OCR extraiu {len(novas_imagem)} transações de uma imagem ({len(extraidas)} brutas)")
            except Exception as e:
                logger.error(f"Erro OCR: {e}")

        if not todas_transacoes:
            logger.warning("Nenhuma transação encontrada nas imagens")
            return

        # 2. Inferir ciclo
        ciclo = x_mes if x_mes else inferir_ciclo(todas_transacoes, supabase)
        logger.info(f"Ciclo inferido: {ciclo}")

        # 2b. Copiar gastos fixos se ciclo novo
        try:
            _copiar_gastos_fixos_se_necessario(supabase, ciclo)
        except Exception as e:
            logger.error(f"Erro ao copiar gastos fixos: {e}")

        # 3. Rotear perfil pelo titular
        for t in todas_transacoes:
            t["dest_profile"] = rotear_perfil(t.get("Titular", "Sistema"))

        # 4. Carregar transações existentes para dedup
        existentes = {}
        for perfil in ["Principal", "Dependente"]:
            try:
                pid = get_profile_id(supabase, perfil)
                result = (
                    supabase.table("transacoes")
                    .select("descricao, valor, cartao, titular, tipo")
                    .eq("profile_id", pid)
                    .eq("mes", ciclo)
                    .execute()
                )
                existentes[perfil] = [
                    {
                        "Descricao": t["descricao"],
                        "Valor": float(t["valor"]),
                        "Cartao": t["cartao"],
                        "Titular": t.get("titular"),
                        "Tipo": t.get("tipo", "debito"),
                    }
                    for t in result.data
                ]
            except ValueError:
                existentes[perfil] = []

        # 5. Dedup
        novos, ignorados = dedup_transacoes(todas_transacoes, existentes)
        logger.info(f"Dedup: {len(novos)} novos, {len(ignorados)} ignorados")

        # 6. Classificar categorias (só os novos débitos; créditos recebem categoria fixa)
        for t in novos:
            if t.get("Tipo") == "credito":
                t["Categoria"] = "Crédito/Estorno"
        novos_debito = [t for t in novos if t.get("Tipo") != "credito"]
        if novos_debito:
            try:
                classificar_transacoes(gemini, gemini_model, novos_debito, regras_ia)
            except Exception as e:
                logger.error(f"Erro classificação: {e}")
                for t in novos_debito:
                    t.setdefault("Categoria", "Outros")

        # 7. Insert batch por perfil
        for perfil in ["Principal", "Dependente"]:
            trans_perfil = [t for t in novos if t["dest_profile"] == perfil]
            if not trans_perfil:
                continue
            try:
                pid = get_profile_id(supabase, perfil)
            except ValueError:
                continue

            records = []
            for t in trans_perfil:
                valor = float(t.get("Valor", 0))
                if math.isnan(valor) or math.isinf(valor):
                    valor = 0.0
                records.append({
                    "profile_id": str(pid),
                    "mes": ciclo,
                    "descricao": str(t.get("Descricao", "")),
                    "valor": valor,
                    "cartao": str(t.get("Cartao", "")),
                    "titular": str(t.get("Titular", "Sistema")),
                    "categoria": str(t.get("Categoria", "Outros")),
                    "tipo": str(t.get("Tipo", "debito")),
                })

            supabase.table("transacoes").insert(records).execute()
            logger.info(f"Inseridas {len(records)} transações para {perfil}")
            supabase.table("profiles").update(
                {"ultima_importacao": datetime.now(timezone.utc).isoformat()}
            ).eq("id", str(pid)).execute()
            logger.info(f"ultima_importacao atualizada para {perfil}")

        logger.info("Processamento concluído com sucesso")

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")


# ── Endpoint ──

@app.post("/upload-fatura")
async def upload_fatura(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    authorization: str = Header(...),
    x_mes: Optional[str] = Header(None),
):
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Não autorizado")

    # Ler todas as imagens imediatamente (antes de responder)
    images_data = []
    for f in files:
        contents = await f.read()
        mime = f.content_type or "image/jpeg"
        images_data.append((contents, mime))

    # Agendar processamento em background
    background_tasks.add_task(processar_faturas, images_data, x_mes)

    # Responder imediatamente ao iPhone
    return {"status": "recebido", "imagens": len(images_data)}


@app.get("/health")
async def health():
    return {"status": "ok"}
