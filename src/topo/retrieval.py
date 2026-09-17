"""HTTP and COG window retrieval for TOPODATA."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

import httpx
import numpy as np
import xarray as xr
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from topo.exceptions import DownloadError
from topo.models import PRODUCT_SPECS
from topo.models import Area
from topo.models import Product


if TYPE_CHECKING:
    from topo.catalog import StacTile


class Fetcher(Protocol):
    """Small transport seam used by catalog and network tests."""

    def get_json(self, url: str) -> object:
        """Return decoded JSON."""


class TileReader(Protocol):
    """Reader seam for offline tests and alternate COG backends."""

    def read(
        self, tile: StacTile, products: tuple[Product, ...], area: Area
    ) -> xr.Dataset:
        """Read one spatial window from the selected tile."""


class HttpxFetcher:
    """HTTP JSON client with bounded retries."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=10, read=60, write=60, pool=10),
            follow_redirects=True,
        )

    def get_json(self, url: str) -> object:
        """Fetch and decode one STAC page."""
        response = self._request(url)
        try:
            return response.json()
        except ValueError as error:
            raise DownloadError(f"Invalid JSON from {url}.") from error

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def _request(self, url: str) -> httpx.Response:
        """Get one URL, retrying transport and server failures."""
        response = self._client.get(url)
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        response.raise_for_status()
        return response

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


class RasterioTileReader:
    """Read COG windows through GDAL's HTTP range requests."""

    def read(
        self, tile: StacTile, products: tuple[Product, ...], area: Area
    ) -> xr.Dataset:
        """Read only the part of each COG intersecting ``area``."""
        import rasterio

        datasets: list[xr.Dataset] = []
        for product in products:
            asset = tile.assets[product]
            try:
                with rasterio.open(asset.href) as source:
                    window = source.window(*area.bbox).round_offsets().round_lengths()
                    values = source.read(1, window=window, masked=False)
                    valid = source.read_masks(1, window=window) > 0
                    transform = source.window_transform(window)
            except (OSError, ValueError, rasterio.errors.RasterioIOError) as error:
                raise DownloadError(
                    f"Could not read TOPODATA asset {asset.href}."
                ) from error
            datasets.append(_array_dataset(product, values, valid, transform))
        return xr.merge(datasets, compat="override", combine_attrs="override")


def _array_dataset(
    product: Product,
    values: np.ndarray,
    valid: np.ndarray,
    transform: object,
) -> xr.Dataset:
    """Build canonical variables and a validity mask from one raster window."""
    from rasterio.transform import Affine

    if not isinstance(transform, Affine) or values.ndim != 2:
        raise DownloadError(f"Invalid raster window for product {product.value}.")
    height, width = values.shape
    lon = transform.c + (np.arange(width, dtype="float64") + 0.5) * transform.a
    lat = transform.f + (np.arange(height, dtype="float64") + 0.5) * transform.e
    if lat.size > 1 and lat[0] > lat[-1]:
        lat = lat[::-1]
        values = values[::-1]
        valid = valid[::-1]
    spec = PRODUCT_SPECS[product]
    if spec.continuous:
        data = values.astype("float32", copy=False)
        data = np.where(valid, data, np.nan)
    else:
        data = values.astype("uint8", copy=False)
        data = np.where(valid, data, 0).astype("uint8")
    field = xr.DataArray(
        data, dims=("lat", "lon"), coords={"lat": lat, "lon": lon}, name=product.value
    )
    field.attrs.update(
        {
            "long_name": spec.long_name,
            "units": spec.units,
            "source_product": product.value,
        }
    )
    mask = xr.DataArray(
        valid,
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},
        name=f"{product.value}_valid",
    )
    mask.attrs["long_name"] = f"valid-data mask for {product.value}"
    return xr.Dataset({product.value: field, mask.name: mask})


__all__ = ["Fetcher", "HttpxFetcher", "RasterioTileReader", "TileReader"]
