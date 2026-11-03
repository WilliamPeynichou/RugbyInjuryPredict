from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from rugby_risk.errors import SourceNotAuthorizedError


class SourceDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_delay_seconds: float = Field(default=3.0, ge=1.0, allow_inf_nan=False)
    respect_robots: bool = True
    max_retries: int = Field(default=3, ge=0, le=5)


class SourceConfig(SourceDefaults):
    source_id: str = Field(min_length=1)
    authorized: bool = Field(default=False, strict=True)
    base_url: HttpUrl | None = None
    extra_hosts: list[str] = Field(default_factory=list)
    feeds: list[HttpUrl] = Field(default_factory=list)
    requires_api_key: bool = False
    user_agent_contact: str = ""
    notes_legal: str = ""

    @model_validator(mode="after")
    def require_endpoint(self) -> Self:
        if self.base_url is None and self.source_id != "news":
            raise ValueError("base_url is required for non-news sources")
        if self.authorized and self.base_url is None and not self.feeds:
            raise ValueError("An authorized source must have a base_url or feeds")
        return self


class SourcesRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1, le=1)
    defaults: SourceDefaults = Field(default_factory=SourceDefaults)
    sources: dict[str, SourceConfig]

    @model_validator(mode="after")
    def check_source_ids(self) -> Self:
        if any(key != source.source_id for key, source in self.sources.items()):
            raise ValueError("Source key must match source_id")
        return self


def load_sources(path: Path = Path("config/sources.yaml")) -> SourcesRegistry:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file)
    if not isinstance(document, dict) or not isinstance(document.get("sources"), dict):
        raise ValueError("Expected a mapping with sources")
    defaults = SourceDefaults.model_validate(document.get("defaults", {}))
    sources = {}
    for source_id, entry in document["sources"].items():
        if not isinstance(entry, dict):
            raise ValueError("Expected a mapping for each source")
        sources[source_id] = SourceConfig.model_validate(
            {**defaults.model_dump(), **entry, "source_id": source_id}
        )
    return SourcesRegistry.model_validate({**document, "defaults": defaults, "sources": sources})


def assert_authorized(source_id: str) -> SourceConfig:
    source = load_sources().sources.get(source_id)
    if source is None or not source.authorized:
        raise SourceNotAuthorizedError(f"Source not authorized: {source_id}")
    return source
