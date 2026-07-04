"""Bandeiras das seleções (imagens do flagcdn; emoji não renderiza no Windows)."""

# Nome em PT (como está em matches.home_team/away_team) -> código ISO do flagcdn.
FLAGS = {
    "África do Sul": "za",
    "Alemanha": "de",
    "Arábia Saudita": "sa",
    "Argélia": "dz",
    "Argentina": "ar",
    "Austrália": "au",
    "Áustria": "at",
    "Bélgica": "be",
    "Bósnia e Herzegovina": "ba",
    "Brasil": "br",
    "Cabo Verde": "cv",
    "Canadá": "ca",
    "Catar": "qa",
    "Colômbia": "co",
    "Coreia do Sul": "kr",
    "Costa do Marfim": "ci",
    "Croácia": "hr",
    "Curaçao": "cw",
    "Egito": "eg",
    "Equador": "ec",
    "Escócia": "gb-sct",
    "Espanha": "es",
    "Estados Unidos": "us",
    "França": "fr",
    "Gana": "gh",
    "Haiti": "ht",
    "Inglaterra": "gb-eng",
    "Irã": "ir",
    "Iraque": "iq",
    "Japão": "jp",
    "Jordânia": "jo",
    "Marrocos": "ma",
    "México": "mx",
    "Noruega": "no",
    "Nova Zelândia": "nz",
    "Países Baixos": "nl",
    "Panamá": "pa",
    "Paraguai": "py",
    "Portugal": "pt",
    "RD Congo": "cd",
    "Senegal": "sn",
    "Suécia": "se",
    "Suíça": "ch",
    "Tchéquia": "cz",
    "Tunísia": "tn",
    "Turquia": "tr",
    "Uruguai": "uy",
    "Uzbequistão": "uz",
}


def flag_url(team: str, width: int = 40) -> str | None:
    """URL da bandeira no flagcdn, ou None se o time não estiver no dicionário."""
    code = FLAGS.get(team)
    return f"https://flagcdn.com/w{width}/{code}.png" if code else None
