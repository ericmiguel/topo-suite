"""Offline experiment and Zarr tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import xarray as xr

from conftest import FakeFetcher
from conftest import FakeReader
from conftest import request
from topo import Experiment
from topo import Layout
from topo import StorageBudgetError


if TYPE_CHECKING:
    from pathlib import Path


def test_dense_experiment_writes_openable_store(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    """Manifest resolution and dense materialization produce a dataset."""
    experiment = Experiment(
        name="small",
        region=request(
            products=("ZN", "SN"),  # type: ignore[arg-type]
            layout=Layout.DENSE,
        ),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    assert len(experiment.download()) == 1
    store = experiment.to_zarr()
    with experiment.open() as dataset:
        assert store == experiment.store_path
        assert "ZN" in dataset
        assert "SN_valid" in dataset
        assert "time" not in dataset.dims


def test_tile_experiment_writes_partition_and_index(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    """The default layout keeps a tile group rather than a dense mosaic."""
    experiment = Experiment(
        name="tiles",
        region=request(),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    experiment.download()
    experiment.to_zarr()
    with experiment.open() as index:
        assert index.attrs["layout"] == "tiles"
        assert index.sizes["tile"] == 1
    with experiment.open_tile("region", "00S465") as tile:
        assert isinstance(tile, xr.Dataset)
        assert "ZN" in tile


def test_dense_budget_fails_before_reader(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    """Large dense stores are rejected before COG windows are read."""
    experiment = Experiment(
        name="too_large",
        region=request(layout=Layout.DENSE, dense_budget=1),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    experiment.download()
    with pytest.raises(StorageBudgetError):
        experiment.to_zarr()


def test_experiment_uses_namespaced_store_and_pool_manifests(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    """Stores are namespaced while the STAC tile manifest lives in the pool."""
    experiment = Experiment(
        name="layout",
        region=request(),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    assert experiment.cache_path == tmp_path / ".cache" / "fragments" / "topo" / "v2"
    assert experiment.cache_key == experiment.fingerprint
    assert experiment.store_path == (
        tmp_path
        / ".cache"
        / "stores"
        / "topo"
        / "layout"
        / f"{experiment.fingerprint}.zarr"
    )
    experiment.download()
    tile_manifest = experiment.cache_path / "manifest.json"
    assert tile_manifest.is_file()
    experiment.to_zarr()
    namespace_manifest = experiment.store_path.parent / "manifest.json"
    assert namespace_manifest.is_file()
    assert namespace_manifest != tile_manifest


def test_same_request_shares_pool_and_fingerprint_across_namespaces(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    """The name is a namespace, not part of the request fingerprint."""
    first = Experiment(
        name="alpha",
        region=request(),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    second = Experiment(
        name="beta",
        region=request(),
        downloader=fake_fetcher,
        reader=FakeReader(),
        root_dir=tmp_path,
    )
    assert first.fingerprint == second.fingerprint
    assert first.cache_path == second.cache_path
    assert first.store_path != second.store_path
