"""Experiment cache identity, namespaces, manifests, coverage, and provenance."""

from __future__ import annotations

from pathlib import Path

from topo.cache.coverage import GRID_SIGNATURE
from topo.cache.coverage import summarize_coverage
from topo.cache.identity import CACHE_SCHEMA_VERSION
from topo.cache.identity import CACHE_SOURCE
from topo.cache.identity import experiment_cache_key
from topo.cache.identity import normalize_dataclass
from topo.cache.identity import normalize_value
from topo.cache.identity import request_fingerprint
from topo.cache.manifest import ExperimentManifest
from topo.cache.manifest import StoreRecord
from topo.cache.namespace import ExperimentNamespace
from topo.cache.namespace import default_namespace
from topo.cache.namespace import validate_slug
from topo.cache.provenance import LEGEND
from topo.cache.provenance import PUBLISHED
from topo.cache.provenance import legend_payload


def experiment_cache_dir(cache_root: Path, cache_key: str) -> Path:
    """Return the legacy isolated cache directory for one experiment."""
    return Path(cache_root) / CACHE_SOURCE / cache_key


def experiment_store_path(data_root: Path, cache_key: str) -> Path:
    """Return the legacy canonical Zarr path for one experiment."""
    return Path(data_root) / CACHE_SOURCE / f"{cache_key}.zarr"


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "CACHE_SOURCE",
    "GRID_SIGNATURE",
    "LEGEND",
    "PUBLISHED",
    "ExperimentManifest",
    "ExperimentNamespace",
    "StoreRecord",
    "default_namespace",
    "experiment_cache_dir",
    "experiment_cache_key",
    "experiment_store_path",
    "legend_payload",
    "normalize_dataclass",
    "normalize_value",
    "request_fingerprint",
    "summarize_coverage",
    "validate_slug",
]
