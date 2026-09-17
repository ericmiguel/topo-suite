"""Atomic Zarr v3 writers for dense and tile-partitioned stores."""

from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from topo.exceptions import MissingCoordinateError
from topo.exceptions import TopoValidationError
from topo.models import CATEGORICAL_PRODUCTS
from topo.models import CONTINUOUS_PRODUCTS
from topo.models import Product


if TYPE_CHECKING:
    from collections.abc import Sequence

    from topo.catalog import StacTile


def normalize_dataset(dataset: xr.Dataset) -> xr.Dataset:
    """Require ascending one-dimensional WGS84 coordinates."""
    _require_spatial_coordinates(dataset)
    normalized = dataset
    for coordinate in ("lat", "lon"):
        if normalized[coordinate].ndim != 1:
            raise TopoValidationError(
                f"Coordinate {coordinate!r} must be one-dimensional."
            )
        normalized = normalized.sortby(coordinate)
    normalized.attrs.setdefault("Conventions", "CF-1.10")
    normalized.attrs.setdefault("crs", "EPSG:4326")
    normalized.attrs.setdefault("source", "INPE TOPODATA v001")
    return normalized


def combine_datasets(datasets: Sequence[xr.Dataset]) -> xr.Dataset:
    """Mosaic spatial tile datasets by their latitude and longitude coordinates."""
    if not datasets:
        raise ValueError("At least one TOPODATA dataset is required.")
    if len(datasets) == 1:
        return normalize_dataset(datasets[0])
    try:
        combined = xr.combine_by_coords(
            tuple(normalize_dataset(dataset) for dataset in datasets),
            combine_attrs="override",
            fill_value=np.nan,
            join="outer",
        )
    except (ValueError, KeyError) as error:
        raise TopoValidationError(
            "TOPODATA tiles could not form one mosaic."
        ) from error
    if not isinstance(combined, xr.Dataset):
        raise TopoValidationError("TOPODATA mosaic did not produce a dataset.")
    combined = _restore_dtypes(combined)
    return normalize_dataset(combined)


def write_dense(
    datasets: Sequence[xr.Dataset], destination: Path, *, overwrite: bool = False
) -> Path:
    """Mosaic datasets and write one atomic dense Zarr v3 store."""
    return write_dataset(combine_datasets(datasets), destination, overwrite=overwrite)


def write_tiles(
    datasets: Sequence[tuple[str, xr.Dataset]],
    tiles: Sequence[StacTile],
    destination: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write an index and one dataset group per source tile."""
    if not datasets:
        raise ValueError("At least one TOPODATA tile dataset is required.")
    destination = Path(destination)
    temporary = _temporary_destination(destination, overwrite=overwrite)
    try:
        index = _tile_index(datasets, tiles)
        index.to_zarr(temporary, mode="w", zarr_format=3, consolidated=False)
        for key, dataset in datasets:
            normalize_dataset(dataset).to_zarr(
                temporary,
                group=f"tiles/{key}",
                mode="a",
                zarr_format=3,
                consolidated=False,
                encoding=_encoding(normalize_dataset(dataset)),
            )
        _commit(temporary, destination)
    finally:
        if temporary.exists():
            _remove_path(temporary)
    return destination


def write_dataset(
    dataset: xr.Dataset, destination: Path, *, overwrite: bool = False
) -> Path:
    """Write one dataset to an atomic Zarr v3 directory."""
    destination = Path(destination)
    temporary = _temporary_destination(destination, overwrite=overwrite)
    try:
        normalized = normalize_dataset(dataset)
        normalized.to_zarr(
            temporary,
            mode="w",
            zarr_format=3,
            consolidated=False,
            encoding=_encoding(normalized),
        )
        _commit(temporary, destination)
    finally:
        if temporary.exists():
            _remove_path(temporary)
    return destination


def _tile_index(
    datasets: Sequence[tuple[str, xr.Dataset]], tiles: Sequence[StacTile]
) -> xr.Dataset:
    """Build a small root index for partitioned stores."""
    by_id = {tile.item_id: tile for tile in tiles}
    entries = tuple(key.split("/", maxsplit=1)[-1] for key, _ in datasets)
    bounds = np.asarray([by_id[item].bbox for item in entries], dtype="float64")
    return xr.Dataset(
        {"bbox": (("tile", "bound"), bounds)},
        coords={
            "tile": ("tile", np.asarray(entries, dtype="U")),
            "bound": (
                "bound",
                np.asarray(("west", "south", "east", "north"), dtype="U"),
            ),
        },
        attrs={
            "layout": "tiles",
            "source": "INPE TOPODATA v001",
            "tile_groups": "tiles/<request>/<item_id>",
        },
    )


def _encoding(dataset: xr.Dataset) -> dict[str, dict[str, tuple[int, ...]]]:
    """Use COG-sized spatial chunks for the Zarr arrays."""
    chunks = {
        str(name): min(int(size), 512) or 1 for name, size in dataset.sizes.items()
    }
    return {
        str(name): {"chunks": tuple(chunks[str(dim)] for dim in variable.dims)}
        for name, variable in dataset.data_vars.items()
        if variable.dims
    }


def _restore_dtypes(dataset: xr.Dataset) -> xr.Dataset:
    """Keep categorical fields compact after outer-coordinate combination."""
    restored = dataset.copy()
    for product in CATEGORICAL_PRODUCTS:
        name = product.value
        if name in restored:
            restored[name] = restored[name].fillna(0).astype("uint8")
    for product in CONTINUOUS_PRODUCTS:
        name = product.value
        if name in restored:
            restored[name] = restored[name].astype("float32")
    for product in Product:
        name = f"{product.value}_valid"
        if name in restored:
            restored[name] = restored[name].fillna(False).astype(bool)
    return restored


def _require_spatial_coordinates(dataset: xr.Dataset) -> None:
    """Require canonical one-dimensional geographic coordinates."""
    for name, minimum, maximum in (("lat", -90, 90), ("lon", -180, 180)):
        if name not in dataset.coords:
            raise MissingCoordinateError(f"Dataset is missing {name!r} coordinate.")
        coordinate = dataset[name]
        if coordinate.ndim != 1:
            raise TopoValidationError(f"Coordinate {name!r} must be one-dimensional.")
        if float(coordinate.min()) < minimum or float(coordinate.max()) > maximum:
            raise TopoValidationError(f"Coordinate {name!r} is outside EPSG:4326.")


def _temporary_destination(destination: Path, *, overwrite: bool) -> Path:
    """Prepare an atomic temporary path."""
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.part")
    if temporary.exists():
        _remove_path(temporary)
    return temporary


def _commit(temporary: Path, destination: Path) -> None:
    """Replace the destination only after a complete write."""
    backup = destination.with_name(f".{destination.name}.old")
    if backup.exists():
        _remove_path(backup)
    if destination.exists():
        destination.rename(backup)
    try:
        temporary.rename(destination)
    except OSError:
        if backup.exists():
            backup.rename(destination)
        raise
    _remove_path(backup)


def _remove_path(path: Path) -> None:
    """Remove a temporary Zarr path."""
    if path.is_dir():
        rmtree(path)
    else:
        path.unlink(missing_ok=True)
