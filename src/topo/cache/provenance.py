"""Provenance ranks for TOPODATA fragments.

INPE publishes one static COG per tile and product, so the store carries a
single provenance variant.
"""

from __future__ import annotations


PUBLISHED = 0

LEGEND: dict[int, str] = {
    PUBLISHED: "published",
}


def legend_payload() -> dict[str, str]:
    """Return the manifest-ready provenance legend."""
    return {str(code): label for code, label in LEGEND.items()}
