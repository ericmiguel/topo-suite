"""Project-root discovery."""

from __future__ import annotations

from pathlib import Path

from topo.exceptions import TopoError


class ProjectRootNotFoundError(TopoError):
    """Raised when no project marker is available."""


def resolve_project_root(root_dir: Path | None = None) -> Path:
    """Resolve an explicit root or the nearest project marker."""
    if root_dir is not None:
        root = Path(root_dir).expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise NotADirectoryError(root)
        return root
    start = Path.cwd().resolve()
    for marker in (".git", ".venv", "README.md"):
        for candidate in (start, *start.parents):
            if (candidate / marker).exists():
                return candidate
    raise ProjectRootNotFoundError("Pass root_dir because no project root was found.")
