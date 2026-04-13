"""Resource loader for QA agent skills.

Uses `importlib.resources` so resources are addressable both in-tree and
when the package is installed as a wheel.
"""

from __future__ import annotations

from importlib.resources import files


def load_resource(name: str) -> str:
    """Load a skill resource file by filename (e.g. ``timeline_template.md``).

    Args:
        name: Basename of the resource file under
            ``beever_atlas.agents.query.skills.resources``.

    Returns:
        The UTF-8 decoded contents of the resource file.

    Raises:
        FileNotFoundError: If the resource does not exist.
    """
    resource = files("beever_atlas.agents.query.skills.resources").joinpath(name)
    return resource.read_text(encoding="utf-8")
