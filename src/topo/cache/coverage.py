"""Coverage summaries for TOPODATA stores.

TOPODATA has no time axis: its fragments are source tiles, so the coverage
axes that matter are the requested areas, products, and storage layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topo.models import TopoRequest


if TYPE_CHECKING:
    from collections.abc import Mapping


GRID_SIGNATURE = "tile:1arcsec:topodata"


def summarize_coverage(requests: Mapping[str, object]) -> dict[str, object]:
    """Return the area, product, layout, and grid coverage of a request set."""
    areas: list[list[float]] = []
    products: dict[str, None] = {}
    layouts: dict[str, None] = {}
    for request in requests.values():
        if isinstance(request, TopoRequest):
            areas.append(list(request.area.bbox))
            for product in request.products:
                products.setdefault(product.value, None)
            layouts.setdefault(request.layout.value, None)
    return {
        "areas": areas,
        "products": sorted(products),
        "layouts": sorted(layouts),
        "grid": GRID_SIGNATURE,
    }
