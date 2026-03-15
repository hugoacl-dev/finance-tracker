import streamlit as st
import json
from google import genai
from core.models import Transacao
from pydantic import TypeAdapter

def get_gemini_client():
    try:
        gemini_key = st.secrets.get("GEMINI_API_KEY")
        if gemini_key:
            return genai.Client(api_key=gemini_key)
    except Exception as e:
        st.error(f"Erro ao inicializar API do Gemini: {e}")
    return None

def extrair_faturas_imagem(image, model_name: str) -> list[dict]:
    client = get_gemini_client()
    if not client:
        raise Exception("Cliente Gemini não inicializado")
        
    prompt_img = """Aja como um extrator de dados financeiros de alta precisão. Sua única tarefa é ler a IMAGEM DE FATURA DE CARTÃO fornecida e extrair as transações.

Para CADA LINHA DE COMPRA visível na imagem, extraia:
1. "Descricao": Nome exato do estabelecimento + Data de compra juntos (ex: "12/02 RESTAURANTE", "13/02 SUPERMERCADO"). Trate compras parceladas com seu sufixo intacto.
2. "Valor": Apenas o número em formato flutuante (ex: 73.89, sem vírgulas ou 'R$').
3. "Cartao": Somente os últimos 4 dígitos impressos próximo da transação (ex: "1234", "5678"). Se a fatura não mostrar o final do cartão para a compra, observe de quem é a fatura e agrupe sob "Nubank" ou "Itau" dependendo do nome do banco impresso.
4. "Titular": Identifique o portador da fatura conforme indicado no app (ex: "Compras de Fulano"). Especifique o nome encontrado. Se não der para saber, use "Sistema".

Respeite estritamente o Schema de Saída fornecido."""
    
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt_img, image],
        config={
            "response_mime_type": "application/json",
            "response_schema": list[Transacao]
        }
    )
    
    if hasattr(response, "parsed"):
        parsed_items = response.parsed
        return [t.model_dump() for t in parsed_items]
    else:
        raw_json = response.text.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:-3]
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:-3]
        data = json.loads(raw_json)
        Adapter = TypeAdapter(list[Transacao])
        items = Adapter.validate_python(data)
        return [t.model_dump() for t in items]

def classificar_itens_texto(itens_texto: str, model_name: str, regras_ia: str) -> list[dict]:
    client = get_gemini_client()
    if not client:
        return []
    
    prompt = f"""Você é um motor de categorização financeira de alta velocidade. Sua missão é ler as seguintes linhas de transação e devolver um JSON Array puro informando qual categoria mapeia cada índice de item passado, mantendo ordem 1:1 rigorosa.
    
Categorias Admissíveis:
["Alimentação", "Supermercado", "Transporte", "Saúde", "Assinatura", "Lazer", "Pet", "Compras", "Combustível", "Casa", "Outros"]

Regras Definidas pelo Usuário do App:
{regras_ia}

Itens para Classificar (índice : texto original puro do extrato bancário):
{itens_texto}

Sua resposta DEVE ser um array JSON validado ESTRITO E PURO de objetos com duas chaves ("idx" e "categoria"). 
Exemplo perfeito:
[
  {{"idx": 0, "categoria": "Alimentação"}},
  {{"idx": 1, "categoria": "Supermercado"}}
]"""
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    raw_json = response.text.strip()
    if raw_json.startswith("```json"):
        raw_json = raw_json[7:-3]
    elif raw_json.startswith("```"):
        raw_json = raw_json[3:-3]
    return json.loads(raw_json)
    
def diagnostico_chatbot(dados_mes_str: str, model_name: str, query: str = None) -> str:
    client = get_gemini_client()
    if not client:
        return "Erro de API"
        
    s_prompt = "Você é um Consultor Financeiro AI. Analise os dados brutos de faturas enviados pelo usuário e crie um Diagnóstico Financeiro."
    if query:
        s_prompt = "Você é um Consultor Financeiro AI respondendo dúvidas do usuário baseado no extrato dele."
    
    context = f"DADOS DO MÊS ATUAL OBTIDOS NO SISTEMA FINANCEIRO DO USUÁRIO:\n{dados_mes_str}\n\nPERGUNTA/AÇÃO DO USUÁRIO:\n{query if query else 'Gere um relatório completo destrinchando o comportamento de gastos.'}"
    
    response = client.models.generate_content(
        model=model_name,
        contents=[s_prompt, context]
    )
    return response.text
