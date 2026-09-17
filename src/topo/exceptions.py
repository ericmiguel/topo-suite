"""Exceptions raised by :mod:`topo`."""

from __future__ import annotations


class TopoError(Exception):
    """Base class for all TOPODATA errors."""


class TopoValidationError(TopoError, ValueError):
    """Raised when a request or decoded tile violates the contract."""


class StacError(TopoError):
    """Raised when the INPE BDC STAC response is malformed."""


class NoDataAvailableError(TopoError):
    """Raised when no TOPODATA tile intersects a requested area."""


class DownloadError(TopoError):
    """Raised when a remote COG cannot be read or verified."""


class MissingCoordinateError(TopoValidationError):
    """Raised when a decoded tile lacks a spatial coordinate."""


class StorageBudgetError(TopoValidationError):
    """Raised before a dense store exceeds its configured logical-size budget."""
