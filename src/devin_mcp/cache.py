"""Private caching utilities for MCP tools."""

import json
import time
from pathlib import Path
from typing import Any

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600


def _get_cache_path() -> Path:
    """Get the cache file path."""
    cache_dir = Path.home() / ".cache" / "devin-mcp"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "tools.json"


def load_from_cache() -> list[dict[str, Any]] | None:
    """Load cached tools if available and not expired."""
    cache_path = _get_cache_path()

    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            cache_data = json.load(f)

        cached_at = cache_data.get("cached_at", 0)
        if time.time() - cached_at > CACHE_TTL:
            return None

        return cache_data.get("tools", [])
    except (json.JSONDecodeError, OSError):
        return None


def save_to_cache(tools: list[dict[str, Any]]) -> None:
    """Save tools to cache."""
    cache_path = _get_cache_path()

    cache_data = {
        "cached_at": time.time(),
        "tools": tools,
    }

    try:
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)
    except OSError:
        pass
