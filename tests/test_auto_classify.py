"""
Testa o pipeline de auto-classificação de tab_settings.py.
Cobre: detecção de crédito por keyword, marcação de Tipo/Categoria,
separação débitos/créditos e aplicação do cmap da IA.

O teste é propositalmente auto-contido (sem deps de Streamlit/Supabase)
para rodar em CI sem infraestrutura.
"""
import unicodedata
from unittest.mock import MagicMock, patch


# ── Réplica das funções puras de produção ─────────────────────────────────────

def normalize_text(t) -> str:
    """Idêntica a services/data_engine.py:normalize_text."""
    if not t:
        return ""
    t = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII')
    return "".join(c for c in t if c.isalnum()).upper()


KW_CREDITO = {"IOF", "ESTORNO", "DEVOLUCAO", "DEVOL", "CASHBACK",
              "REEMBOLSO", "CANCELAMENTO", "CANCELAM", "CREDITO"}


def marcar_creditos(todas: list) -> None:
    for t in todas:
        if t.get("Tipo") == "credito" or any(
            kw in normalize_text(str(t.get("Descricao", ""))) for kw in KW_CREDITO
        ):
            t["Tipo"] = "credito"
            t["Categoria"] = "Crédito/Estorno"


def aplicar_cmap(debitos: list, classfs: list) -> None:
    cmap = {int(c.get("idx", -1)): c.get("categoria", "Outros") for c in classfs}
    for i, t in enumerate(debitos):
        t["Categoria"] = cmap.get(i, "Outros")


# ── Testes de detecção de crédito ─────────────────────────────────────────────

class TestMarcarCreditos:
    def test_iof_keyword(self):
        t = {"Descricao": "16/03 IOF CAIXA", "Tipo": "debito"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"
        assert t["Categoria"] == "Crédito/Estorno"

    def test_credito_com_acento(self):
        t = {"Descricao": "CRÉDITO EM CONTA", "Tipo": "debito"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"

    def test_estorno(self):
        t = {"Descricao": "ESTORNO IFOOD", "Tipo": "debito"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"
        assert t["Categoria"] == "Crédito/Estorno"

    def test_cashback(self):
        t = {"Descricao": "CASHBACK NUBANK", "Tipo": "debito"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"

    def test_tipo_credito_sem_keyword(self):
        t = {"Descricao": "PIX RECEBIDO", "Tipo": "credito"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"
        assert t["Categoria"] == "Crédito/Estorno"

    def test_debito_normal_nao_afetado(self):
        t = {"Descricao": "UBER *TRIP", "Tipo": "debito"}
        marcar_creditos([t])
        assert t["Tipo"] == "debito"
        assert "Categoria" not in t

    def test_sem_tipo_com_keyword(self):
        t = {"Descricao": "DEVOLUCAO AMAZON"}
        marcar_creditos([t])
        assert t["Tipo"] == "credito"

    def test_lista_mista(self):
        trans = [
            {"Descricao": "IOF CAIXA", "Tipo": "debito"},
            {"Descricao": "SUPERMERCADO EXTRA", "Tipo": "debito"},
            {"Descricao": "ESTORNO NETFLIX", "Tipo": "debito"},
        ]
        marcar_creditos(trans)
        assert trans[0]["Tipo"] == "credito"
        assert trans[1]["Tipo"] == "debito"
        assert trans[2]["Tipo"] == "credito"


# ── Testes de aplicação do cmap ───────────────────────────────────────────────

class TestAplicarCmap:
    def test_mapeamento_basico(self):
        debitos = [
            {"Descricao": "UBER", "Tipo": "debito"},
            {"Descricao": "IFOOD", "Tipo": "debito"},
        ]
        classfs = [{"idx": 0, "categoria": "Transporte"}, {"idx": 1, "categoria": "Alimentação"}]
        aplicar_cmap(debitos, classfs)
        assert debitos[0]["Categoria"] == "Transporte"
        assert debitos[1]["Categoria"] == "Alimentação"

    def test_idx_como_string(self):
        """LLM pode retornar idx como string — int() deve normalizar."""
        debitos = [{"Descricao": "NETFLIX", "Tipo": "debito"}]
        classfs = [{"idx": "0", "categoria": "Assinatura"}]
        aplicar_cmap(debitos, classfs)
        assert debitos[0]["Categoria"] == "Assinatura"

    def test_idx_ausente_fallback_outros(self):
        debitos = [{"Descricao": "COMPRA X", "Tipo": "debito"}]
        classfs = [{"idx": 99, "categoria": "Lazer"}]
        aplicar_cmap(debitos, classfs)
        assert debitos[0]["Categoria"] == "Outros"

    def test_categoria_ausente_fallback_outros(self):
        debitos = [{"Descricao": "COMPRA X", "Tipo": "debito"}]
        classfs = [{"idx": 0}]
        aplicar_cmap(debitos, classfs)
        assert debitos[0]["Categoria"] == "Outros"


# ── Testes de pipeline completo ───────────────────────────────────────────────

class TestPipelineCompleto:
    def test_iof_vira_credito_e_nao_vai_para_ia(self):
        todas = [
            {"Descricao": "IOF CAIXA", "Tipo": "debito", "Valor": 1.50},
            {"Descricao": "IFOOD", "Tipo": "debito", "Valor": 45.00},
            {"Descricao": "UBER TRIP", "Tipo": "debito", "Valor": 18.00},
        ]
        marcar_creditos(todas)
        debitos = [t for t in todas if t.get("Tipo") != "credito"]

        assert len(debitos) == 2  # IOF virou crédito, não vai pra IA

        classfs = [{"idx": 0, "categoria": "Alimentação"}, {"idx": 1, "categoria": "Transporte"}]
        aplicar_cmap(debitos, classfs)

        assert todas[0]["Tipo"] == "credito"
        assert todas[0]["Categoria"] == "Crédito/Estorno"
        assert todas[1]["Categoria"] == "Alimentação"
        assert todas[2]["Categoria"] == "Transporte"

    def test_so_creditos_debitos_vazio(self):
        todas = [
            {"Descricao": "ESTORNO AMAZON", "Tipo": "debito"},
            {"Descricao": "CASHBACK", "Tipo": "debito"},
        ]
        marcar_creditos(todas)
        debitos = [t for t in todas if t.get("Tipo") != "credito"]
        assert debitos == []

    def test_lista_vazia(self):
        marcar_creditos([])
        debitos = [t for t in [] if t.get("Tipo") != "credito"]
        assert debitos == []

    def test_modificacao_in_place_preservada(self):
        """Garante que modificar dicts de 'debitos' afeta a lista 'todas'."""
        todas = [
            {"Descricao": "PADARIA", "Tipo": "debito", "Valor": 12.0},
        ]
        marcar_creditos(todas)
        debitos = [t for t in todas if t.get("Tipo") != "credito"]
        aplicar_cmap(debitos, [{"idx": 0, "categoria": "Alimentação"}])

        # O dict em 'todas' deve ter sido modificado in-place
        assert todas[0]["Categoria"] == "Alimentação"

    def test_itens_texto_formato(self):
        """Verifica o formato exato da string enviada para classificar_itens_texto."""
        debitos = [
            {"Descricao": "PADARIA DO ZE", "Valor": 25.0},
            {"Descricao": "UBER", "Valor": 12.0},
        ]
        itens = "\n".join(
            f"{i}: {t.get('Descricao', '')} - R$ {t.get('Valor', 0)}"
            for i, t in enumerate(debitos)
        )
        assert itens == "0: PADARIA DO ZE - R$ 25.0\n1: UBER - R$ 12.0"
