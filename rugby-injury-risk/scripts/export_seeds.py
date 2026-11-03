"""Copy data/reference/*.csv to dbt/seeds/ref_*.csv and export config/seasons.yaml."""

import csv
from pathlib import Path

from rugby_risk.config.seasons import load_seasons

REF = Path("data/reference")
SEEDS = Path("dbt/seeds")
NAMES = ["positions", "competitions", "venues", "venue_surface", "test_windows", "rules_protection"]

SEEDS.mkdir(parents=True, exist_ok=True)
for name in NAMES:
    text = (REF / f"{name}.csv").read_text(encoding="utf-8")
    # Reference CSVs spell NULL out; seeds need empty cells.
    rows = [
        ["" if cell == "NULL" else cell for cell in row] for row in csv.reader(text.splitlines())
    ]
    with (SEEDS / f"ref_{name}.csv").open("w", newline="", encoding="utf-8") as out:
        csv.writer(out, lineterminator="\n").writerows(rows)
with (SEEDS / "ref_seasons.csv").open("w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file, lineterminator="\n")
    writer.writerow(["season_id", "start_date", "end_date", "is_covid_disrupted"])
    for s in load_seasons():
        writer.writerow([s.season_id, s.start_date, s.end_date, str(s.is_covid_disrupted).lower()])
