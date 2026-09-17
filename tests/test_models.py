"""Request validation tests."""

from __future__ import annotations

import pytest

from conftest import request
from topo import Area
from topo import Layout
from topo import Product
from topo import TopoRequest
from topo import TopoValidationError


def test_area_intersection_and_pixel_estimate() -> None:
    """Area helpers use source bbox ordering and arc-second resolution."""
    area = Area(south=-1, north=0, west=-46, east=-45)
    assert area.bbox == (-46, -1, -45, 0)
    assert area.intersects((-46.5, -1.5, -45.5, -0.5))
    assert area.pixel_shape() == (3600, 3600)


def test_request_accepts_raw_product_values() -> None:
    """Enum-valued fields are normalized at the boundary."""
    value = TopoRequest(
        area=Area(south=-1, north=0, west=-46, east=-45),
        products=("ZN",),  # type: ignore[arg-type]
        layout="dense",  # type: ignore[arg-type]
    )
    assert value.products == (Product.ZN,)
    assert value.layout is Layout.DENSE


def test_request_rejects_duplicate_products() -> None:
    """A source variable is requested at most once."""
    with pytest.raises(TopoValidationError, match="repeated"):
        TopoRequest(
            area=Area(south=-1, north=0, west=-46, east=-45),
            products=(Product.ZN, Product.ZN),
        )


def test_dense_budget_is_exposed_by_request() -> None:
    """The request exposes a predictable logical-size estimate."""
    value = request(layout=Layout.DENSE, dense_budget=1)
    assert value.estimated_dense_bytes > value.dense_budget
