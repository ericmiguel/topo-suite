"""Typed TOPODATA requests and product metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from math import isfinite

from topo.exceptions import TopoValidationError


TOPO_RESOLUTION = 1.0 / 3600.0
TOPO_COLLECTION_BBOX = (-75.0, -34.0000038, -34.4999962, 6.0)
DEFAULT_DENSE_BUDGET = 32 * 1024**3


class Product(StrEnum):
    """One of the 16 non-thumbnail TOPODATA raster products."""

    DD = "DD"
    FT = "FT"
    H3 = "H3"
    H5 = "H5"
    HN = "HN"
    OC = "OC"
    ON = "ON"
    RS = "RS"
    SA = "SA"
    SB = "SB"
    SC = "SC"
    SN = "SN"
    V3 = "V3"
    V5 = "V5"
    VN = "VN"
    ZN = "ZN"


CONTINUOUS_PRODUCTS = (
    Product.HN,
    Product.ON,
    Product.RS,
    Product.SN,
    Product.VN,
    Product.ZN,
)
CATEGORICAL_PRODUCTS = tuple(
    product for product in Product if product not in CONTINUOUS_PRODUCTS
)
ALL_PRODUCTS = tuple(Product)


class Layout(StrEnum):
    """Physical organization of the consolidated Zarr store."""

    DENSE = "dense"
    TILES = "tiles"


@dataclass(frozen=True, kw_only=True)
class Area:
    """A longitude/latitude rectangle in the source ``EPSG:4326`` grid."""

    south: float
    north: float
    west: float
    east: float

    def __post_init__(self) -> None:
        """Validate finite, ordered bounds."""
        values = (self.south, self.north, self.west, self.east)
        if not all(isfinite(value) for value in values):
            raise TopoValidationError("Area bounds must be finite.")
        if not -90 <= self.south < self.north <= 90:
            raise TopoValidationError(
                "Latitude bounds must satisfy -90 <= south < north <= 90."
            )
        if not -180 <= self.west < self.east <= 180:
            raise TopoValidationError(
                "Longitude bounds must satisfy -180 <= west < east <= 180."
            )

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return the STAC bbox ordering ``west, south, east, north``."""
        return self.west, self.south, self.east, self.north

    def intersects(self, bbox: tuple[float, float, float, float]) -> bool:
        """Return whether this area intersects a ``west, south, east, north`` box."""
        west, south, east, north = bbox
        return (
            self.west < east
            and self.east > west
            and self.south < north
            and self.north > south
        )

    def clipped_to(self, bbox: tuple[float, float, float, float]) -> Area | None:
        """Return the intersection with a source tile bbox."""
        west, south, east, north = bbox
        if not self.intersects(bbox):
            return None
        return Area(
            south=max(self.south, south),
            north=min(self.north, north),
            west=max(self.west, west),
            east=min(self.east, east),
        )

    def pixel_shape(self) -> tuple[int, int]:
        """Estimate ``(latitude, longitude)`` pixels at one arc-second."""
        return ceil((self.north - self.south) / TOPO_RESOLUTION), ceil(
            (self.east - self.west) / TOPO_RESOLUTION
        )


@dataclass(frozen=True, kw_only=True)
class TopoRequest:
    """One validated TOPODATA spatial request.

    ``TILES`` is the default because the full Brazilian collection is sparse and
    would exceed hundreds of gigabytes when represented as a dense matrix.
    """

    area: Area
    products: tuple[Product, ...] = ALL_PRODUCTS
    layout: Layout = Layout.TILES
    dense_budget: int = DEFAULT_DENSE_BUDGET

    def __post_init__(self) -> None:
        """Normalize enum-valued fields and validate the storage budget."""
        if not isinstance(self.area, Area):
            raise TopoValidationError("TopoRequest area must be an Area.")
        products = tuple(Product(product) for product in self.products)
        if not products:
            raise TopoValidationError("At least one TOPODATA product is required.")
        if len(set(products)) != len(products):
            raise TopoValidationError("TOPODATA products cannot be repeated.")
        object.__setattr__(self, "products", products)
        object.__setattr__(self, "layout", Layout(self.layout))
        if self.dense_budget <= 0:
            raise TopoValidationError("Dense storage budget must be positive.")

    @property
    def estimated_dense_bytes(self) -> int:
        """Estimate logical bytes, including one validity mask per product."""
        lat, lon = self.area.pixel_shape()
        bytes_per_pixel = sum(
            4 if product in CONTINUOUS_PRODUCTS else 1 for product in self.products
        )
        return lat * lon * (bytes_per_pixel + len(self.products))


@dataclass(frozen=True, kw_only=True)
class ProductSpec:
    """Canonical metadata for one TOPODATA product."""

    product: Product
    long_name: str
    units: str
    continuous: bool


PRODUCT_SPECS = {
    Product.DD: ProductSpec(
        product=Product.DD,
        long_name="drainage divides and thalwegs",
        units="1",
        continuous=False,
    ),
    Product.FT: ProductSpec(
        product=Product.FT, long_name="landform class", units="1", continuous=False
    ),
    Product.H3: ProductSpec(
        product=Product.H3,
        long_name="horizontal curvature, 3 classes",
        units="1",
        continuous=False,
    ),
    Product.H5: ProductSpec(
        product=Product.H5,
        long_name="horizontal curvature, 5 classes",
        units="1",
        continuous=False,
    ),
    Product.HN: ProductSpec(
        product=Product.HN,
        long_name="horizontal curvature",
        units="1 m**-1",
        continuous=True,
    ),
    Product.OC: ProductSpec(
        product=Product.OC, long_name="aspect octant class", units="1", continuous=False
    ),
    Product.ON: ProductSpec(
        product=Product.ON, long_name="slope aspect", units="degree", continuous=True
    ),
    Product.RS: ProductSpec(
        product=Product.RS, long_name="hillshade", units="1", continuous=True
    ),
    Product.SA: ProductSpec(
        product=Product.SA,
        long_name="slope class, Marques 1971",
        units="1",
        continuous=False,
    ),
    Product.SB: ProductSpec(
        product=Product.SB,
        long_name="slope class, Lepsch 1991",
        units="1",
        continuous=False,
    ),
    Product.SC: ProductSpec(
        product=Product.SC,
        long_name="slope class, Embrapa 1999",
        units="1",
        continuous=False,
    ),
    Product.SN: ProductSpec(
        product=Product.SN, long_name="slope", units="percent", continuous=True
    ),
    Product.V3: ProductSpec(
        product=Product.V3,
        long_name="vertical curvature, 3 classes",
        units="1",
        continuous=False,
    ),
    Product.V5: ProductSpec(
        product=Product.V5,
        long_name="vertical curvature, 5 classes",
        units="1",
        continuous=False,
    ),
    Product.VN: ProductSpec(
        product=Product.VN,
        long_name="vertical curvature",
        units="1 m**-1",
        continuous=True,
    ),
    Product.ZN: ProductSpec(
        product=Product.ZN,
        long_name="orthometric elevation",
        units="m",
        continuous=True,
    ),
}
