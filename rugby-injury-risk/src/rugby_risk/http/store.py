import hashlib
import os
import tempfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import zstandard

from rugby_risk.http.urls import canonicalize_url
from rugby_risk.settings import get_settings

MANIFEST_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "source": pl.String,
    "url_canonical": pl.String,
    "fetched_at": pl.Datetime(time_zone="UTC"),
    "status": pl.Int64,
    "sha256": pl.String,
    "content_type": pl.String,
    "size_bytes": pl.Int64,
    "etag": pl.String,
    "last_modified": pl.String,
}
EXTENSIONS = {"json": "json", "html": "html", "xml": "xml", "csv": "csv", "text": "txt"}


@dataclass(frozen=True)
class FetchResult:
    source: str
    url: str
    status: int
    content: bytes
    content_type: str
    sha256: str
    fetched_at: datetime
    from_cache: bool
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class ManifestRow:
    source: str
    url_canonical: str
    fetched_at: datetime
    status: int
    sha256: str
    content_type: str
    size_bytes: int
    etag: str | None
    last_modified: str | None


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _extension(content_type: str) -> str:
    return next((ext for key, ext in EXTENSIONS.items() if key in content_type.lower()), "bin")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        Path(tmp).replace(path)
    finally:
        Path(tmp).unlink(missing_ok=True)


class RawStore:
    """Append-only raw lake: `<root>/<source>/<yyyy>/<mm>/<sha256>.<ext>.zst` + manifest."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().data_dir / "raw"
        self.manifest_path = self.root / "_manifest.parquet"

    def _path(self, row: ManifestRow) -> Path:
        stamp = row.fetched_at
        name = f"{row.sha256}.{_extension(row.content_type)}.zst"
        return self.root / row.source / f"{stamp:%Y}" / f"{stamp:%m}" / name

    def put(self, result: FetchResult) -> Path:
        if sha256_of(result.content) != result.sha256:
            raise ValueError("sha256 does not match content")
        row = ManifestRow(
            result.source,
            canonicalize_url(result.url),
            result.fetched_at,
            result.status,
            result.sha256,
            result.content_type,
            len(result.content),
            result.etag,
            result.last_modified,
        )
        path = self._path(row)
        if path.exists():
            # Never rewrite: an existing hash file must already hold identical bytes.
            if zstandard.decompress(path.read_bytes()) != result.content:
                raise FileExistsError(f"Raw file is append-only: {path}")
        else:
            _atomic_write(path, zstandard.compress(result.content))
        self._append(row)
        return path

    def _append(self, row: ManifestRow) -> None:
        new = pl.DataFrame([asdict(row)], schema=MANIFEST_SCHEMA)
        frame = pl.concat([pl.read_parquet(self.manifest_path), new]) if self._exists() else new
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.manifest_path.parent, suffix=".tmp")
        os.close(fd)
        try:
            frame.write_parquet(tmp)
            Path(tmp).replace(self.manifest_path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def _exists(self) -> bool:
        return self.manifest_path.exists()

    def iter_manifest(self, source: str | None = None) -> Iterator[ManifestRow]:
        if not self._exists():
            return
        frame = pl.read_parquet(self.manifest_path)
        if source is not None:
            frame = frame.filter(pl.col("source") == source)
        for record in frame.iter_rows(named=True):
            yield ManifestRow(**record)

    def latest_row(self, source: str, url: str) -> ManifestRow | None:
        canonical = canonicalize_url(url)
        rows = [r for r in self.iter_manifest(source) if r.url_canonical == canonical]
        return max(rows, key=lambda r: r.fetched_at, default=None)

    def get_latest(self, source: str, url: str) -> FetchResult | None:
        row = self.latest_row(source, url)
        if row is None:
            return None
        content = zstandard.decompress(self._path(row).read_bytes())
        return FetchResult(
            source,
            row.url_canonical,
            row.status,
            content,
            row.content_type,
            row.sha256,
            row.fetched_at,
            True,
            row.etag,
            row.last_modified,
        )


def utcnow() -> datetime:
    return datetime.now(UTC)
