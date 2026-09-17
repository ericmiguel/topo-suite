"""STAC catalog resolution for TOPODATA tiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from topo.exceptions import NoDataAvailableError
from topo.exceptions import StacError
from topo.models import Area
from topo.models import Product


STAC_BASE = "https://data.inpe.br/bdc/stac/v1"
COLLECTION_ID = "topodata-1"
COLLECTION_URL = f"{STAC_BASE}/collections/{COLLECTION_ID}"
ITEMS_URL = f"{COLLECTION_URL}/items?limit=1000"


@dataclass(frozen=True, kw_only=True)
class StacAsset:
    """One resolved COG asset."""

    product: Product
    href: str
    size: int | None
    checksum: str | None


@dataclass(frozen=True, kw_only=True)
class StacTile:
    """One TOPODATA item and its 16 data assets."""

    item_id: str
    bbox: tuple[float, float, float, float]
    assets: Mapping[Product, StacAsset]


def parse_tiles(payload: object) -> tuple[StacTile, ...]:
    """Parse one STAC FeatureCollection into resolved tiles."""
    collection = _mapping(payload, "STAC response")
    features = collection.get("features")
    if not isinstance(features, list):
        raise StacError("STAC response has no 'features' array.")
    tiles = tuple(_parse_tile(feature) for feature in features)
    if not tiles:
        raise NoDataAvailableError("TOPODATA collection has no tiles.")
    return tiles


def tiles_for_area(payloads: tuple[object, ...], area: Area) -> tuple[StacTile, ...]:
    """Parse pages and retain tiles intersecting ``area``."""
    tiles = tuple(tile for payload in payloads for tile in parse_tiles(payload))
    selected = tuple(tile for tile in tiles if area.intersects(tile.bbox))
    if not selected:
        raise NoDataAvailableError(f"TOPODATA has no tile intersecting {area.bbox}.")
    return selected


def next_url(payload: object) -> str | None:
    """Return the STAC pagination URL, if the response has one."""
    response = _mapping(payload, "STAC response")
    links = response.get("links", ())
    if not isinstance(links, (list, tuple)):
        raise StacError("STAC response has invalid 'links'.")
    for link in links:
        entry = _mapping(link, "STAC link")
        if entry.get("rel") == "next":
            return _text(entry.get("href"), "next link href")
    return None


def _parse_tile(value: object) -> StacTile:
    """Parse a STAC feature and all expected raster assets."""
    feature = _mapping(value, "STAC feature")
    raw_bbox = feature.get("bbox")
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise StacError("TOPODATA feature has no four-value bbox.")
    try:
        bbox = tuple(float(item) for item in raw_bbox)
    except (TypeError, ValueError) as error:
        raise StacError("TOPODATA feature bbox is not numeric.") from error
    assets = _mapping(feature.get("assets"), "STAC assets")
    parsed: dict[Product, StacAsset] = {}
    for product in Product:
        entry = _mapping(assets.get(product.value), f"asset {product.value}")
        parsed[product] = StacAsset(
            product=product,
            href=_text(entry.get("href"), f"asset {product.value} href"),
            size=_optional_int(entry.get("bdc:size")),
            checksum=_optional_text(entry.get("checksum:multihash")),
        )
    return StacTile(
        item_id=_text(feature.get("id"), "STAC item id"),
        bbox=bbox,  # type: ignore[arg-type]
        assets=parsed,
    )


def _mapping(value: object, what: str) -> Mapping[str, object]:
    """Require a JSON object."""
    if not isinstance(value, Mapping):
        raise StacError(f"{what} is not a JSON object.")
    return value


def _text(value: object, what: str) -> str:
    """Require a non-empty string."""
    if not isinstance(value, str) or not value:
        raise StacError(f"{what} is missing or not a string.")
    return value


def _optional_text(value: object) -> str | None:
    """Return a string or ``None``."""
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    """Return an integer or ``None``."""
    return int(value) if isinstance(value, (int, float)) else None
