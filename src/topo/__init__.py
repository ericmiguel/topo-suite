"""Typed access to INPE TOPODATA geomorphometric products.

TOPODATA is static spatial data, not a time series. The collection's 2000 date
describes production metadata and is intentionally not written as a ``time``
coordinate. COGs are read through HTTP range requests and materialized as Zarr
v3 on demand.
"""

from topo.cache import experiment_cache_dir
from topo.cache import experiment_cache_key
from topo.cache import experiment_store_path
from topo.catalog import COLLECTION_ID
from topo.catalog import COLLECTION_URL
from topo.catalog import ITEMS_URL
from topo.catalog import STAC_BASE
from topo.catalog import StacAsset
from topo.catalog import StacTile
from topo.catalog import next_url
from topo.catalog import parse_tiles
from topo.catalog import tiles_for_area
from topo.events import ItemWritten
from topo.events import PipelineEvent
from topo.events import PipelineListener
from topo.events import RequestPlanned
from topo.events import TileRead
from topo.exceptions import DownloadError
from topo.exceptions import MissingCoordinateError
from topo.exceptions import NoDataAvailableError
from topo.exceptions import StacError
from topo.exceptions import StorageBudgetError
from topo.exceptions import TopoError
from topo.exceptions import TopoValidationError
from topo.experiment import Experiment
from topo.models import ALL_PRODUCTS
from topo.models import CATEGORICAL_PRODUCTS
from topo.models import CONTINUOUS_PRODUCTS
from topo.models import DEFAULT_DENSE_BUDGET
from topo.models import PRODUCT_SPECS
from topo.models import TOPO_COLLECTION_BBOX
from topo.models import TOPO_RESOLUTION
from topo.models import Area
from topo.models import Layout
from topo.models import Product
from topo.models import ProductSpec
from topo.models import TopoRequest
from topo.retrieval import Fetcher
from topo.retrieval import HttpxFetcher
from topo.retrieval import RasterioTileReader
from topo.retrieval import TileReader
from topo.root import ProjectRootNotFoundError
from topo.root import resolve_project_root
from topo.zarr import combine_datasets
from topo.zarr import normalize_dataset
from topo.zarr import write_dataset
from topo.zarr import write_dense
from topo.zarr import write_tiles


__all__ = [
    "ALL_PRODUCTS",
    "CATEGORICAL_PRODUCTS",
    "COLLECTION_ID",
    "COLLECTION_URL",
    "CONTINUOUS_PRODUCTS",
    "DEFAULT_DENSE_BUDGET",
    "ITEMS_URL",
    "PRODUCT_SPECS",
    "STAC_BASE",
    "TOPO_COLLECTION_BBOX",
    "TOPO_RESOLUTION",
    "Area",
    "DownloadError",
    "Experiment",
    "Fetcher",
    "HttpxFetcher",
    "ItemWritten",
    "Layout",
    "MissingCoordinateError",
    "NoDataAvailableError",
    "PipelineEvent",
    "PipelineListener",
    "Product",
    "ProductSpec",
    "ProjectRootNotFoundError",
    "RasterioTileReader",
    "RequestPlanned",
    "StacAsset",
    "StacError",
    "StacTile",
    "StorageBudgetError",
    "TileRead",
    "TileReader",
    "TopoError",
    "TopoRequest",
    "TopoValidationError",
    "combine_datasets",
    "experiment_cache_dir",
    "experiment_cache_key",
    "experiment_store_path",
    "next_url",
    "normalize_dataset",
    "parse_tiles",
    "resolve_project_root",
    "tiles_for_area",
    "write_dataset",
    "write_dense",
    "write_tiles",
]
