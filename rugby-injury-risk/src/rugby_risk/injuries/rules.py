"""Injury labelling rules from config/injury_rules.yaml, validated, exposed to dbt as vars."""

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

POSITION_GROUPS = ("front_row", "lock", "back_row", "half_back", "centre", "back_three")


class ExitSignalRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    early_exit_minute: dict[str, int]
    early_exit_strength: float = Field(ge=0, le=1)
    very_early_minute: int = Field(ge=0, le=80)
    very_early_strength: float = Field(ge=0, le=1)
    sub_off_strength: float = Field(ge=0, le=1)
    block_change_factor: float = Field(ge=0, le=1)
    absent_next_bonus: float = Field(ge=0, le=1)
    suspected_threshold: float = Field(ge=0, le=1)


class AbsenceSignalRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_matches_injury_candidate: int = Field(ge=1)
    suspension_max_matches: int = Field(ge=1)
    protected_rest_max_matches: int = Field(ge=1)
    exit_link_threshold: float = Field(ge=0, le=1)
    intl_history_days: int = Field(ge=0)


class InjuryRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_signal: ExitSignalRules
    absence_signal: AbsenceSignalRules


def load_rules(path: Path = Path("config/injury_rules.yaml")) -> InjuryRules:
    rules = InjuryRules.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    missing = set(POSITION_GROUPS) - set(rules.exit_signal.early_exit_minute)
    if missing:
        raise ValueError(f"early_exit_minute sans seuil pour: {sorted(missing)}")
    return rules


def dbt_vars(path: Path = Path("config/injury_rules.yaml")) -> dict[str, object]:
    return load_rules(path).model_dump()


if __name__ == "__main__":  # used by `make dbt`: --vars "$(python -m rugby_risk.injuries.rules)"
    print(json.dumps(dbt_vars()))
