"""Experiment cache identity and paths."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from topo.models import TopoRequest


CACHE_SOURCE = "topo"
SCHEMA_VERSION = 1


def experiment_cache_key(name: str, requests: dict[str, TopoRequest]) -> str:
    """Return a stable key for experiment name and request fields."""
    identity = {
        "schema": SCHEMA_VERSION,
        "source": CACHE_SOURCE,
        "name": name,
        "requests": {
            key: _request_data(value) for key, value in sorted(requests.items())
        },
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def experiment_cache_dir(cache_root: Path, key: str) -> Path:
    """Return one isolated manifest directory."""
    return Path(cache_root) / CACHE_SOURCE / key


def experiment_store_path(data_root: Path, key: str) -> Path:
    """Return one canonical Zarr path."""
    return Path(data_root) / CACHE_SOURCE / f"{key}.zarr"


def _request_data(request: TopoRequest) -> dict[str, object]:
    """Convert a request into JSON-safe identity data."""
    return {
        "area": asdict(request.area),
        "products": tuple(product.value for product in request.products),
        "layout": request.layout.value,
        "dense_budget": request.dense_budget,
    }
