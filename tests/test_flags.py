"""Todo time dos fixtures precisa resolver para uma bandeira."""

from app.flags import flag_url
from app.seed_data import FIXTURES


def test_todos_os_times_dos_fixtures_tem_bandeira():
    times = {
        t
        for f in FIXTURES
        for t in (f["home_team"], f["away_team"])
        if t != "A definir"
    }
    sem_bandeira = sorted(t for t in times if flag_url(t) is None)
    assert sem_bandeira == []


def test_url_e_largura():
    assert flag_url("Brasil") == "https://flagcdn.com/w40/br.png"
    assert flag_url("Inglaterra", width=20) == "https://flagcdn.com/w20/gb-eng.png"


def test_desconhecido_e_placeholder_retornam_none():
    assert flag_url("Atlântida") is None
    assert flag_url("A definir") is None
