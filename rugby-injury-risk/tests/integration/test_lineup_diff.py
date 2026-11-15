import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from rugby_risk.http.store import FetchResult, RawStore
from rugby_risk.http.urls import canonicalize_url

pytestmark = [pytest.mark.integration, pytest.mark.slow]
REPO = Path(__file__).resolve().parent.parent.parent
LNR_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "lnr"


def _put(store, url, content):
    store.put(
        FetchResult(
            (store.root.parent.name and "x") or "x",
            canonicalize_url(url),
            200,
            content,
            "text/html",
            hashlib.sha256(content).hexdigest(),
            datetime(2025, 1, 1, tzinfo=UTC),
            False,
            None,
            None,
        )
    )


def _allrugby_same_teams_html() -> bytes:
    """Feuille allrugby (markup allrugby-2) pour le même match, avec UN joueur différent."""
    names = [
        ("Cyril BAILLE", "1"),
        ("Peato MAUVAKA", "2"),
        ("Dorian ALDEGHERI", "3"),
        ("Thibaud FLAMENT", "4"),
        ("Emmanuel MEAFOU", "5"),
        ("François CROS", "6"),
        ("Pierrick ESPEUT", "7"),  # <- différence : Jack WILLIS côté LNR
        ("Anthony JELONCH", "8"),
        ("Antoine DUPONT", "9"),
        ("Romain NTAMACK", "10"),
        ("Matthis LEBEL", "11"),
        ("Pita AHKI", "12"),
        ("Santi CHOCOBARES", "13"),
        ("Juan Cruz MALLIA", "14"),
        ("Thomas RAMOS", "15"),
        ("Rodrigue NETI", "16"),
        ("Julien MARCHAND", "17"),
        ("Richie ARNOLD", "18"),
        ("Joshua BRENNAN", "19"),
        ("Paul GRAOU", "20"),
        ("Antoine FRISCH", "21"),
        ("Dimitri DELIBES", "22"),
        ("Arthur RETIERE", "23"),
    ]
    away_names = [
        ("Jefferson POIROT", "1"),
        ("Maxime LAMOTHE", "2"),
        ("Benjamin TAMEIFUNA", "3"),
        ("Adam COLEMAN", "4"),
        ("Cyril CAZEAUX", "5"),
        ("Mahamadou DIABY", "6"),
        ("Pete SAMU", "7"),
        ("Alexandre ROUILLARD", "8"),
        ("Maxime LUCU", "9"),
        ("Mateo GARCIA", "10"),
        ("Louis BIELLE-BIARREY", "11"),
        ("Yoram MOEFANA", "12"),
        ("Nicolas DEPOORTERE", "13"),
        ("Pablo UBERTI", "14"),
        ("Romain BUROS", "15"),
        ("Carlu Sadie", "16"),
        ("Clément MAYNADIER", "17"),
        ("Jono GIBBINS", "18"),
        ("Bastien VERGNES-TAILLEFER", "19"),
        ("Teo HAMDOUI", "20"),
        ("Zack HOLMES", "21"),
        ("Pablo COSTA", "22"),
        ("Gaetan GERMAIN", "23"),
    ]

    def rows(home, away):
        out = []
        pairs = zip(home, away, strict=True)
        for shirt, ((hname, hpid), (aname, apid)) in enumerate(pairs, start=1):
            href_h = f"/joueurs/{hname.lower().replace(' ', '-')}-{hpid}.html"
            href_a = f"/joueurs/{aname.lower().replace(' ', '-')}-{apid}.html"
            out.append(
                "<tr>"
                '<td class="txtcenter"><div class="cartons"></div></td>'
                "<td></td><td></td><td></td><td></td>"
                f'<td class="txtright jiff"><strong><a href="{href_h}">{hname}</a></strong></td>'
                f'<td class="txtcenter">{shirt}</td>'
                f'<td class="txtleft jiff"><strong><a href="{href_a}">{aname}</a></strong></td>'
                "<td></td><td></td><td></td><td></td>"
                '<td class="txtcenter"><div class="cartons"></div></td>'
                "</tr>"
            )
        return "".join(out)

    return (
        "<html><head>"
        '<link rel="canonical" href="https://www.allrugby.com/saison-2024-2025/'
        'matchs/toulouse-ubb-999.html"/></head><body>'
        '<div id="container"><div class="pas"><div class="txtcenter">'
        "<strong>Date : </strong>samedi 21 décembre 2024 "
        "<strong>Coup d'envoi : </strong>21h05 "
        "<strong>Stade : </strong>Stade Ernest-Wallon "
        "<strong>Competition : </strong>Top 14 <strong>Phase : </strong>poule</div>"
        '<div class="match_entete"><div class="equipe">Stade Toulousain</div>'
        '<div class="score">27</div><div class="vs"></div>'
        '<div class="score">19</div><div class="equipe">Union Bordeaux Bègles</div></div>'
        '<div class="grid-2"><div><h1>Match Toulouse vs Bordeaux</h1>'
        "pour le compte de la journée 10 de Top 14.</div></div>"
        '<table class="rtable striped alternate fdm rtablecenter">'
        "<caption>Feuille de match Toulouse vs Bordeaux</caption>"
        f"<tbody>{rows(names, away_names)}</tbody></table>"
        "</div></div></body></html>"
    ).encode()


def _seed(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    lnr_store = RawStore(data_dir / "raw")
    content = (LNR_FIXTURES / "lineup_regular.html").read_bytes()
    lnr_store.put(
        FetchResult(
            "lnr",
            canonicalize_url(
                "https://top14.lnr.fr/feuille-de-match/2024-2025/j10/8427-toulouse-ubb/compositions"
            ),
            200,
            content,
            "text/html",
            hashlib.sha256(content).hexdigest(),
            datetime(2025, 1, 1, tzinfo=UTC),
            False,
            None,
            None,
        )
    )
    ar_content = _allrugby_same_teams_html()
    lnr_store.put(
        FetchResult(
            "allrugby",
            canonicalize_url(
                "https://www.allrugby.com/saison-2024-2025/matchs/toulouse-ubb-999.html"
            ),
            200,
            ar_content,
            "text/html",
            hashlib.sha256(ar_content).hexdigest(),
            datetime(2025, 1, 1, tzinfo=UTC),
            False,
            None,
            None,
        )
    )
    return data_dir


def _materialize(select, partition, tmp_path):
    env = dict(os.environ, PYTHONPATH=f"{REPO}:{REPO / 'src'}", DATA_DIR=str(tmp_path / "data"))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "dagster",
            "asset",
            "materialize",
            "--select",
            select,
            "--partition",
            partition,
            "--module-name",
            "orchestration.definitions",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=REPO,
    )


def test_lineup_partition_and_diff(tmp_path):
    _seed(tmp_path)
    result = _materialize("lnr_staging_lineups", "J10|2024-2025", tmp_path)
    assert result.returncode == 0, result.stderr[-2000:]
    apps = pl.read_parquet(
        tmp_path / "data" / "staging" / "appearance/source=lnr/season=2024-2025" / "part.parquet"
    )
    assert apps.height == 46
    result = _materialize("allrugby_staging_matches", "2024-2025", tmp_path)
    assert result.returncode == 0, result.stderr[-2000:]
    result = _materialize("lnr_vs_allrugby", "2024-2025", tmp_path)
    assert result.returncode == 0, result.stderr[-2000:]
    report = pl.read_parquet(
        tmp_path / "data" / "staging" / "_reports" / "lineup_diff" / "season=2024-2025.parquet"
    )
    assert report.height == 2  # les deux côtés de la différence
    by_status = {r["status"]: r["player_name"] for r in report.iter_rows(named=True)}
    assert by_status["allrugby_only"] == "Pierrick ESPEUT"
    assert by_status["lnr_only"] == "Jack WILLIS"
