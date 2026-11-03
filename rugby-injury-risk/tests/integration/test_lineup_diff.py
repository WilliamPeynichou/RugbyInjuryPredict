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

pytestmark = pytest.mark.integration
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
    """Feuille allrugby (markup allrugby-1) pour le même match, avec UN joueur différent."""
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

    def rows(names, team, city):
        out = []
        for shirt, (name, pid) in enumerate(names, start=1):
            href = f"/joueurs/{name.lower().replace(' ', '-')}-{pid}.html"
            out.append(
                f'<tr><td class="n">{shirt}</td>'
                f'<td class="player-name"><a href="{href}">{name}</a></td>'
                f'<td class="minutes">80</td><td class="card"></td></tr>'
            )
        table = f'<table class="club_stats"><caption>{team} — {city}</caption>'
        return f"{table}<tbody>{''.join(out)}</tbody></table>"

    return (
        "<html><body>"
        '<div class="matchinfo"><h2><span class="home">Stade Toulousain</span> '
        '<span class="away">Union Bordeaux Bègles</span></h2>'
        '<span class="competition-seo">top14</span><span class="season">2024-2025</span>'
        '<span class="round">J10</span><span class="match-id">999</span>'
        '<span class="kickoff">21/12/2024 21:05</span>'
        '<div class="venue"><span itemprop="name">Stade Ernest-Wallon</span></div>'
        '<span class="score">27-19</span></div>'
        + rows(names, "Stade Toulousain", "Toulouse")
        + rows(away_names, "Union Bordeaux Bègles", "Bordeaux")
        + "</body></html>"
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
            canonicalize_url("https://www.allrugby.com/matches/999"),
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
