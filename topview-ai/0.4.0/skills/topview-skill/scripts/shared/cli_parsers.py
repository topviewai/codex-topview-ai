"""Cross-platform CLI parsers for structured TopView arguments."""

from __future__ import annotations

import json


def _is_json_like(value: str) -> bool:
    stripped = value.lstrip()
    return stripped.startswith("[") or stripped.startswith("{")


def parse_json_or_named_media_list(values: list[str] | str | None,
                                   default_prefix: str) -> list[dict]:
    """Parse media refs from legacy JSON or cross-platform CLI tokens.

    Legacy:
        '[{"fileId":"file_abc","name":"Image1"}]'

    Recommended:
        Image1=product.png
        Image1=file_abc
        product.png another.png
    """
    if not values:
        return []
    if isinstance(values, str):
        values = [values]

    if len(values) == 1 and _is_json_like(values[0]):
        parsed = json.loads(values[0])
        return parsed if isinstance(parsed, list) else [parsed]

    items = []
    auto_index = 1
    for token in values:
        if "=" in token:
            name, ref = token.split("=", 1)
            name = name.strip()
            ref = ref.strip()
            if not name or not ref:
                raise ValueError(f"Invalid media token '{token}'. Expected Name=path_or_fileId.")
        else:
            name = f"{default_prefix}{auto_index}"
            ref = token.strip()
            if not ref:
                raise ValueError("Empty media reference.")
        items.append({"name": name, "fileId": ref})
        auto_index += 1
    return items


def parse_json_or_kv_pairs(values: list[str] | str | None,
                           old_key: str = "oldStr",
                           new_key: str = "newStr") -> list[dict]:
    """Parse key-value rules from legacy JSON or cross-platform KEY=VALUE tokens."""
    if not values:
        return []
    if isinstance(values, str):
        values = [values]

    if len(values) == 1 and _is_json_like(values[0]):
        parsed = json.loads(values[0])
        return parsed if isinstance(parsed, list) else [parsed]

    pairs = []
    for token in values:
        if "=" not in token:
            raise ValueError(f"Invalid key-value token '{token}'. Expected old=new.")
        old, new = token.split("=", 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise ValueError(f"Invalid key-value token '{token}'. Expected old=new.")
        pairs.append({old_key: old, new_key: new})
    return pairs


def parse_point_pairs(location: str | None = None,
                      location_points: list[str] | None = None) -> list[list[float]] | None:
    """Parse product coordinates from legacy JSON or X,Y tokens."""
    if location:
        if _is_json_like(location):
            return json.loads(location)
        location_points = [location]

    if not location_points:
        return None

    points = []
    for token in location_points:
        parts = [p.strip() for p in token.split(",")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid point '{token}'. Expected x,y.")
        points.append([float(parts[0]), float(parts[1])])
    return points
