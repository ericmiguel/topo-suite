"""Offline STAC parsing tests."""

from __future__ import annotations

import pytest

from conftest import feature
from conftest import payload
from topo import Area
from topo import NoDataAvailableError
from topo import Product
from topo import StacError
from topo import parse_tiles
from topo import tiles_for_area


def test_parse_tiles_resolves_all_data_assets() -> None:
    """Every product is resolved from the STAC response."""
    tiles = parse_tiles(payload())
    assert len(tiles) == 1
    assert set(tiles[0].assets) == set(Product)
    assert tiles[0].assets[Product.ZN].href.endswith("ZN.tif")


def test_tiles_for_area_filters_intersections() -> None:
    """A non-intersecting area is not silently accepted."""
    area = Area(south=-0.8, north=-0.2, west=-46.2, east=-45.2)
    assert len(tiles_for_area((payload(),), area)) == 1
    with pytest.raises(NoDataAvailableError):
        tiles_for_area(
            ({"type": "FeatureCollection", "features": [feature("00S465")]},),
            Area(south=10, north=11, west=-46, east=-45),
        )


def test_parse_tiles_requires_every_product() -> None:
    """Missing source assets fail before any raster request."""
    broken = feature()
    del broken["assets"]["ZN"]  # type: ignore[index]
    with pytest.raises(StacError, match="ZN"):
        parse_tiles({"type": "FeatureCollection", "features": [broken]})
