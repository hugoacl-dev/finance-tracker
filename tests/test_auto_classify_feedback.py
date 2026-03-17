"""
Testa a ordem de execução do auto-classificar:
- st.success deve ser chamado FORA do spinner (após o contexto fechar)
- st.rerun deve ser chamado APÓS st.success
- Erros de IA não impedem o save nem o feedback
- Erros de save mostram st.error e param com st.stop
"""
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call


# ── Replay helpers ────────────────────────────────────────────────────────────

class CallRecorder:
    """Registra chamadas na ordem em que ocorrem."""
    def __init__(self):
        self.log = []

    def record(self, name, *args):
        self.log.append(name)
        return MagicMock()

    @contextmanager
    def spinner(self, *args, **kwargs):
        self.log.append("spinner:enter")
        yield
        self.log.append("spinner:exit")

    def __getattr__(self, name):
        return lambda *a, **kw: self.record(name, *a, **kw)


def _run_auto_classify(todas, classify_result=None, classify_raises=None,
                       save_raises=None):
    """
    Reproduz o fluxo do botão auto-classificar de tab_settings.py.
    Retorna (recorder, stopped) onde stopped=True se st.stop() foi chamado.
    """
    import unicodedata

    def normalize_text(t):
        if not t: return ""
        t = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII')
        return "".join(c for c in t if c.isalnum()).upper()

    rec = CallRecorder()
    stopped = False

    class StopSignal(Exception):
        pass

    def fake_stop():
        rec.log.append("stop")
        raise StopSignal()

    def fake_success(msg):
        rec.log.append("success")

    def fake_error(msg):
        rec.log.append("error")

    def fake_rerun():
        rec.log.append("rerun")

    def fake_sleep(n):
        rec.log.append("sleep")

    def fake_classify(itens, model, regras):
        if classify_raises:
            raise classify_raises
        return classify_result or []

    def fake_save(perfil, mes, data):
        rec.log.append("save")
        if save_raises:
            raise save_raises

    KW_CREDITO = {"IOF", "ESTORNO", "DEVOLUCAO", "DEVOL", "CASHBACK",
                  "REEMBOLSO", "CANCELAMENTO", "CANCELAM", "CREDITO"}

    try:
        ia_error = None
        with rec.spinner("Classificando com IA..."):
            for t in todas:
                if t.get("Tipo") == "credito" or any(
                    kw in normalize_text(str(t.get("Descricao", ""))) for kw in KW_CREDITO
                ):
                    t["Tipo"] = "credito"
                    t["Categoria"] = "Crédito/Estorno"

            debitos = [t for t in todas if t.get("Tipo") != "credito"]
            if debitos:
                try:
                    itens = "\n".join(
                        f"{i}: {t.get('Descricao', '')} - R$ {t.get('Valor', 0)}"
                        for i, t in enumerate(debitos)
                    )
                    classfs = fake_classify(itens, "model", "")
                    cmap = {int(c.get("idx", -1)): c.get("categoria", "Outros") for c in classfs}
                    for i, t in enumerate(debitos):
                        t["Categoria"] = cmap.get(i, "Outros")
                except Exception as e:
                    ia_error = str(e)

        if ia_error:
            fake_error(f"Erro na classificação IA: {ia_error}")

        try:
            fake_save("perfil", "mes", todas)
        except Exception as e:
            fake_error(f"Erro ao salvar: {e}")
            fake_stop()

        fake_success("Atualizado!")
        fake_sleep(1)
        fake_rerun()

    except StopSignal:
        stopped = True

    return rec, stopped


# ── Testes de ordem de execução ───────────────────────────────────────────────

class TestFeedbackOrdem:
    def _transacoes(self):
        return [
            {"Descricao": "IFOOD", "Tipo": "debito", "Valor": 45.0},
            {"Descricao": "IOF CAIXA", "Tipo": "debito", "Valor": 1.5},
        ]

    def test_success_apos_spinner_fecha(self):
        """st.success deve aparecer DEPOIS do spinner:exit."""
        rec, _ = _run_auto_classify(
            self._transacoes(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        spinner_exit = rec.log.index("spinner:exit")
        success_pos = rec.log.index("success")
        assert success_pos > spinner_exit, (
            f"success ({success_pos}) deve vir após spinner:exit ({spinner_exit})\n"
            f"Log: {rec.log}"
        )

    def test_rerun_apos_success(self):
        """st.rerun deve vir depois de st.success."""
        rec, _ = _run_auto_classify(
            self._transacoes(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        success_pos = rec.log.index("success")
        rerun_pos = rec.log.index("rerun")
        assert rerun_pos > success_pos, (
            f"rerun ({rerun_pos}) deve vir após success ({success_pos})\n"
            f"Log: {rec.log}"
        )

    def test_sleep_entre_success_e_rerun(self):
        """sleep(1) deve estar entre success e rerun."""
        rec, _ = _run_auto_classify(
            self._transacoes(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        success_pos = rec.log.index("success")
        sleep_pos = rec.log.index("sleep")
        rerun_pos = rec.log.index("rerun")
        assert success_pos < sleep_pos < rerun_pos, (
            f"Ordem esperada: success→sleep→rerun\nLog: {rec.log}"
        )

    def test_ordem_completa(self):
        """Ordem completa: spinner:enter → spinner:exit → save → success → sleep → rerun."""
        rec, _ = _run_auto_classify(
            self._transacoes(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        assert rec.log == ["spinner:enter", "spinner:exit", "save", "success", "sleep", "rerun"], (
            f"Ordem inesperada: {rec.log}"
        )


class TestFeedbackComErros:
    def test_erro_ia_nao_impede_save_nem_success(self):
        """Se IA falhar, deve aparecer error mas save e success ainda executam."""
        transacoes = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        rec, stopped = _run_auto_classify(
            transacoes,
            classify_raises=ValueError("API timeout")
        )
        assert "error" in rec.log
        assert "save" in rec.log
        assert "success" in rec.log
        assert "rerun" in rec.log
        assert not stopped

    def test_erro_ia_error_antes_do_save(self):
        """Erro da IA deve aparecer antes do save (fora do spinner)."""
        transacoes = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        rec, _ = _run_auto_classify(
            transacoes,
            classify_raises=ValueError("timeout")
        )
        error_pos = rec.log.index("error")
        save_pos = rec.log.index("save")
        spinner_exit = rec.log.index("spinner:exit")
        assert error_pos > spinner_exit, "error deve ser fora do spinner"
        assert error_pos < save_pos, "error deve vir antes do save"

    def test_erro_save_mostra_error_e_para(self):
        """Se save falhar: mostra error e chama stop — não chama success nem rerun."""
        transacoes = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        rec, stopped = _run_auto_classify(
            transacoes,
            classify_result=[{"idx": 0, "categoria": "Transporte"}],
            save_raises=RuntimeError("Supabase error")
        )
        assert "error" in rec.log
        assert "stop" in rec.log
        assert "success" not in rec.log
        assert "rerun" not in rec.log
        assert stopped

    def test_erro_save_apos_spinner(self):
        """Erro do save deve aparecer fora do spinner."""
        transacoes = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        rec, _ = _run_auto_classify(
            transacoes,
            save_raises=RuntimeError("db error")
        )
        spinner_exit = rec.log.index("spinner:exit")
        error_pos = rec.log.index("error")
        assert error_pos > spinner_exit, (
            f"Erro do save deve estar fora do spinner\nLog: {rec.log}"
        )
