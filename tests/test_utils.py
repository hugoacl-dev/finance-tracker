from core.utils import mes_sort_key


def test_mes_sort_key_mm_aa():
    assert mes_sort_key("03/26") == (2026, 3)


def test_mes_sort_key_mm_aaaa():
    assert mes_sort_key("03/2026") == (2026, 3)


def test_mes_sort_key_nome_mes_aa():
    assert mes_sort_key("Marco 26") == (2026, 3)


def test_mes_sort_key_nome_mes_com_acento():
    assert mes_sort_key("Março 2026") == (2026, 3)


def test_mes_sort_key_invalid():
    assert mes_sort_key("Periodo X") == (0, 0)


def test_mes_sort_key_mixed_sorting():
    months = ["Março 2026", "02/26", "01/2026", "Abril 26"]
    assert sorted(months, key=mes_sort_key) == ["01/2026", "02/26", "Março 2026", "Abril 26"]
