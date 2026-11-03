from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeasonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season_id: str = Field(pattern=r"^\d{4}-\d{4}$")
    start_date: date
    end_date: date
    is_covid_disrupted: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        start, end = (int(year) for year in self.season_id.split("-"))
        if end != start + 1 or self.start_date > self.end_date:
            raise ValueError("Invalid season interval")
        if self.start_date.year != start or self.end_date.year != end:
            raise ValueError("Season dates must match season_id years")
        return self


def load_seasons(path: Path = Path("config/seasons.yaml")) -> list[SeasonConfig]:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file)
    if not isinstance(document, dict) or not isinstance(document.get("seasons"), list):
        raise ValueError("Expected a mapping with seasons")
    seasons = sorted(
        (SeasonConfig.model_validate(entry) for entry in document["seasons"]),
        key=lambda season: season.start_date,
    )
    for previous, current in pairwise(seasons):
        if previous.end_date >= current.start_date:
            raise ValueError("Seasons must not overlap")
    return seasons


def season_for_date(d: date) -> str | None:
    return next(
        (
            season.season_id
            for season in load_seasons()
            if season.start_date <= d <= season.end_date
        ),
        None,
    )
