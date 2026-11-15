import pytest

from rugby_risk.modeling.validation import FINAL_TEST_SEASON, season_folds

pytestmark = pytest.mark.unit

SEASONS = [f"{y}-{y + 1}" for y in range(2014, 2027)]  # 2014-2015 .. 2026-2027


def test_no_test_season_in_train_and_order_respected():
    folds = season_folds(SEASONS, min_train_seasons=2)
    assert folds, "des folds doivent exister"
    for f in folds:
        assert f.test_season not in f.train_seasons
        assert f.valid_season not in f.train_seasons  # valid exclue du train
        assert SEASONS.index(f.valid_season) < SEASONS.index(f.test_season)
        for s in f.train_seasons:
            assert SEASONS.index(s) < SEASONS.index(f.valid_season)


def test_min_train_seasons_respected():
    folds = season_folds(SEASONS, min_train_seasons=2)
    assert all(len(f.train_seasons) >= 2 for f in folds)
    assert not season_folds(SEASONS[:3], min_train_seasons=5)


def test_final_season_excluded_without_flag():
    folds = season_folds(SEASONS, min_train_seasons=2)
    assert all(f.test_season != FINAL_TEST_SEASON for f in folds)
    allowed = season_folds(SEASONS, min_train_seasons=2, allow_final_test=True)
    assert any(f.test_season == FINAL_TEST_SEASON for f in allowed)


def test_covid_never_alone_in_test():
    covid = {"2019-2020"}
    folds = season_folds(SEASONS, min_train_seasons=2, covid_disrupted=covid)
    assert all(f.test_season != "2019-2020" for f in folds)
