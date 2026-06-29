#!/usr/bin/env python3
"""Build Spacerocks shop data from inventory folders.

Each listing lives in inventory/shop/<slug>/item.json. This script normalizes the
listing data, discovers item-folder images, enriches by exact Meteoritical
Bulletin name lookup when requested, and writes data/shop.json plus the MetBull
lookup cache. It intentionally uses only the Python standard library so it can
run in GitHub Actions without dependency setup.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_DIR = ROOT / "inventory" / "shop"
DATA_DIR = ROOT / "data"
SHOP_JSON = DATA_DIR / "shop.json"
METBULL_CACHE = DATA_DIR / "metbull-cache.json"

ALLOWED_STATUSES = {"available", "coming-soon", "hold", "sold"}
IMAGE_EXTENSIONS = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
METBULL_SEARCH_URL = "https://www.lpi.usra.edu/meteor/metbull.php"
METBULL_DETAIL_URL = "https://www.lpi.usra.edu/meteor/metbull.php?code={code}"
USER_AGENT = (
    "SpacerocksShopBuilder/1.0 "
    "(+https://github.com/rayborg/spacerocks; spacerocks.club@gmail.com)"
)
REQUEST_TIMEOUT_SECONDS = 12
FAILURE_RETRY_SECONDS = 24 * 60 * 60


class MetBullTableParser(HTMLParser):
    """Extract the first normal-result row from MetBull's search table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main_table = False
        self.table_depth = 0
        self.in_td = False
        self.current_cell: dict[str, Any] | None = None
        self.current_row: list[dict[str, Any]] = []
        self.rows: list[list[dict[str, Any]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "maintable":
            self.in_main_table = True
            self.table_depth = 1
            return

        if not self.in_main_table:
            return

        if tag == "table":
            self.table_depth += 1
        elif tag == "tr":
            self.current_row = []
        elif tag == "td":
            self.in_td = True
            self.current_cell = {"text": [], "links": []}
        elif tag == "a" and self.in_td and self.current_cell is not None:
            href = attrs_dict.get("href")
            if href:
                self.current_cell["links"].append(href)
        elif tag == "sup" and self.in_td and self.current_cell is not None:
            self.current_cell["text"].append("^")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_main_table:
            return

        if tag == "td" and self.in_td and self.current_cell is not None:
            text = normalize_space(" ".join(self.current_cell["text"]))
            self.current_cell["text"] = text
            self.current_row.append(self.current_cell)
            self.current_cell = None
            self.in_td = False
        elif tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth <= 0:
                self.in_main_table = False

    def handle_data(self, data: str) -> None:
        if self.in_td and self.current_cell is not None:
            self.current_cell["text"].append(data)


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_name(value: Any) -> str:
    return normalize_space(value).casefold()


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(fallback)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return default


def to_float(value: Any, field: str, slug: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            warn(f"{slug}: ignoring invalid {field!r}: {value!r}")
            return None
    warn(f"{slug}: ignoring invalid {field!r}: {value!r}")
    return None


def to_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [normalize_space(item) for item in value if normalize_space(item)]
    return []


def to_http_url(value: Any, field: str, slug: str) -> str | None:
    url = normalize_space(value)
    if not url:
        return None
    parsed = parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        warn(f"{slug}: ignoring invalid {field!r}: {value!r}")
        return None
    return url


def infer_taxonomy(classification: str) -> dict[str, str]:
    clean = normalize_space(classification)
    if not clean:
        return {
            "class": "Unclassified meteorite",
            "type": "Classification pending",
            "subtype": "Pending",
        }

    lower = clean.lower()
    token = re.split(r"[\s,(/]+", clean, maxsplit=1)[0].upper()

    chondrite_groups = [
        (r"^(CI|CM|CO|CV|CK|CR|CH|CB|CY|CL|C)(?=\d|$|[-/])", "Carbonaceous chondrite"),
        (r"^(LL|L|H)(?=\d|$|[-/])", "Ordinary chondrite"),
        (r"^(EH|EL)(?=\d|$|[-/])", "Enstatite chondrite"),
        (r"^R(?=\d|$|[-/])", "Rumuruti chondrite"),
        (r"^K(?=\d|$|[-/])", "Kakangari chondrite"),
    ]
    for pattern, meteorite_type in chondrite_groups:
        if re.match(pattern, token):
            return {"class": "Chondrite", "type": meteorite_type, "subtype": clean}

    if lower.startswith("iron") or re.match(r"^(IAB|IC|IIAB|IIC|IID|IIE|IIF|IIG|IIIAB|IIICD|IIIE|IIIF|IVA|IVB)\b", token):
        meteorite_type = clean.split(",", 1)[1].strip() if "," in clean else "Iron meteorite"
        return {"class": "Iron meteorite", "type": meteorite_type or "Iron meteorite", "subtype": clean}

    if "pallasite" in lower:
        return {"class": "Stony-iron meteorite", "type": "Pallasite", "subtype": clean}
    if "mesosiderite" in lower:
        return {"class": "Stony-iron meteorite", "type": "Mesosiderite", "subtype": clean}

    achondrite_types = [
        ("lunar", "Lunar meteorite"),
        ("martian", "Martian meteorite"),
        ("shergottite", "Martian meteorite"),
        ("nakhlite", "Martian meteorite"),
        ("chassignite", "Martian meteorite"),
        ("howardite", "HED achondrite"),
        ("eucrite", "HED achondrite"),
        ("diogenite", "HED achondrite"),
        ("aubrite", "Aubrite"),
        ("angrite", "Angrite"),
        ("ureilite", "Ureilite"),
        ("acapulcoite", "Acapulcoite"),
        ("lodranite", "Lodranite"),
        ("winonaite", "Winonaite"),
        ("brachinite", "Brachinite"),
    ]
    for keyword, meteorite_type in achondrite_types:
        if keyword in lower:
            return {"class": "Achondrite", "type": meteorite_type, "subtype": clean}

    if "chondrite" in lower:
        return {"class": "Chondrite", "type": "Chondrite", "subtype": clean}
    if "achondrite" in lower:
        return {"class": "Achondrite", "type": "Achondrite", "subtype": clean}

    return {"class": "Unclassified meteorite", "type": "Classification pending", "subtype": clean}


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_image_entry(entry: Any, fallback_alt: str) -> dict[str, Any] | None:
    if isinstance(entry, str):
        src = normalize_space(entry)
        if not src:
            return None
        return {"src": src, "alt": fallback_alt}
    if isinstance(entry, dict):
        src = normalize_space(entry.get("src") or entry.get("path") or entry.get("url"))
        if not src:
            return None
        normalized = {"src": src, "alt": normalize_space(entry.get("alt")) or fallback_alt}
        caption = normalize_space(entry.get("caption"))
        if caption:
            normalized["caption"] = caption
        return normalized
    return None


def collect_images(item_dir: Path, item: dict[str, Any], title: str) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in item.get("images") or []:
        normalized = normalize_image_entry(entry, title)
        if normalized and normalized["src"] not in seen:
            images.append(normalized)
            seen.add(normalized["src"])

    folder_images = [
        path
        for path in item_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    order = [normalize_space(value) for value in item.get("image_order") or [] if normalize_space(value)]
    order_lookup = {value: index for index, value in enumerate(order)}

    def image_sort_key(path: Path) -> tuple[int, str]:
        src = relative_path(path)
        return (order_lookup.get(path.name, order_lookup.get(src, len(order_lookup))), path.name.lower())

    for path in sorted(folder_images, key=image_sort_key):
        src = relative_path(path)
        if src in seen:
            continue
        images.append({"src": src, "alt": title})
        seen.add(src)

    if order:
        order_lookup = {value: index for index, value in enumerate(order)}

        def combined_sort_key(image: dict[str, Any]) -> tuple[int, str]:
            src = image["src"]
            filename = Path(src).name
            return (order_lookup.get(src, order_lookup.get(filename, len(order_lookup))), src.lower())

        images = sorted(images, key=combined_sort_key)

    return images


def build_metbull_search_url(name: str) -> str:
    params = {
        "sea": name,
        "sfor": "names",
        "ants": "",
        "nwas": "",
        "falls": "",
        "valids": "",
        "stype": "exact",
        "lrec": "50",
        "map": "ge",
        "browse": "",
        "country": "All",
        "srt": "name",
        "categ": "All",
        "mblist": "All",
        "rect": "",
        "phot": "",
        "strewn": "",
        "snew": "0",
        "pnt": "Normal table",
        "dr": "",
        "page": "0",
    }
    return f"{METBULL_SEARCH_URL}?{parse.urlencode(params)}"


def fetch_url(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_code(links: list[str]) -> str | None:
    for href in links:
        parsed = parse.urlparse(html.unescape(href))
        query = parse.parse_qs(parsed.query)
        if "code" in query and query["code"]:
            return query["code"][0]
    return None


def extract_first_url(links: list[str]) -> str | None:
    for href in links:
        unescaped = html.unescape(href)
        if unescaped.startswith("http://") or unescaped.startswith("https://"):
            return unescaped
    return None


def normalize_fall_marker(marker: str) -> dict[str, str | None]:
    clean = normalize_space(marker).replace(" ", "")
    if not clean:
        return {"fall_find": None, "fall_find_marker": None}
    if clean.upper().startswith("Y"):
        label = "Confirmed fall" if "^c" in clean.lower() or "c" in clean.lower() else "Fall"
    elif clean.upper().startswith("N"):
        label = "Find"
    else:
        label = clean
    return {"fall_find": label, "fall_find_marker": clean}


def parse_metbull_record(name: str, body: str, source_url: str) -> dict[str, Any] | None:
    parser = MetBullTableParser()
    parser.feed(body)
    for row in parser.rows:
        if len(row) < 8:
            continue
        official_name = row[0]["text"].replace("**", "").strip()
        if normalize_name(official_name) != normalize_name(name):
            continue

        code = extract_code(row[0].get("links", []))
        fall_data = normalize_fall_marker(row[2]["text"])
        record = {
            "official_name": official_name,
            "status": row[1]["text"] or None,
            "fall_find": fall_data["fall_find"],
            "fall_find_marker": fall_data["fall_find_marker"],
            "year": row[3]["text"] or None,
            "place": row[4]["text"] or None,
            "classification": row[5]["text"] or None,
            "total_known_mass": row[6]["text"] or None,
            "bulletin": row[7]["text"] or None,
            "bulletin_url": extract_first_url(row[7].get("links", [])),
            "source_url": METBULL_DETAIL_URL.format(code=code) if code else source_url,
            "code": code,
        }
        return {key: value for key, value in record.items() if value not in {None, ""}}
    return None


def cache_entry_is_recent_failure(entry: dict[str, Any], now: dt.datetime) -> bool:
    if entry.get("status") != "error":
        return False
    cached_at = entry.get("cached_at")
    if not cached_at:
        return False
    try:
        cached = dt.datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (now - cached).total_seconds() < FAILURE_RETRY_SECONDS


def lookup_metbull(name: str, cache: dict[str, Any]) -> dict[str, Any]:
    lookups = cache.setdefault("lookups", {})
    cached = lookups.get(name)
    now = dt.datetime.now(dt.UTC)
    if isinstance(cached, dict) and cached.get("status") in {"ok", "not_found"}:
        return cached
    if isinstance(cached, dict) and cache_entry_is_recent_failure(cached, now):
        return cached

    source_url = build_metbull_search_url(name)
    try:
        body = fetch_url(source_url)
        record = parse_metbull_record(name, body, source_url)
        if record:
            entry = {
                "cached_at": now_utc(),
                "query": name,
                "source": "Meteoritical Bulletin Database",
                "status": "ok",
                "record": record,
            }
        else:
            entry = {
                "cached_at": now_utc(),
                "query": name,
                "source": "Meteoritical Bulletin Database",
                "status": "not_found",
                "source_url": source_url,
            }
    except (error.URLError, TimeoutError, OSError) as exc:
        entry = {
            "cached_at": now_utc(),
            "query": name,
            "source": "Meteoritical Bulletin Database",
            "status": "error",
            "error": str(exc),
            "source_url": source_url,
        }

    lookups[name] = entry
    time.sleep(0.5)
    return entry


def normalize_item(item_dir: Path, cache: dict[str, Any]) -> dict[str, Any]:
    slug = item_dir.name
    raw = read_json(item_dir / "item.json", {})
    if not isinstance(raw, dict):
        raise ValueError(f"{item_dir / 'item.json'} must contain a JSON object")

    title = normalize_space(raw.get("title")) or normalize_space(raw.get("name")) or title_from_slug(slug)
    meteorite_name = normalize_space(raw.get("name"))
    status = normalize_space(raw.get("status") or "available").lower().replace("_", "-")
    if status == "coming soon":
        status = "coming-soon"
    if status not in ALLOWED_STATUSES:
        warn(f"{slug}: unknown status {status!r}; using 'available'")
        status = "available"

    metbull_enabled = to_bool(raw.get("metbull_lookup"), default=bool(meteorite_name))
    metbull_entry: dict[str, Any] | None = None
    if metbull_enabled and meteorite_name:
        metbull_entry = lookup_metbull(meteorite_name, cache)

    metbull_record = metbull_entry.get("record", {}) if isinstance(metbull_entry, dict) else {}
    metbull_classification = normalize_space(metbull_record.get("classification"))
    local_classification = normalize_space(raw.get("classification"))
    classification = metbull_classification or local_classification
    taxonomy = infer_taxonomy(classification)
    taxonomy["source"] = "Meteoritical Bulletin Database" if metbull_classification else "Listing classification"
    taxonomy["classification"] = classification or "Pending"
    item_type = normalize_space(raw.get("type")) or classification

    normalized = {
        "slug": slug,
        "title": title,
        "name": meteorite_name or None,
        "weight_g": to_float(raw.get("weight_g"), "weight_g", slug),
        "price_usd": to_float(raw.get("price_usd"), "price_usd", slug),
        "status": status,
        "description": normalize_space(raw.get("description")),
        "type": item_type or None,
        "classification": classification or None,
        "taxonomy": taxonomy,
        "provenance": normalize_space(raw.get("provenance")),
        "badges": to_string_list(raw.get("badges")),
        "checkout_url": to_http_url(raw.get("checkout_url"), "checkout_url", slug),
        "checkout_label": normalize_space(raw.get("checkout_label")),
        "images": collect_images(item_dir, raw, title),
        "featured": to_bool(raw.get("featured"), default=False),
        "metbull_lookup": {
            "enabled": bool(metbull_enabled and meteorite_name),
            "status": metbull_entry.get("status") if isinstance(metbull_entry, dict) else "skipped",
            "cached_at": metbull_entry.get("cached_at") if isinstance(metbull_entry, dict) else None,
        },
    }

    if metbull_record:
        normalized["metbull"] = metbull_record

    return {key: value for key, value in normalized.items() if not is_empty_value(value)}


def display_meteorite_name(item: dict[str, Any]) -> str:
    metbull = item.get("metbull", {})
    return normalize_space(metbull.get("official_name")) or normalize_space(item.get("name")) or normalize_space(item.get("title"))


def build_taxonomy_index(items: list[dict[str, Any]]) -> dict[str, Any]:
    class_map: dict[str, Any] = {}
    metbull_items = 0

    for item in items:
        taxonomy = item.get("taxonomy", {})
        class_name = normalize_space(taxonomy.get("class")) or "Unclassified meteorite"
        type_name = normalize_space(taxonomy.get("type")) or "Classification pending"
        subtype_name = normalize_space(taxonomy.get("subtype")) or normalize_space(item.get("classification")) or "Pending"
        meteorite_name = display_meteorite_name(item) or "Unnamed meteorite"
        metbull = item.get("metbull", {})
        source_url = normalize_space(metbull.get("source_url"))

        if taxonomy.get("source") == "Meteoritical Bulletin Database":
            metbull_items += 1

        class_entry = class_map.setdefault(class_name, {"name": class_name, "count": 0, "types": {}})
        type_entry = class_entry["types"].setdefault(type_name, {"name": type_name, "count": 0, "subtypes": {}})
        subtype_entry = type_entry["subtypes"].setdefault(
            subtype_name,
            {"name": subtype_name, "count": 0, "names": {}},
        )
        name_entry = subtype_entry["names"].setdefault(
            meteorite_name,
            {"name": meteorite_name, "count": 0, "source_url": source_url, "listings": []},
        )

        class_entry["count"] += 1
        type_entry["count"] += 1
        subtype_entry["count"] += 1
        name_entry["count"] += 1
        if source_url and not name_entry.get("source_url"):
            name_entry["source_url"] = source_url
        name_entry["listings"].append(
            {
                "slug": item.get("slug"),
                "title": item.get("title"),
                "status": item.get("status"),
            }
        )

    def sort_key(entry: dict[str, Any]) -> tuple[bool, str]:
        return (entry["name"].startswith(("Unclassified", "Classification pending", "Pending")), entry["name"].casefold())

    classes = []
    for class_entry in sorted(class_map.values(), key=sort_key):
        types = []
        for type_entry in sorted(class_entry["types"].values(), key=sort_key):
            subtypes = []
            for subtype_entry in sorted(type_entry["subtypes"].values(), key=sort_key):
                names = sorted(subtype_entry["names"].values(), key=lambda entry: entry["name"].casefold())
                for name_entry in names:
                    name_entry["listings"] = sorted(
                        name_entry["listings"],
                        key=lambda listing: normalize_space(listing.get("title")).casefold(),
                    )
                subtypes.append(
                    {
                        "name": subtype_entry["name"],
                        "count": subtype_entry["count"],
                        "names": names,
                    }
                )
            types.append({"name": type_entry["name"], "count": type_entry["count"], "subtypes": subtypes})
        classes.append({"name": class_entry["name"], "count": class_entry["count"], "types": types})

    return {
        "source": "Meteoritical Bulletin Database exact-name classifications; listing classification is used only when the database is unavailable.",
        "item_count": len(items),
        "metbull_item_count": metbull_items,
        "classes": classes,
    }


def summarize_lookup_status(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"enabled": 0, "ok": 0, "not_found": 0, "error": 0, "skipped": 0}
    for item in items:
        lookup = item.get("metbull_lookup", {})
        status = lookup.get("status", "skipped")
        if lookup.get("enabled"):
            summary["enabled"] += 1
        if status not in summary:
            summary[status] = 0
        summary[status] += 1
    return summary


def payload_without_generated_at(data: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(data)
    clone.pop("generated_at", None)
    return clone


def build_shop_data(cache: dict[str, Any]) -> dict[str, Any]:
    if not INVENTORY_DIR.exists():
        items: list[dict[str, Any]] = []
    else:
        item_dirs = sorted(path for path in INVENTORY_DIR.iterdir() if (path / "item.json").is_file())
        items = [normalize_item(item_dir, cache) for item_dir in item_dirs]

    items.sort(key=lambda item: (not item.get("featured", False), item.get("title", "").casefold()))
    return {
        "generated_at": now_utc(),
        "taxonomy": build_taxonomy_index(items),
        "lookup_status": summarize_lookup_status(items),
        "items": items,
    }


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = read_json(METBULL_CACHE, {"lookups": {}})
    if not isinstance(cache, dict):
        cache = {"lookups": {}}
    cache.setdefault("lookups", {})

    shop_data = build_shop_data(cache)
    previous_shop_data = read_json(SHOP_JSON, None)
    if isinstance(previous_shop_data, dict) and payload_without_generated_at(previous_shop_data) == payload_without_generated_at(shop_data):
        shop_data["generated_at"] = previous_shop_data.get("generated_at", shop_data["generated_at"])

    write_json(SHOP_JSON, shop_data)
    cache.pop("generated_at", None)
    write_json(METBULL_CACHE, cache)
    print(f"Built {SHOP_JSON.relative_to(ROOT)} with {len(shop_data['items'])} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
