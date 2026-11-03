"""Fixtures LNR construites à la main (source activée mais crawl non encore lancé)."""

POSITIONS_15 = [
    ("Pilier gauche", "Cyril BAILLE", "9182"),
    ("Talonneur", "Peato MAUVAKA", "9201"),
    ("Pilier droit", "Dorian ALDEGHERI", "9177"),
    ("Deuxième ligne", "Thibaud FLAMENT", "9455"),
    ("Deuxième ligne", "Emmanuel MEAFOU", "10914"),
    ("Troisième ligne aile", "François CROS", "9033"),
    ("Troisième ligne", "Jack WILLIS", "11558"),
    ("Troisième ligne centre", "Anthony JELONCH", "9377"),
    ("Demi de mêlée", "Antoine DUPONT", "9293"),
    ("Demi d'ouverture", "Romain NTAMACK", "9402"),
    ("Ailier", "Matthis LEBEL", "11011"),
    ("Centre", "Pita AHKI", "8853"),
    ("Centre", "Santi CHOCOBARES", "11631"),
    ("Ailier", "Juan Cruz MALLIA", "10462"),
    ("Arrière", "Thomas RAMOS", "9472"),
]
BENCH_8 = [
    ("Pilier", "Rodrigue NETI", "9444"),
    ("Talonneur", "Julien MARCHAND", "9155"),
    ("Deuxième ligne", "Richie ARNOLD", "8942"),
    ("Troisième ligne", "Joshua BRENNAN", "12007"),
    ("Demi de mêlée", "Paul GRAOU", "11002"),
    ("Demi d'ouverture", "Antoine FRISCH", "10444"),
    ("Centre", "Dimitri DELIBES", "11540"),
    ("Ailier", "Arthur RETIERE", "9888"),
]
UBG_15 = [
    ("Pilier gauche", "Jefferson POIROT", "8879"),
    ("Talonneur", "Maxime LAMOTHE", "9500"),
    ("Pilier droit", "Benjamin TAMEIFUNA", "8755"),
    ("Deuxième ligne", "Adam COLEMAN", "8577"),
    ("Deuxième ligne", "Cyril CAZEAUX", "9511"),
    ("Troisième ligne aile", "Mahamadou DIABY", "10997"),
    ("Troisième ligne", "Pete SAMU", "9844"),
    ("Troisième ligne centre", "Alexandre ROUILLARD", "9880"),
    ("Demi de mêlée", "Maxime LUCU", "9488"),
    ("Demi d'ouverture", "Mateo GARCIA", "11222"),
    ("Ailier", "Louis BIELLE-BIARREY", "12231"),
    ("Centre", "Yoram MOEFANA", "11533"),
    ("Centre", "Nicolas DEPOORTERE", "12110"),
    ("Ailier", "Pablo UBERTI", "11660"),
    ("Arrière", "Romain BUROS", "9633"),
]
UBG_BENCH = [
    ("Pilier", "Carlu Sadie", "10001"),
    ("Talonneur", "Clément MAYNADIER", "9001"),
    ("Deuxième ligne", "Jono GIBBINS", "11444"),
    ("Troisième ligne", "Bastien VERGNES-TAILLEFER", "11990"),
    ("Demi de mêlée", "Teo HAMDOUI", "11820"),
    ("Demi d'ouverture", "Zack HOLMES", "9011"),
    ("Centre", "Pablo COSTA", "11777"),
    ("Arrière", "Gaetan GERMAIN", "8222"),
]


def slug(name):
    return name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")


def lineup_page(
    match_id,
    season,
    round_,
    home,
    away,
    score,
    kickoff,
    venue,
    starters_h,
    bench_h,
    starters_a,
    bench_a,
    late=False,
):
    def rows(starters, bench):
        out = []
        for shirt, (pos, name, pid) in enumerate(starters, start=1):
            late_attr = ' data-late="1"' if late and shirt == 10 else ""
            out.append(
                f'<tr class="starter"{late_attr} data-shirt="{shirt}"><td class="pos">{pos}</td>'
                f'<td class="player"><a href="/joueurs/{slug(name)}-{pid}">{name}</a></td>'
                f'<td class="nat">France</td></tr>'
            )
        for shirt, (pos, name, pid) in enumerate(bench, start=16):
            out.append(
                f'<tr class="bench" data-shirt="{shirt}"><td class="pos">{pos}</td>'
                f'<td class="player"><a href="/joueurs/{slug(name)}-{pid}">{name}</a></td>'
                f'<td class="nat">France</td></tr>'
            )
        return "".join(out)

    def section(team, starters, bench):
        return (
            f'<section class="team" data-team="{team}"><h3>{team}</h3>'
            f'<table class="lineup"><tbody>{rows(starters, bench)}</tbody></table></section>'
        )

    return (
        "<html><body>"
        f'<div class="match-sheet"><div class="comp-header"><span class="comp">Top 14</span>'
        f'<span class="season">{season}</span><span class="round">{round_}</span>'
        f'<span class="match-id">{match_id}</span></div>'
        f'<h2><span class="home">{home}</span> <span class="score">{score}</span> <span class="away">{away}</span></h2>'
        f'<div class="kickoff">{kickoff}</div>'
        f'<div class="venue" itemprop="location"><span itemprop="name">{venue}</span></div>'
        + section(home, starters_h, bench_h)
        + section(away, starters_a, bench_a)
        + "</div></body></html>"
    )


def main():
    out = __import__("pathlib").Path(__file__).parent
    out.joinpath("lineup_regular.html").write_text(
        lineup_page(
            "8427",
            "2024-2025",
            "J10",
            "Stade Toulousain",
            "Union Bordeaux Bègles",
            "27-19",
            "21/12/2024 21:05",
            "Stade Ernest-Wallon",
            POSITIONS_15,
            BENCH_8,
            UBG_15,
            UBG_BENCH,
        ),
        encoding="utf-8",
    )
    out.joinpath("lineup_playoff.html").write_text(
        lineup_page(
            "8431",
            "2024-2025",
            "Demi",
            "Stade Toulousain",
            "Union Bordeaux Bègles",
            "19-10",
            "21/06/2025 21:05",
            "Nouveau Stade de Bordeaux",
            POSITIONS_15,
            BENCH_8,
            UBG_15,
            UBG_BENCH,
        ),
        encoding="utf-8",
    )
    out.joinpath("lineup_late_change.html").write_text(
        lineup_page(
            "8428",
            "2024-2025",
            "J11",
            "Stade Toulousain",
            "ASM Clermont",
            "33-0",
            "29/12/2024",
            "Stade Ernest-Wallon",
            POSITIONS_15,
            BENCH_8,
            UBG_15,
            UBG_BENCH,
            late=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
