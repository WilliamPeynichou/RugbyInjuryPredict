"""Builds the frozen allrugby fixtures (hand-written markup, format per
tests/fixtures/allrugby/README.md). The live site is not accessed."""


def slug(name):
    return name.lower().replace(" ", "-")


def team_table(team, city, players):
    rows = []
    for num, name, pid, minutes, card in players:
        minutes_cell = str(minutes) if minutes > 0 else ""
        rows.append(
            f'<tr><td class="n">{num}</td>'
            f'<td class="player-name"><a href="/joueurs/{slug(name)}-{pid}.html">{name}</a></td>'
            f'<td class="minutes">{minutes_cell}</td>'
            f'<td class="card">{card}</td></tr>'
        )
    return (
        f'<table class="club_stats"><caption>{team} — {city}</caption>'
        f"<thead></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def match_page(match_id, season, competition, round_, home, away, score, kickoff, venue, tables):
    return (
        "<html><body>"
        f'<div class="matchinfo"><h2><span class="home">{home}</span> <span class="away">{away}</span></h2>'
        f'<span class="competition-seo">{competition}</span><span class="season">{season}</span>'
        f'<span class="round">{round_}</span><span class="match-id">{match_id}</span>'
        f'<span class="kickoff">{kickoff}</span>'
        f'<div class="venue"><span itemprop="name">{venue}</span></div>'
        f'<span class="score">{score}</span></div>' + "".join(tables) + "</body></html>"
    )


def player_page(name, birth="", height="", weight="", nationality="", jiff="", selections=""):
    lines = []
    for label, value in (
        ("Naissance", birth),
        ("Taille", height),
        ("Poids", weight),
        ("Nationalité", nationality),
        ("JIFF", jiff),
        ("Sélections", selections),
    ):
        if value:
            lines.append(f"<li>{label} : {value}</li>")
    return f'<html><body><h1 itemprop="name">{name}</h1><ul class="fiche">{"".join(lines)}</ul></body></html>'


def write(path, content):
    path.write_text(content, encoding="utf-8")


def main():
    out = __import__("pathlib").Path(__file__).parent

    toulouse = [
        (n, name, pid, mins, card)
        for n, (name, pid, mins, card) in enumerate(
            [
                ("Julien MARCHAND", "101", 56, ""),
                ("Peato MAUVAKA", "102", 24, ""),
                ("Cyril BAILLE", "103", 80, ""),
                ("Emmanuel MEAFOU", "104", 80, ""),
                ("Thibaud FLAMENT", "105", 80, ""),
                ("François CROS", "106", 80, ""),
                ("Jack WILLIS", "107", 80, ""),
                ("Antoine DUPONT", "108", 62, ""),
                ("Romain NTAMACK", "109", 80, ""),
                ("Matthis LEBEL", "110", 21, ""),
                ("Pita AHKI", "111", 80, ""),
                ("Santi CHOCOBARES", "112", 59, ""),
                ("Juan Cruz MALLIA", "113", 80, ""),
                ("Thomas RAMOS", "114", 80, ""),
                ("Blair KINGHORN", "115", 80, ""),
            ],
            start=1,
        )
    ]
    toulouse += [
        (16, "Dorian ALDEGHERI", "116", 24, ""),
        (17, "Rodrigue NETI", "117", 0, ""),
        (18, "Richie ARNOLD", "118", 0, ""),
        (21, "Paul GRAOU", "119", 18, ""),
        (23, "Dany PRISO", "120", 0, ""),
    ]
    la_rochelle = [
        (n, name, pid, mins, card)
        for n, (name, pid, mins, card) in enumerate(
            (
                [
                    ("Quentin LESPIAUCQ", "202", 29, ""),
                    ("Pierre BOURGARIT", "201", 51, "rouge"),
                    ("Uini ATONIO", "203", 56, ""),
                    ("Will SKELTON", "204", 80, ""),
                    ("Thomas LAVAULT", "205", 80, ""),
                    ("Judson ALVES DE SAA", "206", 80, ""),
                    ("Paul BOUDEHENT", "207", 80, ""),
                    ("Tawera KERR BARLOW", "208", 80, ""),
                    ("Antoine HASTOY", "209", 61, ""),
                    ("Dillyn LEYDS", "210", 80, ""),
                    ("Jonathan DANTY", "211", 80, ""),
                    ("Teddy THOMAS", "212", 80, ""),
                    ("Jules FAVRE", "213", 19, ""),
                    ("Brice DULIN", "214", 80, ""),
                    ("Louis PENVERNE", "215", 80, ""),
                ]
            ),
            start=1,
        )
    ]
    la_rochelle += [
        (16, "Facundo BOSCH", "216", 29, ""),
        (18, "Joel SCLAVI", "217", 24, ""),
        (21, "Ihaia WEST", "218", 0, ""),
        (22, "Geoffrey DOUMAYROU", "219", 0, ""),
        (23, "Hoskins SOTUTU", "220", 80, ""),
    ]
    write(
        out / "match_red_card.html",
        match_page(
            "1",
            "2024-2025",
            "top14",
            "J18",
            "Stade Toulousain",
            "Stade Rochelais",
            "33-25",
            "19/10/2024 21:05",
            "Stade Ernest-Wallon",
            [
                team_table("Stade Toulousain", "Toulouse", toulouse),
                team_table("Stade Rochelais", "La Rochelle", la_rochelle),
            ],
        ),
    )

    # 2. Standard, heure de coup d'envoi imputée (date seule)
    clermont = [
        (n, name, pid, mins, card)
        for n, (name, pid, mins, card) in enumerate(
            [
                ("Yannick PENXAERT", "301", 17, ""),
                ("Etienne FOURCADE", "302", 63, ""),
                ("Lucas PACCOTEAUX", "303", 80, ""),
                ("Luka TCHELIDZE", "304", 70, ""),
                ("Thomas Ceyte".upper(), "305", 80, ""),
                ("Peceli YATO", "306", 80, ""),
                ("Fritz LEE", "307", 80, ""),
                ("Kevin VIALLARD", "308", 80, ""),
                ("Gregoire GARCIA-BENITEZ", "309", 80, ""),
                ("Bautista DELGUY", "310", 80, ""),
                ("George MOALA", "311", 80, ""),
                ("Alivereti RAKA", "312", 80, ""),
                ("Joshua HODGE", "313", 80, ""),
                ("Anthony BELLEAU", "314", 80, ""),
                ("Alex NEWSOME", "315", 80, ""),
            ],
            start=1,
        )
    ]
    clermont += [
        (16, "Adrien LAFFITE", "316", 63, ""),
        (17, "Regis BARJALOUS", "317", 10, ""),
        (18, "Sébastien VAHAAMAHINA", "318", 10, ""),
        (21, "Louis FOURNIER", "319", 0, ""),
        (22, "Joris JURAND", "320", 0, ""),
    ]
    write(
        out / "match_standard.html",
        match_page(
            "2",
            "2023-2024",
            "top14",
            "J8",
            "ASM Clermont",
            "Stade Toulousain",
            "23-18",
            "29/10/2023",
            "Stade Marcel-Michelin",
            [
                team_table("ASM Clermont", "Clermont-Ferrand", clermont),
                team_table("Stade Toulousain", "Toulouse", toulouse[:23]),
            ],
        ),
    )

    # 3. Phase finale (demi)
    toulouse_playoff = [(*row[:3], 80 if row[0] <= 15 else 0, "") for row in toulouse[:23]]
    write(
        out / "match_playoff.html",
        match_page(
            "3",
            "2024-2025",
            "top14-playoffs",
            "Demi",
            "Stade Toulousain",
            "Stade Rochelais",
            "19-10",
            "21/06/2025 21:05",
            "Nouveau Stade de Bordeaux",
            [
                team_table("Stade Toulousain", "Bordeaux", toulouse_playoff),
                team_table("Stade Rochelais", "Bordeaux", la_rochelle[:23]),
            ],
        ),
    )

    write(
        out / "player_full.html",
        player_page(
            "Antoine DUPONT",
            "14/12/1994 à Saint-Savin (France)",
            "1,74 m",
            "85 kg",
            "France",
            "Oui",
            "58",
        ),
    )
    write(
        out / "player_partial.html", player_page("Louis FOURNIER", "Nationalité : France")
    )  # prénom seul, fiche incomplète


if __name__ == "__main__":
    main()
