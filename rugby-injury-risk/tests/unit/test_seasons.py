from datetime import date

import pytest
import yaml
from pydantic import ValidationError

from rugby_risk.config.seasons import SeasonConfig, load_seasons, season_for_date

pytestmark = pytest.mark.unit


def test_repository_seasons():
    seasons = load_seasons()
    assert seasons[0].season_id == "2013-2014"
    assert seasons[-1].season_id == "2026-2027"
    assert next(s for s in seasons if s.season_id == "2019-2020").is_covid_disrupted
    assert not seasons[0].is_covid_disrupted


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 3), "2026-2027"),
        (date(2026, 6, 30), "2025-2026"),
        (date(2026, 7, 1), "2026-2027"),
        (date(2013, 6, 30), None),
        (date(2027, 7, 1), None),
    ],
)
def test_season_for_date(day, expected):
    assert season_for_date(day) == expected


@pytest.mark.parametrize(
    "override",
    [
        {"season_id": "invalid"},
        {"season_id": "2025-2027"},
        {"start_date": "2027-07-01"},
        {"end_date": "2025-06-30"},
        {"end_date": "2028-06-30"},
    ],
)
def test_invalid_season(override):
    with pytest.raises(ValidationError):
        SeasonConfig.model_validate(
            {
                "season_id": "2026-2027",
                "start_date": "2026-07-01",
                "end_date": "2027-06-30",
                **override,
            }
        )


@pytest.mark.parametrize("document", [None, [], {"seasons": {}}])
def test_invalid_document(tmp_path, document):
    path = tmp_path / "seasons.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError):
        load_seasons(path)


def test_overlapping_seasons(tmp_path):
    path = tmp_path / "seasons.yaml"
    path.write_text(
        "seasons:\n"
        "- {season_id: 2025-2026, start_date: 2025-07-01, end_date: 2026-07-01}\n"
        "- {season_id: 2026-2027, start_date: 2026-07-01, end_date: 2027-06-30}\n"
    )
    with pytest.raises(ValueError, match="overlap"):
        load_seasons(path)
