#!/usr/bin/env python3
"""Met à jour les données statiques de la carte des feux.

- Feux actifs : NASA FIRMS, trois instruments VIIRS NRT, 7 jours.
- Validation : masque VIIRS filtré d'EFFIS, corroboration multi-satellite,
  regroupement spatial et temporel, puis filtre des sources thermiques fixes.
- Surfaces brûlées : périmètres vectoriels EFFIS MODIS, 30 jours.

Les visiteurs ne contactent jamais NASA ou EFFIS : les données préparées sont
publiées sous forme de fichiers GeoJSON statiques par GitHub Pages.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
import shapefile
from PIL import Image
from requests.adapters import HTTPAdapter
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
FIRES_PATH = DATA_DIR / "fires.geojson"
BURNED_PATH = DATA_DIR / "burned.geojson"
LEGACY_BURNED_PATH = DATA_DIR / "burned.png"
MANIFEST_PATH = DATA_DIR / "manifest.json"
THERMAL_HISTORY_PATH = DATA_DIR / "thermal-history.json"
INDUSTRIAL_THERMAL_PATH = DATA_DIR / "industrial-thermal.geojson"
UNCONFIRMED_THERMAL_PATH = DATA_DIR / "unconfirmed-thermal.geojson"

EUROPE_BBOX = (-25.0, 34.0, 42.0, 72.0)  # ouest, sud, est, nord
EUROPE_CLIP = box(*EUROPE_BBOX)
FIRMS_SOURCES: tuple[dict[str, str], ...] = (
    {"id": "VIIRS_NOAA20_NRT", "label": "NOAA-20", "role": "primary"},
    {"id": "VIIRS_NOAA21_NRT", "label": "NOAA-21", "role": "primary"},
    # Suomi-NPP reste une source de corroboration. Une détection issue de ce
    # satellite seul n'est pas retenue sans confirmation EFFIS ou périmètre brûlé.
    {"id": "VIIRS_SNPP_NRT", "label": "Suomi-NPP", "role": "supporting"},
)
PRIMARY_SOURCE_IDS = {source["id"] for source in FIRMS_SOURCES if source["role"] == "primary"}
FIRMS_PERIOD_DAYS = 7

EFFIS_WFS_URL = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_WMS_URL = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_TYPENAME = "ms:modis.ba.poly"
EFFIS_ACTIVE_FIRE_LAYER = "viirs.hs"
MAX_EFFIS_DOWNLOAD_BYTES = 250 * 1024 * 1024

# Le masque EFFIS est téléchargé en quatre images. Cette résolution est assez
# fine pour vérifier la proximité d'un symbole de hotspot sans charger une
# image européenne gigantesque.
EFFIS_MASK_COLS = 2
EFFIS_MASK_ROWS = 2
EFFIS_MASK_WIDTH = 1600
EFFIS_MASK_HEIGHT = 1100
EFFIS_MASK_SAMPLE_RADIUS_PX = 2

# Regroupement des observations satellitaires en événements probables.
CLUSTER_RADIUS_KM = 1.25
CLUSTER_MAX_TIME_GAP_HOURS = 42
CLUSTER_GRID_DEGREES = 0.02

# Grille proche de la résolution VIIRS (375 m). Une cellule n'est classée comme
# source thermique récurrente qu'après observation pendant au moins huit jours
# distincts sur une fenêtre de trente jours.
THERMAL_CELL_DEGREES = 0.004
THERMAL_HISTORY_DAYS = 30
RECURRENT_MIN_DISTINCT_DAYS = 8
BURNED_PROTECTION_BUFFER_DEGREES = 0.006

# Masque initial volontairement limité aux installations déjà identifiées.
STATIC_THERMAL_SITES: tuple[dict[str, Any], ...] = (
    {"name": "ArcelorMittal Dunkerque", "longitude": 2.283794, "latitude": 51.032392, "radius_km": 1.15},
    {"name": "Terminal méthanier de Dunkerque", "longitude": 2.19653, "latitude": 51.03361, "radius_km": 1.0},
    {"name": "ArcelorMittal Fos-sur-Mer", "longitude": 4.88983, "latitude": 43.4368, "radius_km": 1.15},
    {"name": "Terminal méthanier de Fos-Cavaou", "longitude": 4.90051, "latitude": 43.41928, "radius_km": 1.0},
    {"name": "Raffinerie de Fos", "longitude": 4.92592, "latitude": 43.44551, "radius_km": 1.1},
    {"name": "Incinérateur de Fos-sur-Mer", "longitude": 4.85471, "latitude": 43.41805, "radius_km": 0.9},
)


def log(message: str) -> None:
    print(message, flush=True)


def build_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "tle-carte-feux/3.0 (+https://github.com/valldrttle/tle-carte-feux)"
    })
    return session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 3}
    try:
        result = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        result["version"] = 3
        return result
    except (OSError, json.JSONDecodeError):
        return {"version": 3}


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def parse_detection_datetime(row: dict[str, str]) -> datetime | None:
    raw_date = (row.get("acq_date") or "").strip()
    raw_time = (row.get("acq_time") or "").strip().zfill(4)
    try:
        detected_date = date.fromisoformat(raw_date)
        detected_time = time(int(raw_time[:2]), int(raw_time[2:4]), tzinfo=timezone.utc)
        return datetime.combine(detected_date, detected_time)
    except (ValueError, TypeError):
        return None


def recency_class(age_hours: float) -> int:
    if age_hours <= 24:
        return 0
    if age_hours <= 72:
        return 1
    if age_hours <= 120:
        return 2
    return 3


def firms_url(map_key: str, source: str, day_range: int, start_date: date | None = None) -> str:
    west, south, east, north = EUROPE_BBOX
    area = f"{west},{south},{east},{north}"
    base = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{map_key}/{source}/{area}/{day_range}"
    )
    return f"{base}/{start_date.isoformat()}" if start_date else base


def download_csv(session: requests.Session, url: str) -> list[dict[str, str]]:
    response = session.get(url, timeout=(20, 180))
    response.raise_for_status()
    text = response.text.lstrip("\ufeff").strip()
    if not text:
        return []
    if text.startswith("Invalid") or ("MAP_KEY" in text[:250] and "," not in text[:250]):
        raise RuntimeError(f"Réponse FIRMS invalide: {text[:250]}")
    return list(csv.DictReader(io.StringIO(text)))


def download_firms_source(
    session: requests.Session,
    map_key: str,
    source_id: str,
    today: date,
) -> list[dict[str, str]]:
    recent_rows = download_csv(session, firms_url(map_key, source_id, 5))
    older_start = today - timedelta(days=FIRMS_PERIOD_DAYS - 1)
    older_rows = download_csv(session, firms_url(map_key, source_id, 2, older_start))
    return older_rows + recent_rows


def haversine_km(longitude_a: float, latitude_a: float, longitude_b: float, latitude_b: float) -> float:
    radius_km = 6371.0088
    phi_a = math.radians(latitude_a)
    phi_b = math.radians(latitude_b)
    delta_phi = math.radians(latitude_b - latitude_a)
    delta_lambda = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(value)))


def thermal_cell_key(longitude: float, latitude: float) -> str:
    longitude_index = math.floor(longitude / THERMAL_CELL_DEGREES)
    latitude_index = math.floor(latitude / THERMAL_CELL_DEGREES)
    return f"{longitude_index}:{latitude_index}"


def thermal_cell_center(cell_key: str) -> tuple[float, float]:
    longitude_index, latitude_index = (int(value) for value in cell_key.split(":", 1))
    longitude = (longitude_index + 0.5) * THERMAL_CELL_DEGREES
    latitude = (latitude_index + 0.5) * THERMAL_CELL_DEGREES
    return longitude, latitude


def load_thermal_history(today: date) -> dict[str, set[str]]:
    cutoff = today - timedelta(days=THERMAL_HISTORY_DAYS - 1)
    history: dict[str, set[str]] = {}
    try:
        raw = json.loads(THERMAL_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return history

    for cell_key, values in (raw.get("cells") or {}).items():
        dates: set[str] = set()
        for raw_date in values.get("dates", []):
            try:
                parsed = date.fromisoformat(str(raw_date))
            except ValueError:
                continue
            if cutoff <= parsed <= today:
                dates.add(parsed.isoformat())
        if dates:
            history[str(cell_key)] = dates
    return history


def save_thermal_history(history: dict[str, set[str]], now: datetime) -> None:
    cells: dict[str, dict[str, Any]] = {}
    for cell_key, dates in sorted(history.items()):
        if len(dates) < 2:
            continue
        longitude, latitude = thermal_cell_center(cell_key)
        ordered_dates = sorted(dates)
        cells[cell_key] = {
            "longitude": round(longitude, 5),
            "latitude": round(latitude, 5),
            "dates": ordered_dates,
            "distinct_days": len(ordered_dates),
            "last_seen": ordered_dates[-1],
        }
    payload = {
        "version": 1,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "window_days": THERMAL_HISTORY_DAYS,
        "cell_degrees": THERMAL_CELL_DEGREES,
        "cells": cells,
    }
    atomic_write(
        THERMAL_HISTORY_PATH,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
    )


def load_burned_protection_geometry() -> Any | None:
    try:
        collection = json.loads(BURNED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return None

    geometries = []
    for feature in collection.get("features", []):
        geometry_json = feature.get("geometry")
        if not geometry_json:
            continue
        try:
            geometry = shape(geometry_json)
            if not geometry.is_empty:
                geometries.append(geometry)
        except Exception:
            continue
    if not geometries:
        return None
    try:
        return unary_union(geometries).buffer(BURNED_PROTECTION_BUFFER_DEGREES)
    except Exception:
        return None


def point_is_near_burned(longitude: float, latitude: float, burned_protection: Any | None) -> bool:
    if burned_protection is None:
        return False
    try:
        return bool(burned_protection.covers(Point(longitude, latitude)))
    except Exception:
        return False


def known_thermal_site(longitude: float, latitude: float) -> dict[str, Any] | None:
    for site in STATIC_THERMAL_SITES:
        distance = haversine_km(
            longitude,
            latitude,
            float(site["longitude"]),
            float(site["latitude"]),
        )
        if distance <= float(site["radius_km"]):
            return site
    return None


def probable_industrial_reason(
    longitude: float,
    latitude: float,
    cell_key: str,
    history: dict[str, set[str]],
    burned_protection: Any | None,
) -> tuple[str, str | None] | None:
    if point_is_near_burned(longitude, latitude, burned_protection):
        return None

    site = known_thermal_site(longitude, latitude)
    if site is not None:
        return "site_industriel_connu", str(site["name"])

    if len(history.get(cell_key, set())) >= RECURRENT_MIN_DISTINCT_DAYS:
        return "anomalie_thermique_recurrente", None
    return None


def split_bbox(
    bbox: tuple[float, float, float, float],
    cols: int,
    rows: int,
) -> list[tuple[float, float, float, float]]:
    west, south, east, north = bbox
    lon_step = (east - west) / cols
    lat_step = (north - south) / rows
    result = []
    for row_index in range(rows):
        tile_south = south + row_index * lat_step
        tile_north = south + (row_index + 1) * lat_step
        for col_index in range(cols):
            tile_west = west + col_index * lon_step
            tile_east = west + (col_index + 1) * lon_step
            result.append((tile_west, tile_south, tile_east, tile_north))
    return result


def pixel_is_hot(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    if alpha < 20:
        return False
    # Certaines configurations WMS renvoient un fond blanc malgré TRANSPARENT.
    if red > 245 and green > 245 and blue > 245:
        return False
    if max(red, green, blue) - min(red, green, blue) < 8 and red > 220:
        return False
    return True


def download_effis_active_mask(
    session: requests.Session,
    start_day: date,
    end_day: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    time_candidates = (
        f"{start_day.isoformat()}/{end_day.isoformat()}",
        f"{start_day.isoformat()},{end_day.isoformat()}",
    )

    for time_value in time_candidates:
        tiles: list[dict[str, Any]] = []
        signal_pixels = 0
        try:
            for tile_bbox in split_bbox(EUROPE_BBOX, EFFIS_MASK_COLS, EFFIS_MASK_ROWS):
                params = {
                    "SERVICE": "WMS",
                    "VERSION": "1.1.1",
                    "REQUEST": "GetMap",
                    "LAYERS": EFFIS_ACTIVE_FIRE_LAYER,
                    "STYLES": "",
                    "FORMAT": "image/png",
                    "TRANSPARENT": "true",
                    "SRS": "EPSG:4326",
                    "BBOX": ",".join(str(value) for value in tile_bbox),
                    "WIDTH": str(EFFIS_MASK_WIDTH),
                    "HEIGHT": str(EFFIS_MASK_HEIGHT),
                    "TIME": time_value,
                }
                response = session.get(EFFIS_WMS_URL, params=params, timeout=(30, 240))
                response.raise_for_status()
                try:
                    image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                    image.load()
                except Exception as exc:
                    sample = response.content[:350].decode("utf-8", errors="replace")
                    raise RuntimeError(f"réponse WMS EFFIS non lisible: {sample}") from exc

                if image.size != (EFFIS_MASK_WIDTH, EFFIS_MASK_HEIGHT):
                    image = image.resize((EFFIS_MASK_WIDTH, EFFIS_MASK_HEIGHT))
                pixels = image.load()
                tile_signal = 0
                # Échantillonnage d'une ligne sur deux pour valider que le masque
                # n'est pas entièrement vide, sans parcourir tous les pixels.
                for y in range(0, image.height, 2):
                    for x in range(0, image.width, 2):
                        if pixel_is_hot(pixels[x, y]):
                            tile_signal += 1
                signal_pixels += tile_signal
                tiles.append({"bbox": tile_bbox, "image": image, "signal_pixels": tile_signal})

            if signal_pixels == 0:
                raise RuntimeError("le masque VIIRS EFFIS est entièrement vide")

            return tiles, {
                "available": True,
                "layer": EFFIS_ACTIVE_FIRE_LAYER,
                "period_start": start_day.isoformat(),
                "period_end": end_day.isoformat(),
                "time_parameter": time_value,
                "tile_count": len(tiles),
                "sampled_signal_pixels": signal_pixels,
            }
        except Exception as exc:
            errors.append(f"TIME={time_value}: {exc}")

    raise RuntimeError("; ".join(errors))


def effis_mask_matches(longitude: float, latitude: float, tiles: list[dict[str, Any]]) -> bool:
    for tile in tiles:
        west, south, east, north = tile["bbox"]
        if not (west <= longitude <= east and south <= latitude <= north):
            continue
        image: Image.Image = tile["image"]
        x = int(round((longitude - west) / (east - west) * (image.width - 1)))
        y = int(round((north - latitude) / (north - south) * (image.height - 1)))
        pixels = image.load()
        radius = EFFIS_MASK_SAMPLE_RADIUS_PX
        for sample_y in range(max(0, y - radius), min(image.height, y + radius + 1)):
            for sample_x in range(max(0, x - radius), min(image.width, x + radius + 1)):
                if pixel_is_hot(pixels[sample_x, sample_y]):
                    return True
        return False
    return False


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, first: int, second: int) -> None:
        root_a = self.find(first)
        root_b = self.find(second)
        if root_a == root_b:
            return
        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a
        self.parent[root_b] = root_a
        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1


def cluster_candidates(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not candidates:
        return []
    disjoint = DisjointSet(len(candidates))
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)

    for index, candidate in enumerate(candidates):
        grid_x = math.floor(candidate["longitude"] / CLUSTER_GRID_DEGREES)
        grid_y = math.floor(candidate["latitude"] / CLUSTER_GRID_DEGREES)
        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                for other_index in grid.get((grid_x + offset_x, grid_y + offset_y), []):
                    other = candidates[other_index]
                    time_gap = abs(
                        (candidate["detected_at"] - other["detected_at"]).total_seconds()
                    ) / 3600
                    if time_gap > CLUSTER_MAX_TIME_GAP_HOURS:
                        continue
                    if haversine_km(
                        candidate["longitude"],
                        candidate["latitude"],
                        other["longitude"],
                        other["latitude"],
                    ) <= CLUSTER_RADIUS_KM:
                        disjoint.union(index, other_index)
        grid[(grid_x, grid_y)].append(index)

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        grouped[disjoint.find(index)].append(candidate)
    return list(grouped.values())


def cluster_summary(members: list[dict[str, Any]]) -> dict[str, Any]:
    latest = min(members, key=lambda item: item["age_hours"])
    sources = sorted({member["source_id"] for member in members})
    source_labels = sorted({member["source_label"] for member in members})
    primary_sources = sorted(set(sources) & PRIMARY_SOURCE_IDS)
    passes = {
        (member["source_id"], member["detected_at"].strftime("%Y-%m-%dT%H:%M"))
        for member in members
    }
    high_count = sum(1 for member in members if member["confidence"] == "high")
    effis_confirmed = any(member.get("effis_confirmed", False) for member in members)
    burned_confirmed = any(member.get("burned_confirmed", False) for member in members)
    max_frp = max((member["frp"] for member in members), default=0.0)

    score = 0
    if effis_confirmed:
        score += 5
    if burned_confirmed:
        score += 5
    if len(primary_sources) >= 2:
        score += 4
    elif len(primary_sources) >= 1 and len(sources) >= 2:
        score += 3
    if len(passes) >= 2:
        score += 2
    if len(members) >= 3:
        score += 2
    if high_count:
        score += 1
    if max_frp >= 10:
        score += 1

    accepted = bool(
        effis_confirmed
        or burned_confirmed
        or len(primary_sources) >= 2
        or (len(primary_sources) >= 1 and len(sources) >= 2 and len(passes) >= 2)
        or (high_count > 0 and len(passes) >= 2 and len(members) >= 2)
        or (high_count > 0 and len(members) >= 3)
    )

    evidence: list[str] = []
    if effis_confirmed:
        evidence.append("EFFIS")
    if burned_confirmed:
        evidence.append("périmètre brûlé")
    if len(primary_sources) >= 2:
        evidence.append("NOAA-20 + NOAA-21")
    elif len(sources) >= 2:
        evidence.append("multi-VIIRS")
    if len(passes) >= 2:
        evidence.append("passages répétés")
    if len(members) >= 3:
        evidence.append("groupe spatial")
    if high_count:
        evidence.append("confiance élevée")

    return {
        "accepted": accepted,
        "representative": latest,
        "observations": len(members),
        "passes": len(passes),
        "sources": sources,
        "source_labels": source_labels,
        "primary_sources": primary_sources,
        "high_count": high_count,
        "effis_confirmed": effis_confirmed,
        "burned_confirmed": burned_confirmed,
        "max_frp": round(max_frp, 1),
        "score": score,
        "evidence": evidence,
    }


def cluster_feature(summary: dict[str, Any], rejected: bool = False) -> dict[str, Any]:
    candidate = summary["representative"]
    properties = {
        "age_h": round(candidate["age_hours"], 1),
        "recency": recency_class(candidate["age_hours"]),
        "frp": summary["max_frp"],
        "confidence": "high" if summary["high_count"] else "nominal",
        "observations": summary["observations"],
        "passes": summary["passes"],
        "sensor_count": len(summary["sources"]),
        "sensors": ", ".join(summary["source_labels"]),
        "effis_confirmed": summary["effis_confirmed"],
        "burned_confirmed": summary["burned_confirmed"],
        "evidence_score": summary["score"],
        "evidence": ", ".join(summary["evidence"]),
    }
    if rejected:
        properties["filter_reason"] = "anomalie_non_corroboree"
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [candidate["longitude"], candidate["latitude"]],
        },
        "properties": properties,
    }


def update_active_fires(session: requests.Session, manifest: dict[str, Any]) -> bool:
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise RuntimeError("Le secret GitHub FIRMS_MAP_KEY n'est pas défini.")

    now = utc_now()
    today = now.date()
    oldest_allowed = now - timedelta(days=FIRMS_PERIOD_DAYS, hours=3)
    source_rows: dict[str, list[dict[str, str]]] = {}
    source_errors: dict[str, str] = {}

    for source in FIRMS_SOURCES:
        try:
            rows = download_firms_source(session, map_key, source["id"], today)
            source_rows[source["id"]] = rows
            log(f"FIRMS {source['label']}: {len(rows)} lignes téléchargées.")
        except Exception as exc:
            source_errors[source["id"]] = str(exc)
            log(f"AVERTISSEMENT - FIRMS {source['label']}: {exc}")

    if not any(source_id in source_rows for source_id in PRIMARY_SOURCE_IDS):
        raise RuntimeError("aucune source VIIRS NOAA principale n'est disponible")

    source_by_id = {source["id"]: source for source in FIRMS_SOURCES}
    seen: set[tuple[str, str, str, str, str]] = set()
    candidates: list[dict[str, Any]] = []
    excluded_low_confidence = 0
    excluded_non_vegetation = 0
    history = load_thermal_history(today)
    cutoff = today - timedelta(days=THERMAL_HISTORY_DAYS - 1)

    for source_id, rows in source_rows.items():
        source = source_by_id[source_id]
        for row in rows:
            confidence_raw = (row.get("confidence") or "").strip().lower()
            if confidence_raw in {"l", "low"}:
                excluded_low_confidence += 1
                continue

            hotspot_type = (row.get("type") or "").strip()
            if hotspot_type and hotspot_type not in {"0", "0.0"}:
                excluded_non_vegetation += 1
                continue

            detected_at = parse_detection_datetime(row)
            if not detected_at or detected_at < oldest_allowed or detected_at > now + timedelta(hours=2):
                continue

            try:
                latitude = round(float(row["latitude"]), 5)
                longitude = round(float(row["longitude"]), 5)
            except (KeyError, TypeError, ValueError):
                continue

            key = (
                source_id,
                str(latitude),
                str(longitude),
                row.get("acq_date", ""),
                row.get("acq_time", ""),
            )
            if key in seen:
                continue
            seen.add(key)

            age_hours = max(0.0, (now - detected_at).total_seconds() / 3600)
            try:
                frp = round(float(row.get("frp") or 0), 1)
            except ValueError:
                frp = 0.0

            cell_key = thermal_cell_key(longitude, latitude)
            history.setdefault(cell_key, set()).add(detected_at.date().isoformat())
            candidates.append({
                "longitude": longitude,
                "latitude": latitude,
                "detected_at": detected_at,
                "age_hours": age_hours,
                "frp": frp,
                "confidence": "high" if confidence_raw in {"h", "high"} else "nominal",
                "cell_key": cell_key,
                "source_id": source_id,
                "source_label": source["label"],
            })

    for cell_key in list(history):
        retained_dates = {
            raw_date
            for raw_date in history[cell_key]
            if cutoff <= date.fromisoformat(raw_date) <= today
        }
        if retained_dates:
            history[cell_key] = retained_dates
        else:
            del history[cell_key]
    save_thermal_history(history, now)

    burned_protection = load_burned_protection_geometry()
    mask_tiles: list[dict[str, Any]] = []
    mask_metadata: dict[str, Any]
    try:
        mask_tiles, mask_metadata = download_effis_active_mask(
            session,
            today - timedelta(days=FIRMS_PERIOD_DAYS - 1),
            today,
        )
        log(
            f"Masque EFFIS: {mask_metadata['tile_count']} tuiles chargées "
            f"pour la validation des hotspots."
        )
    except Exception as exc:
        mask_metadata = {"available": False, "error": str(exc), "layer": EFFIS_ACTIVE_FIRE_LAYER}
        log(f"AVERTISSEMENT - masque actif EFFIS indisponible: {exc}")

    filtered_candidates: list[dict[str, Any]] = []
    industrial_features: list[dict[str, Any]] = []
    excluded_known_sites = 0
    excluded_recurrent = 0

    for candidate in candidates:
        candidate["burned_confirmed"] = point_is_near_burned(
            candidate["longitude"], candidate["latitude"], burned_protection
        )
        candidate["effis_confirmed"] = bool(
            mask_tiles and effis_mask_matches(candidate["longitude"], candidate["latitude"], mask_tiles)
        )
        reason = probable_industrial_reason(
            candidate["longitude"],
            candidate["latitude"],
            candidate["cell_key"],
            history,
            burned_protection,
        )
        if reason is None:
            filtered_candidates.append(candidate)
            continue

        reason_code, site_name = reason
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [candidate["longitude"], candidate["latitude"]],
            },
            "properties": {
                "age_h": round(candidate["age_hours"], 1),
                "recency": recency_class(candidate["age_hours"]),
                "frp": candidate["frp"],
                "confidence": candidate["confidence"],
                "sensor": candidate["source_label"],
                "filter_reason": reason_code,
                "site_name": site_name,
                "recurrent_days": len(history.get(candidate["cell_key"], set())),
            },
        }
        industrial_features.append(feature)
        if reason_code == "site_industriel_connu":
            excluded_known_sites += 1
        else:
            excluded_recurrent += 1

    clusters = cluster_candidates(filtered_candidates)
    accepted_features: list[dict[str, Any]] = []
    unconfirmed_features: list[dict[str, Any]] = []
    confirmed_by_effis = 0
    confirmed_by_burned = 0
    confirmed_multi_viirs = 0

    for members in clusters:
        summary = cluster_summary(members)
        if summary["accepted"]:
            accepted_features.append(cluster_feature(summary))
            confirmed_by_effis += int(summary["effis_confirmed"])
            confirmed_by_burned += int(summary["burned_confirmed"])
            confirmed_multi_viirs += int(len(summary["sources"]) >= 2)
        else:
            unconfirmed_features.append(cluster_feature(summary, rejected=True))

    accepted_features.sort(key=lambda feature: feature["properties"]["age_h"], reverse=True)
    industrial_features.sort(key=lambda feature: feature["properties"]["age_h"], reverse=True)
    unconfirmed_features.sort(key=lambda feature: feature["properties"]["age_h"], reverse=True)

    atomic_write(
        FIRES_PATH,
        json.dumps(
            {"type": "FeatureCollection", "features": accepted_features},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    atomic_write(
        INDUSTRIAL_THERMAL_PATH,
        json.dumps(
            {"type": "FeatureCollection", "features": industrial_features},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    atomic_write(
        UNCONFIRMED_THERMAL_PATH,
        json.dumps(
            {"type": "FeatureCollection", "features": unconfirmed_features},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )

    recurrent_cells = sum(
        1 for dates in history.values() if len(dates) >= RECURRENT_MIN_DISTINCT_DAYS
    )
    manifest["active_fires"] = {
        "source": "NASA FIRMS - VIIRS NOAA-20, NOAA-21 et Suomi-NPP NRT",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "period_start": (today - timedelta(days=FIRMS_PERIOD_DAYS - 1)).isoformat(),
        "period_end": today.isoformat(),
        "count": len(accepted_features),
        "raw_detections_after_basic_filters": len(candidates),
        "candidate_clusters": len(clusters),
        "excluded_low_confidence": excluded_low_confidence,
        "excluded_non_vegetation": excluded_non_vegetation,
        "excluded_probable_industrial": len(industrial_features),
        "excluded_known_industrial_sites": excluded_known_sites,
        "excluded_recurrent_thermal_cells": excluded_recurrent,
        "excluded_unconfirmed_clusters": len(unconfirmed_features),
        "confirmed_by_effis": confirmed_by_effis,
        "confirmed_by_burned_perimeter": confirmed_by_burned,
        "confirmed_by_multiple_viirs": confirmed_multi_viirs,
        "geographic_extent": list(EUROPE_BBOX),
        "sources_status": {
            source["id"]: {
                "label": source["label"],
                "role": source["role"],
                "rows": len(source_rows.get(source["id"], [])),
                "error": source_errors.get(source["id"]),
            }
            for source in FIRMS_SOURCES
        },
        "filtering": {
            "effis_active_fire_mask": mask_metadata,
            "cluster_radius_km": CLUSTER_RADIUS_KM,
            "cluster_max_time_gap_hours": CLUSTER_MAX_TIME_GAP_HOURS,
            "known_industrial_sites": len(STATIC_THERMAL_SITES),
            "history_window_days": THERMAL_HISTORY_DAYS,
            "recurrent_threshold_distinct_days": RECURRENT_MIN_DISTINCT_DAYS,
            "recurrent_cells_in_history": recurrent_cells,
            "industrial_audit_file": INDUSTRIAL_THERMAL_PATH.name,
            "unconfirmed_audit_file": UNCONFIRMED_THERMAL_PATH.name,
        },
    }
    log(
        f"Feux probables: {len(accepted_features)} groupes retenus sur {len(clusters)}; "
        f"{len(unconfirmed_features)} groupes non corroborés, "
        f"{len(industrial_features)} sources industrielles probables, "
        f"{excluded_low_confidence} détections de faible confiance et "
        f"{excluded_non_vegetation} détections non végétales écartées."
    )
    return True


def burned_refresh_needed(manifest: dict[str, Any]) -> bool:
    if os.environ.get("FORCE_BURNED", "0") == "1" or not BURNED_PATH.exists():
        return True
    generated = manifest.get("burned_areas", {}).get("generated_at")
    if not generated:
        return True
    try:
        generated_at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError:
        return True
    return utc_now() - generated_at > timedelta(hours=20)


def stream_to_file(response: requests.Response, target: Path) -> int:
    response.raise_for_status()
    size = 0
    with target.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_EFFIS_DOWNLOAD_BYTES:
                raise RuntimeError("Le fichier EFFIS dépasse la limite de sécurité de 250 Mio.")
            handle.write(chunk)
    return size


def download_effis_shapezip(
    session: requests.Session,
    target: Path,
    start_day: date,
    end_day: date,
) -> tuple[int, str]:
    filters: list[str | None] = [
        f"firedate >= '{start_day.isoformat()}' AND firedate <= '{end_day.isoformat()}'",
        f"firedate BETWEEN '{start_day.isoformat()}' AND '{end_day.isoformat()}'",
        None,  # dernier recours: Shapefile complet, puis filtrage local
    ]
    errors: list[str] = []

    for cql_filter in filters:
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typename": EFFIS_TYPENAME,
            "outputformat": "SHAPEZIP",
            "srsName": "EPSG:4326",
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        try:
            response = session.get(
                EFFIS_WFS_URL,
                params=params,
                timeout=(30, 600),
                stream=True,
            )
            size = stream_to_file(response, target)
            if not zipfile.is_zipfile(target):
                sample = target.read_bytes()[:500].decode("utf-8", errors="replace")
                raise RuntimeError(f"réponse non ZIP: {sample}")
            return size, cql_filter or "aucun (filtrage local)"
        except Exception as exc:
            errors.append(str(exc))
            target.unlink(missing_ok=True)

    raise RuntimeError("; ".join(errors))


def normalize_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def value_for(record: dict[str, Any], candidates: Iterable[str]) -> Any:
    normalized = {normalize_key(key): value for key, value in record.items()}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized:
            return normalized[key]
    return None


def parse_effis_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text[:10], text.replace("/", "-")[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return round(result, 1)


def polygonal_only(geometry: Any) -> Polygon | MultiPolygon | None:
    if geometry.is_empty:
        return None
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        polygons = [part for part in geometry.geoms if isinstance(part, (Polygon, MultiPolygon))]
        if not polygons:
            return None
        merged = unary_union(polygons)
        return merged if isinstance(merged, (Polygon, MultiPolygon)) else None
    return None


def round_coordinates(value: Any, precision: int = 5) -> Any:
    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, tuple):
        return [round_coordinates(item, precision) for item in value]
    if isinstance(value, list):
        return [round_coordinates(item, precision) for item in value]
    if isinstance(value, dict):
        return {key: round_coordinates(item, precision) for key, item in value.items()}
    return value


def shapefile_to_geojson(
    archive_path: Path,
    extraction_dir: Path,
    start_day: date,
    end_day: date,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extraction_dir)

    shp_files = sorted(extraction_dir.rglob("*.shp"), key=lambda path: path.stat().st_size, reverse=True)
    if not shp_files:
        raise RuntimeError("Le ZIP EFFIS ne contient aucun fichier .shp.")

    reader = shapefile.Reader(str(shp_files[0]), encoding="utf-8", encodingErrors="replace")
    features: list[dict[str, Any]] = []
    rejected_old = 0
    rejected_outside = 0
    rejected_geometry = 0
    total_area_ha = 0.0

    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        fire_date = parse_effis_date(value_for(record, ("firedate", "fire_date", "startdate", "start_date")))
        if fire_date and not (start_day <= fire_date <= end_day):
            rejected_old += 1
            continue

        try:
            geometry = shape(shape_record.shape.__geo_interface__)
            if not geometry.is_valid:
                geometry = make_valid(geometry)
            geometry = polygonal_only(geometry)
            if geometry is None or not geometry.intersects(EUROPE_CLIP):
                rejected_outside += 1
                continue
            geometry = polygonal_only(geometry.intersection(EUROPE_CLIP))
            if geometry is None:
                rejected_outside += 1
                continue

            area_ha = safe_float(value_for(record, ("area_ha", "area ha", "area")))
            tolerance = 0.00022
            if area_ha is not None and area_ha >= 5000:
                tolerance = 0.0007
            elif area_ha is not None and area_ha >= 500:
                tolerance = 0.0004
            geometry = polygonal_only(geometry.simplify(tolerance, preserve_topology=True))
            if geometry is None or geometry.is_empty:
                rejected_geometry += 1
                continue
        except Exception:
            rejected_geometry += 1
            continue

        if area_ha is not None:
            total_area_ha += area_ha

        geometry_json = round_coordinates(mapping(geometry), 5)
        features.append({
            "type": "Feature",
            "geometry": geometry_json,
            "properties": {
                "firedate": fire_date.isoformat() if fire_date else None,
                "area_ha": area_ha,
                "country": value_for(record, ("countryful", "country", "countryname")),
            },
        })

    features.sort(key=lambda feature: (
        feature["properties"].get("firedate") or "",
        feature["properties"].get("area_ha") or 0,
    ))
    collection = {"type": "FeatureCollection", "features": features}
    stats = {
        "count": len(features),
        "total_area_ha": round(total_area_ha, 1),
        "records_read": len(reader),
        "rejected_outside_period": rejected_old,
        "rejected_outside_extent": rejected_outside,
        "rejected_invalid_geometry": rejected_geometry,
    }
    reader.close()
    return collection, stats


def update_burned_areas(session: requests.Session, manifest: dict[str, Any]) -> bool:
    if not burned_refresh_needed(manifest):
        log("Surfaces brûlées: fichier vectoriel encore récent, téléchargement ignoré.")
        return False

    now = utc_now()
    end_day = now.date()
    start_day = end_day - timedelta(days=30)

    with tempfile.TemporaryDirectory(prefix="effis-burned-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        archive_path = temp_dir / "effis-burned.zip"
        archive_size, cql_filter = download_effis_shapezip(session, archive_path, start_day, end_day)
        collection, stats = shapefile_to_geojson(
            archive_path,
            temp_dir / "extracted",
            start_day,
            end_day,
        )

    payload = json.dumps(collection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    atomic_write(BURNED_PATH, payload)
    LEGACY_BURNED_PATH.unlink(missing_ok=True)

    manifest["burned_areas"] = {
        "source": "EFFIS / Copernicus - périmètres MODIS supervisés",
        "transport": "WFS SHAPEZIP",
        "layer": EFFIS_TYPENAME,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "period_start": start_day.isoformat(),
        "period_end": end_day.isoformat(),
        "count": stats["count"],
        "total_area_ha": stats["total_area_ha"],
        "geographic_extent": list(EUROPE_BBOX),
        "archive_bytes": archive_size,
        "geojson_bytes": len(payload),
        "filter": cql_filter,
        "processing": stats,
    }
    log(
        f"Surfaces brûlées: {stats['count']} périmètres EFFIS enregistrés "
        f"({len(payload) / 1024:.0f} Kio de GeoJSON)."
    )
    return True


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = build_session()
    failures: list[str] = []
    changed = False

    # Les surfaces brûlées sont traitées en premier afin que leur géométrie la
    # plus récente puisse servir de confirmation aux détections actives.
    try:
        changed = update_burned_areas(session, manifest) or changed
    except Exception as exc:
        failures.append(f"EFFIS surfaces brûlées: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    try:
        changed = update_active_fires(session, manifest) or changed
    except Exception as exc:
        failures.append(f"NASA FIRMS / validation EFFIS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    manifest["last_run_at"] = utc_now().isoformat().replace("+00:00", "Z")
    manifest["last_run_errors"] = failures
    atomic_write(
        MANIFEST_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
    )

    valid_fires = False
    try:
        existing_fires = json.loads(FIRES_PATH.read_text(encoding="utf-8"))
        valid_fires = bool(existing_fires.get("features"))
    except (OSError, json.JSONDecodeError, AttributeError):
        valid_fires = False

    if failures and not valid_fires:
        log("ÉCHEC - aucune donnée FIRMS valide n'est disponible dans le dépôt.")
        return 1
    if changed:
        log("Mise à jour terminée.")
    else:
        log("Aucune donnée distante n'a remplacé les fichiers existants.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
