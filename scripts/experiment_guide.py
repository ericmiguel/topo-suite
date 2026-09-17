"""Executable documentation for :mod:`topo`.

The guide follows the library from its public vocabulary to a lazy Xarray
dataset:

1. source facts and product groups;
2. validated spatial requests and dense-size estimates;
3. STAC item and asset resolution without constructing URLs by hand;
4. the dense and tile-partitioned store layouts;
5. a complete offline experiment using synthetic tiles;
6. an optional live catalog inspection and optional small COG materialization.

The default run is offline and writes temporary demonstration stores only::

    uv run scripts/experiment_guide.py

Inspect the real INPE catalog without reading COGs::

    uv run scripts/experiment_guide.py --network

Read a small real window and write a Zarr store under ``--root``::

    uv run scripts/experiment_guide.py --network --materialize --root .

The live example uses one small area inside tile ``00S465``. It deliberately
does not attempt a dense Brazil-wide mosaic: the full collection contains 556
tiles and is intended for the default tile-partitioned layout.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import xarray as xr

from topo import ALL_PRODUCTS
from topo import COLLECTION_URL
from topo import CONTINUOUS_PRODUCTS
from topo import DEFAULT_DENSE_BUDGET
from topo import ITEMS_URL
from topo import PRODUCT_SPECS
from topo import TOPO_COLLECTION_BBOX
from topo import TOPO_RESOLUTION
from topo import Area
from topo import Experiment
from topo import HttpxFetcher
from topo import Layout
from topo import Product
from topo import StacTile
from topo import TopoRequest
from topo import parse_tiles
from topo import tiles_for_area


GUIDE_AREA = Area(south=-0.2, north=-0.1, west=-46.3, east=-46.2)
GUIDE_PRODUCTS = (Product.ZN, Product.SN, Product.ON, Product.HN)


def main() -> None:
    """Run the complete documentation tour."""
    args = _parse_args()
    _print_header()
    section_source()
    section_requests()
    section_products()
    section_stac_offline()
    section_layouts()
    section_offline_experiment()
    if args.network:
        section_stac_network()
        if args.materialize:
            section_network_experiment(args.root)
    elif args.materialize:
        raise SystemExit("--materialize requires --network.")
    _rule()
    print("The default tour made no network request and left no permanent files.")


def _parse_args() -> argparse.Namespace:
    """Parse guide options."""
    parser = argparse.ArgumentParser(
        description="Executable documentation for the topo-suite library."
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="inspect the live INPE STAC catalog",
    )
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="read the small live COG window and write a Zarr store",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="root for the live materialized store (default: current directory)",
    )
    return parser.parse_args()


def _print_header() -> None:
    """Print the scope of the guide."""
    print("topo-suite executable guide")
    print("static INPE TOPODATA physiography -> windowed COG -> Zarr v3")


def _rule(title: str = "") -> None:
    """Print a plain section separator without a UI dependency."""
    print(f"\n--- {title} ---")


def section_source() -> None:
    """Explain what the source is and what it is not."""
    _rule("1 · source — static physiography, not a time series")
    print(f"  collection : {COLLECTION_URL}")
    print(f"  bbox       : {TOPO_COLLECTION_BBOX}")
    print(f"  resolution : {TOPO_RESOLUTION:.10f} degree (~30 m)")
    print("  temporal   : production metadata only; stores have no time axis")
    print(
        "  rainfall use: altitude, slope, exposure, curvature and drainage "
        "describe terrain-related forcing"
    )
    print(
        "  forest note : TOPODATA has no forest-cover variable; combine it with "
        "a land-cover dataset"
    )


def section_requests() -> None:
    """Demonstrate immutable request construction and budget checks."""
    _rule("2 · requests — typed areas and storage economics")
    area = Area(south=-24.5, north=-23.0, west=-48.0, east=-45.5)
    dense = TopoRequest(area=area, products=GUIDE_PRODUCTS, layout=Layout.DENSE)
    tiled = TopoRequest(area=area, products=GUIDE_PRODUCTS)
    print(f"  area       : {area.bbox} (west, south, east, north)")
    print(f"  products   : {[product.value for product in dense.products]}")
    print(f"  pixels     : {area.pixel_shape()} (estimated latitude, longitude)")
    print(f"  dense bytes: {dense.estimated_dense_bytes:,}")
    print(f"  budget     : {dense.dense_budget:,} ({DEFAULT_DENSE_BUDGET:,} default)")
    print(f"  dense mode : {dense.layout.value}")
    print(f"  broad mode : {tiled.layout.value} (the safe default)")
    print(
        "  validation : requests reject inverted bounds, empty products, "
        "duplicates and invalid budgets before network access"
    )


def section_products() -> None:
    """Print the canonical products and their physical meaning."""
    _rule("3 · products — continuous fields and categorical context")
    continuous = {product.value for product in CONTINUOUS_PRODUCTS}
    for product in ALL_PRODUCTS:
        spec = PRODUCT_SPECS[product]
        kind = "continuous" if product.value in continuous else "categorical"
        print(f"  {product.value:>2} · {kind:<11} · {spec.units:<8} · {spec.long_name}")
    print(
        "  dtype rule : continuous products are float32; categorical products are uint8"
    )
    print(
        "  nodata rule: every product has <product>_valid because -9999 cannot "
        "be represented by uint8"
    )


def section_stac_offline() -> None:
    """Show the STAC response shape with a small synthetic feature."""
    _rule("4 · STAC — assets come from the catalog")
    feature = _synthetic_feature()
    tiles = parse_tiles({"type": "FeatureCollection", "features": [feature]})
    tile = tiles[0]
    print("  item id    :", tile.item_id)
    print("  tile bbox  :", tile.bbox)
    print("  first asset:", tile.assets[Product.ZN].href)
    print(
        "  principle  : the suite resolves href, size and checksum from STAC; "
        "it never guesses a COG path"
    )


def section_layouts() -> None:
    """Explain how dense and partitioned stores differ."""
    _rule("5 · layouts — dense mosaic versus source tiles")
    print("  Layout.DENSE:")
    print("    one lat/lon dataset, convenient for small regional analysis")
    print("    refused before transfer when the logical byte budget is exceeded")
    print("  Layout.TILES:")
    print("    root index plus tiles/<request>/<item_id> Zarr groups")
    print("    preserves sparse Brazilian coverage and avoids empty pixels")
    print("  Experiment.open() returns the dense dataset or the tile index.")
    print("  Experiment.open_tile(request_name, item_id) opens one partition lazily.")


def section_offline_experiment() -> None:
    """Run both store layouts with an injected offline reader."""
    _rule("6 · experiment — download, materialize, open")
    print(
        "  The transport and COG reader are injectable. This section uses a "
        "synthetic STAC page and reader, so it is safe to run offline."
    )
    with TemporaryDirectory(prefix="topo-guide-") as temporary:
        root = Path(temporary)
        dense = _offline_experiment(root, Layout.DENSE)
        tiled = _offline_experiment(root, Layout.TILES)
        print(f"  dense store : {dense}")
        print(f"  tile store  : {tiled}")
        print("  temporary stores are removed when this section finishes")


def section_stac_network() -> None:
    """Inspect the live collection without reading raster bytes."""
    _rule("7 · network — live STAC inspection")
    fetcher = HttpxFetcher()
    try:
        payload = fetcher.get_json(ITEMS_URL)
    finally:
        fetcher.close()
    tiles = tiles_for_area((payload,), Area(south=-34, north=6, west=-75, east=-34.5))
    print(f"  selected tiles: {len(tiles)}")
    print(f"  first item    : {tiles[0].item_id}")
    print(f"  first ZN size : {tiles[0].assets[Product.ZN].size:,} bytes")
    print("  no COG was read; only the catalog was queried")


def section_network_experiment(root: Path) -> None:
    """Materialize a small real COG window into a user-selected root."""
    _rule("8 · network — a small real Zarr materialization")
    request = TopoRequest(
        area=GUIDE_AREA,
        products=GUIDE_PRODUCTS,
        layout=Layout.DENSE,
    )
    experiment = Experiment(name="guide-real-window", root_dir=root, region=request)
    tiles = experiment.download()
    store = experiment.to_zarr(overwrite=True)
    with experiment.open() as dataset:
        print(f"  resolved tiles: {len(tiles)}")
        print(f"  store         : {store}")
        print(f"  sizes         : {dict(dataset.sizes)}")
        print(f"  variables     : {sorted(str(name) for name in dataset.data_vars)}")
        print("  access        : lazy xarray Dataset via experiment.open()")


def _offline_experiment(root: Path, layout: Layout) -> Path:
    """Materialize one synthetic experiment in the selected layout."""
    experiment = Experiment(
        name=f"guide-{layout.value}",
        root_dir=root,
        downloader=_GuideFetcher(),
        reader=_GuideReader(),
        region=TopoRequest(area=GUIDE_AREA, products=GUIDE_PRODUCTS, layout=layout),
    )
    experiment.download()
    return experiment.to_zarr()


class _GuideFetcher:
    """Return one STAC page without making a network request."""

    def get_json(self, url: str) -> object:
        """Return the synthetic page and display the requested endpoint."""
        del url
        return {"type": "FeatureCollection", "features": [_synthetic_feature()]}


class _GuideReader:
    """Create small in-memory fields for the offline experiment."""

    def read(
        self, tile: StacTile, products: tuple[Product, ...], area: Area
    ) -> xr.Dataset:
        """Return one synthetic window with the canonical variable names."""
        del tile
        lat = np.linspace(area.south, area.north, 4)
        lon = np.linspace(area.west, area.east, 4)
        variables: dict[str, xr.DataArray] = {}
        for product in products:
            values = np.ones((4, 4), dtype="float32")
            variables[product.value] = xr.DataArray(
                values,
                dims=("lat", "lon"),
                coords={"lat": lat, "lon": lon},
            )
            variables[f"{product.value}_valid"] = xr.DataArray(
                np.ones((4, 4), dtype=bool),
                dims=("lat", "lon"),
                coords={"lat": lat, "lon": lon},
            )
        return xr.Dataset(variables)


def _synthetic_feature() -> dict[str, object]:
    """Build a compact STAC feature with all 16 data assets."""
    assets = {
        product.value: {
            "href": f"https://example.invalid/topodata/00S465{product.value}.tif",
            "bdc:size": 1,
            "checksum:multihash": "1220" + "0" * 64,
        }
        for product in ALL_PRODUCTS
    }
    return {
        "type": "Feature",
        "id": "00S465",
        "bbox": [-46.5, -1.0, -45.0, 0.0],
        "assets": assets,
    }


if __name__ == "__main__":
    main()
