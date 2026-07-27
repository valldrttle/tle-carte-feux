#!/usr/bin/env python3
"""Met à jour les données statiques de la carte des feux.

- Feux actifs : NASA FIRMS, VIIRS NOAA-20 NRT, 7 jours.
- Surfaces brûlées : périmètres vectoriels EFFIS MODIS, 30 jours.

Le téléchargement EFFIS utilise en priorité le Shapefile officiel diffusé par
le service WFS. Les fichiers précédents sont conservés si une source distante
échoue.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
import shapefile
from requests.adapters import HTTPAdapter
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
FIRES_PATH = DATA_DIR / "fires.geojson"
BURNED_PATH = DATA_DIR / "burned.geojson"
LEGACY_BURNED_PATH = DATA_DIR / "burned.png"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EUROPE_BBOX = (-25.0, 34.0, 42.0, 72.0)  # ouest, sud, est, nord
EUROPE_CLIP = box(*EUROPE_BBOX)
FIRMS_SOURCE = "VIIRS_NOAA20_NRT"
EFFIS_WFS_URL = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_TYPENAME = "ms:modis.ba.poly"
MAX_EFFIS_DOWNLOAD_BYTES = 250 * 1024 * 1024


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
        "User-Agent": "tle-carte-feux/2.0 (+https://github.com/valldrttle/tle-carte-feux)"
    })
    return session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 2}
    try:
        result = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        result["version"] = 2
        return result
    except (OSError, json.JSONDecodeError):
        return {"version": 2}


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


def firms_url(map_key: str, day_range: int, start_date: date | None = None) -> str:
    west, south, east, north = EUROPE_BBOX
    area = f"{west},{south},{east},{north}"
    base = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{map_key}/{FIRMS_SOURCE}/{area}/{day_range}"
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


def update_active_fires(session: requests.Session, manifest: dict[str, Any]) -> bool:
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise RuntimeError("Le secret GitHub FIRMS_MAP_KEY n'est pas défini.")

    today = utc_now().date()
    recent_rows = download_csv(session, firms_url(map_key, 5))
    older_start = today - timedelta(days=6)
    older_rows = download_csv(session, firms_url(map_key, 2, older_start))

    now = utc_now()
    oldest_allowed = now - timedelta(days=7, hours=3)
    seen: set[tuple[str, str, str, str]] = set()
    features: list[dict[str, Any]] = []
    excluded_low_confidence = 0
    excluded_non_vegetation = 0

    for row in older_rows + recent_rows:
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

        key = (str(latitude), str(longitude), row.get("acq_date", ""), row.get("acq_time", ""))
        if key in seen:
            continue
        seen.add(key)

        age_hours = max(0.0, (now - detected_at).total_seconds() / 3600)
        try:
            frp = round(float(row.get("frp") or 0), 1)
        except ValueError:
            frp = 0.0

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {
                "age_h": round(age_hours, 1),
                "recency": recency_class(age_hours),
                "frp": frp,
                "confidence": "high" if confidence_raw in {"h", "high"} else "nominal",
            },
        })

    features.sort(key=lambda feature: feature["properties"]["age_h"], reverse=True)
    collection = {"type": "FeatureCollection", "features": features}
    payload = json.dumps(collection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    atomic_write(FIRES_PATH, payload)

    manifest["active_fires"] = {
        "source": "NASA FIRMS - VIIRS NOAA-20 NRT",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "period_start": (today - timedelta(days=6)).isoformat(),
        "period_end": today.isoformat(),
        "count": len(features),
        "excluded_low_confidence": excluded_low_confidence,
        "excluded_non_vegetation": excluded_non_vegetation,
        "geographic_extent": list(EUROPE_BBOX),
    }
    log(
        f"Feux actifs: {len(features)} détections enregistrées; "
        f"{excluded_low_confidence} de faible confiance écartées."
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

    try:
        changed = update_active_fires(session, manifest) or changed
    except Exception as exc:
        failures.append(f"NASA FIRMS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    try:
        changed = update_burned_areas(session, manifest) or changed
    except Exception as exc:
        failures.append(f"EFFIS: {exc}")
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
