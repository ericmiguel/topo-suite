"""Canonical dataset validation tests."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from topo import MissingCoordinateError
from topo import TopoValidationError
from topo import normalize_dataset


def test_normalize_sorts_coordinates_and_adds_provenance() -> None:
    """Mosaics expose ascending geographic coordinates."""
    dataset = xr.Dataset(
        {"ZN": (("lat", "lon"), np.ones((2, 2), dtype="float32"))},
        coords={"lat": [1.0, 0.0], "lon": [-45.0, -46.0]},
    )
    normalized = normalize_dataset(dataset)
    assert normalized["lat"].values.tolist() == [0.0, 1.0]
    assert normalized["lon"].values.tolist() == [-46.0, -45.0]
    assert normalized.attrs["crs"] == "EPSG:4326"


def test_normalize_requires_coordinates() -> None:
    """A non-spatial dataset cannot become a TOPODATA store."""
    with pytest.raises(MissingCoordinateError):
        normalize_dataset(xr.Dataset({"ZN": ("x", [1.0])}))


def test_normalize_rejects_invalid_coordinates() -> None:
    """Coordinates outside WGS84 are rejected."""
    dataset = xr.Dataset(
        {"ZN": (("lat", "lon"), np.ones((1, 1)))},
        coords={"lat": [95.0], "lon": [0.0]},
    )
    with pytest.raises(TopoValidationError, match="outside"):
        normalize_dataset(dataset)
