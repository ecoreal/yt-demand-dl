from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .models import VideoDemand

# AP-10K is documented by the project as 23 families and 54 species.
# The project objective asks for 53 classes, so CLI users can pass
# --category-limit 53 or provide a categories file exported from annotations.
AP10K_CATEGORIES: tuple[str, ...] = (
    "antelope",
    "argali sheep",
    "bison",
    "buffalo",
    "cow",
    "sheep",
    "dog",
    "fox",
    "wolf",
    "arctic fox",
    "beaver",
    "chimpanzee",
    "monkey",
    "squirrel monkey",
    "gibbon",
    "gorilla",
    "orangutan",
    "deer",
    "elk",
    "elephant",
    "horse",
    "zebra",
    "bobcat",
    "cat",
    "cheetah",
    "jaguar",
    "leopard",
    "lion",
    "panther",
    "snow leopard",
    "tiger",
    "giraffe",
    "hippopotamus",
    "macaque",
    "rabbit",
    "skunk",
    "mouse",
    "rat",
    "otter",
    "weasel",
    "badger",
    "rhinoceros",
    "marmot",
    "squirrel",
    "pig",
    "black bear",
    "brown bear",
    "panda",
    "polar bear",
    "hamster",
    "koala",
    "kangaroo",
    "raccoon",
    "killer whale",
)

AP10K_DEFAULT_COUNT = 53


def load_categories(path: Path) -> tuple[str, ...]:
    """Load categories from JSON, JSONL, or newline-separated text.

    COCO-style annotation files are supported by reading ``categories[].name``.
    Malformed structured input is rejected instead of silently producing an
    empty plan.
    """

    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON: {exc.msg}") from exc

        if isinstance(data, dict):
            categories = data.get("categories")
            if not isinstance(categories, list):
                raise ValueError(f"{path}: categories must be an array")
            names = _category_names(categories, path)
        elif isinstance(data, list):
            if all(isinstance(item, str) for item in data):
                names = [item.strip() for item in data]
            elif all(isinstance(item, dict) for item in data):
                names = _category_names(data, path)
            else:
                raise ValueError(f"{path}: JSON array must contain only strings or objects")
        else:
            raise ValueError(f"{path}: JSON root must be an object or array")

        result = tuple(_dedupe(names))
        if not result:
            raise ValueError(f"{path}: no non-empty categories found")
        return result

    result = tuple(_dedupe(line.strip() for line in text.splitlines() if line.strip()))
    if not result:
        raise ValueError(f"{path}: no non-empty categories found")
    return result


def _category_names(items: list[object], path: Path) -> list[str]:
    names: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: categories[{index}] must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: categories[{index}].name must be a non-empty string")
        names.append(name.strip())
    return names


def select_categories(
    categories: Iterable[str] = AP10K_CATEGORIES,
    *,
    limit: int | None = AP10K_DEFAULT_COUNT,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> tuple[str, ...]:
    selected = list(_dedupe(categories))
    if include:
        wanted = {item.lower() for item in include}
        selected = [item for item in selected if item.lower() in wanted]
    if exclude:
        blocked = {item.lower() for item in exclude}
        selected = [item for item in selected if item.lower() not in blocked]
    if limit is not None:
        selected = selected[:limit]
    return tuple(selected)


def make_ap10k_jobs(
    *,
    categories: Iterable[str] = AP10K_CATEGORIES,
    category_limit: int | None = AP10K_DEFAULT_COUNT,
    videos_per_category: int = 1,
    query_template: str = "{category} animal video",
    exclude: Iterable[str] | None = None,
) -> list[VideoDemand]:
    try:
        probe = query_template.format(category="__yt_demand_category__")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "query_template must be a valid format string using {category}"
        ) from exc
    if probe == query_template:
        raise ValueError("query_template must include the {category} field")
    selected = select_categories(categories, limit=category_limit, exclude=exclude)
    demands: list[VideoDemand] = []
    for category in selected:
        try:
            source = query_template.format(category=category)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "query_template must be a valid format string using {category}"
            ) from exc
        demands.append(
            VideoDemand(
                source=source,
                label=category,
                query=True,
                limit=videos_per_category,
                metadata={"dataset": "ap10k"},
            )
        )
    return demands


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value.strip())
    return result
