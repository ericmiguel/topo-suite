"""TOPODATA experiment orchestration."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import xarray as xr

from topo.cache import experiment_cache_dir
from topo.cache import experiment_cache_key
from topo.cache import experiment_store_path
from topo.catalog import ITEMS_URL
from topo.catalog import StacTile
from topo.catalog import next_url
from topo.catalog import tiles_for_area
from topo.events import ItemWritten
from topo.events import PipelineListener
from topo.events import RequestPlanned
from topo.events import TileRead
from topo.exceptions import StorageBudgetError
from topo.exceptions import TopoValidationError
from topo.models import Layout
from topo.models import TopoRequest
from topo.retrieval import HttpxFetcher
from topo.retrieval import RasterioTileReader
from topo.retrieval import TileReader
from topo.root import resolve_project_root
from topo.zarr import write_dense
from topo.zarr import write_tiles


if TYPE_CHECKING:
    from pathlib import Path

    from topo.retrieval import Fetcher


class Experiment:
    """Resolve TOPODATA tiles and materialize a spatial Zarr v3 store.

    ``download`` resolves and caches a STAC manifest. Raster bytes are fetched
    as COG windows during ``to_zarr``; downloading full Brazilian tiles by
    default would waste hundreds of gigabytes when a request covers a small
    region.
    """

    def __init__(
        self,
        *,
        name: str,
        downloader: Fetcher | None = None,
        reader: TileReader | None = None,
        root_dir: Path | None = None,
        **requests: TopoRequest,
    ) -> None:
        if not name.strip():
            raise TopoValidationError("Experiment name cannot be empty.")
        if not requests:
            raise TopoValidationError("At least one named request is required.")
        if any(not isinstance(request, TopoRequest) for request in requests.values()):
            raise TopoValidationError("Experiment requests must be TopoRequests.")
        layouts = {request.layout for request in requests.values()}
        if len(layouts) != 1:
            raise TopoValidationError("All requests must use the same Zarr layout.")
        self.name = name
        self.requests = dict(requests)
        self.root_dir = resolve_project_root(root_dir)
        self.fetcher = downloader or HttpxFetcher()
        self.reader = reader or RasterioTileReader()
        self._cache_key = experiment_cache_key(name, self.requests)
        self._tiles: dict[str, tuple[StacTile, ...]] = {}
        self._store_path: Path | None = None
        self._logger = logging.getLogger(__name__)

    @property
    def cache_key(self) -> str:
        """Return the isolated experiment key."""
        return self._cache_key

    @property
    def cache_path(self) -> Path:
        """Return the manifest cache directory."""
        return experiment_cache_dir(self.root_dir / ".cache", self._cache_key)

    @property
    def store_path(self) -> Path:
        """Return the canonical Zarr path."""
        return experiment_store_path(self.root_dir / "data", self._cache_key)

    @property
    def layout(self) -> Layout:
        """Return the common request layout."""
        return next(iter(self.requests.values())).layout

    def download(
        self, *, listener: PipelineListener | None = None
    ) -> tuple[StacTile, ...]:
        """Resolve selected items and cache their STAC manifest."""
        self.cache_path.mkdir(parents=True, exist_ok=True)
        all_tiles: list[StacTile] = []
        for request_name, request in self.requests.items():
            tiles = self._resolve(request)
            self._tiles[request_name] = tiles
            all_tiles.extend(tiles)
            if listener is not None:
                listener(
                    RequestPlanned(
                        name=request_name,
                        tiles=len(tiles),
                        products=len(request.products),
                    )
                )
        manifest = self.cache_path / "manifest.json"
        manifest.write_text(
            json.dumps(_manifest(self._tiles), indent=2), encoding="utf-8"
        )
        unique = {tile.item_id: tile for tile in all_tiles}
        return tuple(unique.values())

    def to_zarr(
        self, *, overwrite: bool = False, listener: PipelineListener | None = None
    ) -> Path:
        """Read requested windows and write the configured Zarr store."""
        if not self._tiles:
            raise RuntimeError("Call download() before to_zarr().")
        if self.layout is Layout.DENSE:
            estimate = sum(
                request.estimated_dense_bytes for request in self.requests.values()
            )
            budget = min(request.dense_budget for request in self.requests.values())
            if estimate > budget:
                raise StorageBudgetError(
                    f"Dense TOPODATA store estimate is {estimate} bytes, above budget {budget}."
                )
        datasets: list[xr.Dataset] = []
        partitioned: list[tuple[str, xr.Dataset]] = []
        source_tiles = tuple(tile for tiles in self._tiles.values() for tile in tiles)
        for request_name, request in self.requests.items():
            for tile in self._tiles[request_name]:
                clipped = request.area.clipped_to(tile.bbox)
                if clipped is None:
                    continue
                dataset = self.reader.read(tile, request.products, clipped)
                if listener is not None:
                    listener(TileRead(request=request_name, item=tile.item_id))
                if self.layout is Layout.DENSE:
                    datasets.append(dataset)
                else:
                    partitioned.append((f"{request_name}/{tile.item_id}", dataset))
        if self.layout is Layout.DENSE:
            destination = write_dense(datasets, self.store_path, overwrite=overwrite)
        else:
            destination = write_tiles(
                partitioned, source_tiles, self.store_path, overwrite=overwrite
            )
        self._store_path = destination
        if listener is not None:
            listener(ItemWritten(description=str(destination), path=destination))
        self._logger.info("Wrote TOPODATA Zarr store %s.", destination)
        return destination

    def open(self) -> xr.Dataset:
        """Open the dense dataset or tile index lazily."""
        if self._store_path is None:
            raise RuntimeError("Call to_zarr() before open().")
        return xr.open_zarr(self._store_path, consolidated=False)

    def open_tile(self, request_name: str, item_id: str) -> xr.Dataset:
        """Open one partition from a tile-layout store lazily."""
        if self._store_path is None:
            raise RuntimeError("Call to_zarr() before open_tile().")
        return xr.open_zarr(
            self._store_path,
            group=f"tiles/{request_name}/{item_id}",
            consolidated=False,
        )

    def _resolve(self, request: TopoRequest) -> tuple[StacTile, ...]:
        """Fetch every STAC page and select tiles intersecting the request."""
        payloads: list[object] = []
        url: str | None = ITEMS_URL
        visited: set[str] = set()
        while url is not None:
            if url in visited:
                raise TopoValidationError("STAC pagination contains a cycle.")
            visited.add(url)
            payload = self.fetcher.get_json(url)
            payloads.append(payload)
            url = next_url(payload)
        return tiles_for_area(tuple(payloads), request.area)


def _manifest(tiles_by_request: dict[str, tuple[StacTile, ...]]) -> dict[str, object]:
    """Serialize the resolved STAC metadata without binary raster data."""
    return {
        request: [
            {
                "id": tile.item_id,
                "bbox": tile.bbox,
                "assets": {
                    product.value: {
                        "href": asset.href,
                        "size": asset.size,
                        "checksum": asset.checksum,
                    }
                    for product, asset in tile.assets.items()
                },
            }
            for tile in tiles
        ]
        for request, tiles in tiles_by_request.items()
    }
