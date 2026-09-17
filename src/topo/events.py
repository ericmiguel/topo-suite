"""Typed events emitted by the TOPODATA pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class RequestPlanned:
    """One named request was resolved to source tiles."""

    name: str
    tiles: int
    products: int


@dataclass(frozen=True, kw_only=True)
class TileRead:
    """One spatial COG window was decoded."""

    request: str
    item: str


@dataclass(frozen=True, kw_only=True)
class ItemWritten:
    """The experiment store was written."""

    description: str
    path: Path


type PipelineEvent = RequestPlanned | TileRead | ItemWritten
"""Union of events emitted by the pipeline."""

type PipelineListener = Callable[[PipelineEvent], None]
"""Subscriber receiving pipeline events."""
