"""Tests for the cache namespace, fingerprint, and manifest contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topo.cache import ExperimentNamespace
from topo.cache import request_fingerprint
from topo.cache import validate_slug
from topo.exceptions import TopoValidationError
from topo.models import Area
from topo.models import TopoRequest


if TYPE_CHECKING:
    from pathlib import Path


def _request(east: float = -45.2) -> TopoRequest:
    return TopoRequest(area=Area(south=-0.8, north=-0.2, west=-46.2, east=east))


def test_fingerprint_excludes_name_and_tracks_fields() -> None:
    same = request_fingerprint({"region": _request()})
    assert same == request_fingerprint({"region": _request()})
    assert same != request_fingerprint({"region": _request(-45.3)})
    assert same != request_fingerprint({"other": _request()})


def test_slug_validation() -> None:
    assert validate_slug("topo-brasil") == "topo-brasil"
    for bad in ("", " ", "../escape", "a/b", ".hidden"):
        with pytest.raises(TopoValidationError):
            validate_slug(bad)


def test_namespace_paths(tmp_path: Path) -> None:
    namespace = ExperimentNamespace(tmp_path, "topo", "relief")
    assert namespace.pool_dir == tmp_path / ".cache" / "fragments" / "topo" / "v2"
    assert namespace.store_path("abc") == (
        tmp_path / ".cache" / "stores" / "topo" / "relief" / "abc.zarr"
    )


def test_pool_is_shared_across_namespaces(tmp_path: Path) -> None:
    first = ExperimentNamespace(tmp_path, "topo", "relief")
    second = ExperimentNamespace(tmp_path, "topo", "slope")
    assert first.pool_dir == second.pool_dir
    assert first.data_dir != second.data_dir


def test_store_path_tracks_fingerprint(tmp_path: Path) -> None:
    namespace = ExperimentNamespace(tmp_path, "topo", "relief")
    first = request_fingerprint({"region": _request()})
    second = request_fingerprint({"region": _request(-45.3)})
    assert namespace.store_path(first) != namespace.store_path(second)


def test_manifest_round_trip(tmp_path: Path) -> None:
    namespace = ExperimentNamespace(tmp_path, "topo", "relief")
    assert namespace.load_manifest() is None
    namespace.record_store(
        "fp1",
        requests={"region": {"type": "TopoRequest"}},
        coverage={"areas": [[-46.2, -0.8, -45.2, -0.2]], "products": ["ZN"]},
        provenance={"0": "published"},
        now="2026-09-18T12:00:00+00:00",
    )
    manifest = namespace.load_manifest()
    assert manifest is not None
    assert manifest.current == "fp1"
    assert manifest.stores["fp1"].coverage["products"] == ["ZN"]
    assert manifest.stores["fp1"].provenance == {"0": "published"}
