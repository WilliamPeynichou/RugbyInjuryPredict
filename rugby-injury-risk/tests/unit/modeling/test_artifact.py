"""F30 : persistance M2 — aller-retour fidèle, rien de nominatif, altération détectée."""

import dataclasses
import json

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.artifact import (
    ArtifactError,
    is_promoted,
    latest_artifact,
    load_hierarchical,
    save_hierarchical,
)
from rugby_risk.modeling.hierarchical import FAST_SAMPLER
from rugby_risk.modeling.profile import PositionProfile, profile_frame
from tests.hazard_factory import hierarchical_frame
from tests.unit.modeling.test_profile import fitted_model

pytestmark = pytest.mark.unit

TRAIN = hierarchical_frame(players=120, seasons=1, matches=12, seed=3)


def _save(model, root):
    return save_hierarchical(
        model, TRAIN, seasons=("2020-2021",), dataset_version="synthetic", git_sha="abc", root=root
    )


def test_round_trip_same_predictions(tmp_path) -> None:
    model = fitted_model()
    directory = _save(model, tmp_path)
    loaded, meta = load_hierarchical(directory)
    frame = profile_frame(model, PositionProfile("HOOKER", horizon=5))
    np.testing.assert_allclose(loaded.predict_draws(frame), model.predict_draws(frame))
    assert loaded.status == "ok"
    assert meta["dataset_version"] == "synthetic"
    assert latest_artifact(tmp_path) == directory
    assert not is_promoted(directory)
    (directory / "PROMOTION.md").write_text("décision humaine", encoding="utf-8")
    assert is_promoted(directory)


def test_nothing_nominative_persisted(tmp_path) -> None:
    directory = _save(fitted_model(), tmp_path)
    frame = pl.read_parquet(directory / "design_frame.parquet")
    banned = {"player_key", "player_id", "match_id", "team_id", "y_injury", "kickoff_ts"}
    assert not set(frame.columns) & banned
    meta_text = (directory / "meta.json").read_text(encoding="utf-8")
    assert "p0001" not in meta_text
    with np.load(directory / "draws.npz") as npz:
        assert "player_effect" not in npz.files and "team_effect" not in npz.files


def test_tampered_transform_detected(tmp_path) -> None:
    directory = _save(fitted_model(), tmp_path)
    meta_path = directory / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    first = next(iter(meta["transform"]["medians"]))
    meta["transform"]["medians"][first] += 1.0
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ArtifactError, match="altéré"):
        load_hierarchical(directory)


def test_unfitted_and_fast_refused(tmp_path) -> None:
    from rugby_risk.modeling.hierarchical import HierarchicalHazardModel  # noqa: PLC0415

    with pytest.raises(ArtifactError, match="non ajusté"):
        _save(HierarchicalHazardModel(ipw=False), tmp_path)
    fast = fitted_model()
    fast.sampler = dataclasses.replace(FAST_SAMPLER)
    with pytest.raises(ArtifactError, match="fast"):
        _save(fast, tmp_path)


def test_no_artifact_message(tmp_path) -> None:
    with pytest.raises(ArtifactError, match="fit-final"):
        latest_artifact(tmp_path / "absent")
