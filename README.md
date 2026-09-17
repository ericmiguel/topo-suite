# topo-suite

Data suite (leaf) for the INPE **TOPODATA** collection, package `topo`. It
resolves the BDC STAC catalog, reads the published Cloud Optimized GeoTIFFs by
HTTP windows, and materializes canonical Zarr v3 stores.

TOPODATA is useful for rainfall studies as a static physiographic covariate:
altitude and slope describe orographic forcing; aspect and hillshade describe
exposure; profile and plan curvature indicate flow acceleration and convergence;
landform and drainage classes provide categorical terrain context. It does not
contain forest cover. Combine it with a land-cover product when forest extent
is required.

The collection contains 556 tiles over Brazil, each at approximately one
arc-second (30 m), with 16 products:

- Continuous: `ZN` altitude (m), `SN` slope (%), `ON` aspect (degree), `VN` and
  `HN` curvature (1/m), and `RS` hillshade.
- Categorical: `DD`, `FT`, `H3`, `H5`, `OC`, `SA`, `SB`, `SC`, `V3`, and `V5`.

The STAC date (`2000-02-11` to `2000-02-22`) is production metadata. Stores do
not receive a time coordinate.

## Usage

```python
from topo import Area, Experiment, Layout, Product, TopoRequest

experiment = Experiment(
    name="serra_do_mar_topography",
    region=TopoRequest(
        area=Area(south=-24.5, north=-23.0, west=-48.0, east=-45.5),
        products=(Product.ZN, Product.SN, Product.ON, Product.HN),
        layout=Layout.DENSE,
    ),
)
experiment.download()  # resolves and caches the STAC manifest
experiment.to_zarr()  # reads only the COG windows intersecting the area
dataset = experiment.open()  # lat, lon; no time axis
```

For Brazil-wide or other large requests, use the default `Layout.TILES`. It
writes an index at the Zarr root and one dataset under
`tiles/<request>/<item_id>`, preserving the sparse source layout without
materializing hundreds of gigabytes of empty pixels:

```python
experiment = Experiment(
    name="topodata_brazil",
    brazil=TopoRequest(
        area=Area(south=-34, north=6, west=-75, east=-34.5),
        products=(Product.ZN, Product.SN),
    ),
)
experiment.download()
experiment.to_zarr()
index = experiment.open()
tile = experiment.open_tile("brazil", "00S465")
```

Dense requests are refused before transfer when their logical size, including
validity masks, exceeds `dense_budget` (32 GiB by default). Categorical fields
remain `uint8`; because the source advertises `-9999` nodata for `uint8`, every
product also has a boolean `<product>_valid` mask and invalid categorical pixels
are stored as zero.

## Quality

```bash
uv run ruff check .
uv run ruff format . --check
uv run pyrefly check
uv run pytest
```
