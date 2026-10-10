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

    COCO-style annotation files are supported by reading categories[].name.
    """

    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(text)
        categories = data.get("categories", [])
        names = [item["name"] for item in categories if "name" in item]
        return tuple(_dedupe(names))
    if stripped.startswith("["):
        data = json.loads(text)
        if all(isinstance(item, str) for item in data):
            return tuple(_dedupe(data))
        names = [item["name"] for item in data if isinstance(item, dict) and "name" in item]
        return tuple(_dedupe(names))
    return tuple(_dedupe(line.strip() for line in text.splitlines() if line.strip()))


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
