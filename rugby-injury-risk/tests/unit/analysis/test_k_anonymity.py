from datetime import UTC, datetime

import polars as pl

from rugby_risk.analysis.sequences import K_MIN, build_report, suppress_small


def test_cells_under_k_players_are_dropped():
    cells = pl.DataFrame({"position_code": ["PROP", "HOOKER"], "n_players": [K_MIN, K_MIN - 1]})
    assert suppress_small(cells)["position_code"].to_list() == ["PROP"]


def test_small_position_absent_from_report(tmp_path):
    start = datetime(2024, 9, 7, tzinfo=UTC)
    rows = [
        {
            "player_id": i,
            "season_id": "2024-2025",
            "position_code": pos,
            "start_ts": start,
            "length": 3,
        }
        for pos, n in (("PROP", 10), ("HOOKER", 9))
        for i in range(n * (pos == "PROP"), n * (pos == "PROP") + n)
    ]
    report = build_report(pl.DataFrame(rows), pl.DataFrame(), tmp_path)
    assert "| PROP |" in report
    assert "HOOKER" not in report
