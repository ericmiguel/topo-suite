"""Offline fixtures for the TOPODATA suite."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from topo import ALL_PRODUCTS
from topo import Area
from topo import Product
from topo import StacTile
from topo import TopoRequest


def feature(item_id: str = "00S465") -> dict[str, object]:
    """Return a compact STAC feature with all data assets."""
    assets = {
        product.value: {
            "href": f"https://data.inpe.br/bdc/data/{item_id}{product.value}.tif",
            "bdc:size": 100,
            "checksum:multihash": "1220" + "0" * 64,
        }
        for product in ALL_PRODUCTS
    }
    return {
        "type": "Feature",
        "id": item_id,
        "bbox": [-46.5, -1.0, -45.0, 0.0],
        "assets": assets,
    }


def payload() -> dict[str, object]:
    """Return one-page STAC response."""
    return {"type": "FeatureCollection", "features": [feature()]}


def request(
    area: Area | None = None,
    *,
    products: tuple[Product, ...] = (Product.ZN,),
    layout: str | None = None,
    dense_budget: int | None = None,
) -> TopoRequest:
    """Build a small valid request."""
    values: dict[str, object] = {
        "area": area or Area(south=-0.8, north=-0.2, west=-46.2, east=-45.2),
        "products": products,
    }
    if layout is not None:
        values["layout"] = layout
    if dense_budget is not None:
        values["dense_budget"] = dense_budget
    return TopoRequest(**values)  # type: ignore[arg-type]


class FakeFetcher:
    """Return one synthetic STAC page."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json(self, url: str) -> object:
        """Record the URL and return the fixture page."""
        self.urls.append(url)
        return payload()


class FakeReader:
    """Produce two-pixel windows without requiring GDAL in tests."""

    def read(
        self, tile: StacTile, products: tuple[Product, ...], area: Area
    ) -> xr.Dataset:
        """Return a synthetic dataset for the requested products."""
        del tile
        lat = np.array([area.south + 0.1, area.north - 0.1])
        lon = np.array([area.west + 0.1, area.east - 0.1])
        variables: dict[str, xr.DataArray] = {}
        for product in products:
            values = np.ones((2, 2), dtype="float32")
            variables[product.value] = xr.DataArray(
                values, dims=("lat", "lon"), coords={"lat": lat, "lon": lon}
            )
            variables[f"{product.value}_valid"] = xr.DataArray(
                np.ones((2, 2), dtype=bool),
                dims=("lat", "lon"),
                coords={"lat": lat, "lon": lon},
            )
        return xr.Dataset(variables)


@pytest.fixture
def fake_fetcher() -> FakeFetcher:
    """Return a fake STAC transport."""
    return FakeFetcher()
