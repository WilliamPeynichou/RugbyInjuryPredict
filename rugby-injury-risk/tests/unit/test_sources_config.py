from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from rugby_risk.config.sources import (
    SourceConfig,
    SourcesRegistry,
    assert_authorized,
    load_sources,
)
from rugby_risk.errors import SourceNotAuthorizedError

pytestmark = pytest.mark.unit


def test_repository_registry():
    registry = load_sources()
    assert set(registry.sources) == {
        "allrugby",
        "lnr",
        "itsrugby",
        "espn",
        "worldrugby",
        "apisports",
        "sportradar",
        "wikipedia",
        "news",
    }
    assert all(not source.authorized for source in registry.sources.values())
    assert registry.sources["lnr"].min_delay_seconds == registry.defaults.min_delay_seconds
    expected_espn_delay = 2.0
    assert registry.sources["espn"].min_delay_seconds == expected_espn_delay
    assert registry.sources["lnr"].extra_hosts == ["prod2.lnr.fr", "www.lnr.fr"]
    assert registry.sources["apisports"].requires_api_key


@pytest.mark.parametrize("source_id", ["lnr", "unknown", "wikipedia"])
def test_authorization_denied(source_id):
    with pytest.raises(SourceNotAuthorizedError, match=source_id):
        assert_authorized(source_id)


def test_authorization_accepts_explicit_permission(monkeypatch, tmp_path):
    # Synthetic local configuration; never changes repository permissions.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/sources.yaml").write_text(
        "sources:\n  example:\n    base_url: https://example.com\n    authorized: true\n"
    )
    assert assert_authorized("example").authorized


@pytest.mark.parametrize(
    "override",
    [
        {"min_delay_seconds": 0.5},
        {"min_delay_seconds": float("inf")},
        {"max_retries": 6},
        {"max_retries": -1},
        {"base_url": "not-a-url"},
        {"authorized": "yes"},
        {"unexpected": True},
    ],
)
def test_invalid_source_values(override):
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(
            {"source_id": "example", "base_url": "https://example.com", **override}
        )


@pytest.mark.parametrize(
    "entry", [{"source_id": "example"}, {"source_id": "news", "authorized": True}]
)
def test_missing_endpoint(entry):
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(entry)


def test_news_with_feeds():
    source = SourceConfig(source_id="news", authorized=True, feeds=["https://example.com/rss"])
    assert source.base_url is None


@pytest.mark.parametrize("document", [None, [], {"sources": []}, {"sources": {"example": None}}])
def test_invalid_documents(tmp_path, document):
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError):
        load_sources(path)


def test_invalid_defaults(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("defaults:\n  min_delay_seconds: 0\nsources: {}\n")
    with pytest.raises(ValidationError):
        load_sources(path)


def test_registry_rejects_mismatched_id():
    source = SourceConfig(source_id="news")
    with pytest.raises(ValidationError, match="Source key must match"):
        SourcesRegistry(sources={"other": source})


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_sources(Path(tmp_path / "missing.yaml"))
