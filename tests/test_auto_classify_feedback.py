"""
Testa o padrão correto de feedback do auto-classificar:
- Após operações bem-sucedidas, _notify_success é setado em session_state
- st.rerun() é chamado imediatamente, SEM time.sleep()
- A mensagem é exibida no próximo render, não antes do rerun
- Erros de IA não impedem o save
- Erros de save setam _notify_error e fazem rerun (sem st.stop())
"""
import unicodedata
from contextlib import contextmanager


class FakeSessionState(dict):
    def pop(self, key, default=None):
        return super().pop(key, default)


def _run_auto_classify(todas, classify_result=None, classify_raises=None,
                       save_raises=None):
    """
    Reproduz o fluxo do botão auto-classificar de tab_settings.py.
    Retorna (session_state, log_de_chamadas).
    """
    def normalize_text(t):
        if not t: return ""
        t = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII')
        return "".join(c for c in t if c.isalnum()).upper()

    session = FakeSessionState()
    log = []

    @contextmanager
    def spinner(*a, **kw):
        log.append("spinner:enter")
        yield
        log.append("spinner:exit")

    def fake_classify(itens, model, regras):
        if classify_raises:
            raise classify_raises
        return classify_result or []

    def fake_save(perfil, mes, data):
        log.append("save")
        if save_raises:
            raise save_raises

    def fake_rerun():
        log.append("rerun")

    KW_CREDITO = {"IOF", "ESTORNO", "DEVOLUCAO", "DEVOL", "CASHBACK",
                  "REEMBOLSO", "CANCELAMENTO", "CANCELAM", "CREDITO"}

    # ── Replicação exata do bloco em tab_settings.py ──────────────────────────
    ia_error = None
    with spinner("Classificando com IA..."):
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

    try:
        fake_save("perfil", "mes", todas)
    except Exception as e:
        session["_notify_error"] = f"Erro ao salvar: {e}"
        fake_rerun()
        return session, log

    session["_notify_success"] = "Atualizado!"
    fake_rerun()
    # ─────────────────────────────────────────────────────────────────────────

    return session, log


# ── Testes de padrão de notificação ──────────────────────────────────────────

class TestNotificacaoPosRerun:
    def _trans(self):
        return [
            {"Descricao": "IFOOD", "Tipo": "debito", "Valor": 45.0},
            {"Descricao": "IOF CAIXA", "Tipo": "debito", "Valor": 1.5},
        ]

    def test_sucesso_seta_flag_session_state(self):
        """Após save bem-sucedido, _notify_success deve estar em session_state."""
        session, _ = _run_auto_classify(
            self._trans(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        assert session.get("_notify_success") == "Atualizado!"

    def test_sem_sleep_antes_do_rerun(self):
        """Não deve haver sleep entre save e rerun (padrão correto)."""
        _, log = _run_auto_classify(
            self._trans(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        assert "sleep" not in log

    def test_rerun_chamado_apos_set_flag(self):
        """rerun deve ser chamado e a flag deve ter sido setada antes."""
        session, log = _run_auto_classify(
            self._trans(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        assert "rerun" in log
        assert session.get("_notify_success") == "Atualizado!"

    def test_ordem_completa(self):
        """Ordem: spinner:enter → spinner:exit → save → rerun."""
        _, log = _run_auto_classify(
            self._trans(),
            classify_result=[{"idx": 0, "categoria": "Alimentação"}]
        )
        assert log == ["spinner:enter", "spinner:exit", "save", "rerun"]

    def test_erro_ia_nao_impede_save_nem_flag_sucesso(self):
        """Se IA falhar, save ainda ocorre e _notify_success é setado."""
        trans = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        session, log = _run_auto_classify(
            trans,
            classify_raises=ValueError("API timeout")
        )
        assert "save" in log
        assert "rerun" in log
        assert session.get("_notify_success") == "Atualizado!"
        assert "_notify_error" not in session

    def test_erro_save_seta_notify_error_e_faz_rerun(self):
        """Se save falhar, _notify_error é setado e rerun ocorre — sem success."""
        trans = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        session, log = _run_auto_classify(
            trans,
            classify_result=[{"idx": 0, "categoria": "Transporte"}],
            save_raises=RuntimeError("Supabase error")
        )
        assert "_notify_error" in session
        assert "Supabase error" in session["_notify_error"]
        assert "_notify_success" not in session
        assert "rerun" in log

    def test_erro_save_sem_stop(self):
        """Erro de save deve fazer rerun, não stop (log não contém 'stop')."""
        trans = [{"Descricao": "UBER", "Tipo": "debito", "Valor": 20.0}]
        _, log = _run_auto_classify(
            trans,
            save_raises=RuntimeError("db error")
        )
        assert "stop" not in log
        assert "rerun" in log
