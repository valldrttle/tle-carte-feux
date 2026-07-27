Texte collé(89).txt
Document
OK. J'ai déjà un fond de carte paramétré comme je l'entends dans le code ci-joint. (La carte porte sur un tout autre sujet, mais j'aimerais garder cet aspect visuel.
Concrètement, si je veux visualiser les terres brûlées sur la saison des feux sur cette carte. Comment puis-je procéder ? 

aujourd’hui 11:08
Texte collé(92).txt
Document
Voici ci-joint ma version actuelle de la carte. Le problème est que pour cette carte, le temps de chargement est beaucoup trop long. Et parfois la requête WMS EFFIS échoue. Quelles solutions me proposes-tu ?

Parfait. Il faut maintenant exécuter ce workflow manuellement pour générer les vraies données.

    Dans Actions, cliquez sur Mettre à jour la carte des feux dans la colonne de gauche.

    Cliquez sur le bouton Run workflow à droite.

    Vérifiez que la branche sélectionnée est main.

    Cliquez à nouveau sur le bouton vert Run workflow.

Une nouvelle exécution doit apparaître après quelques secondes. Ouvrez-la, puis cliquez sur le job update.

Les étapes doivent notamment inclure:

Récupérer le dépôt
Installer Python
Installer les dépendances
Télécharger et préparer les données
Enregistrer les nouveaux fichiers

Résultat attendu

Toutes les étapes doivent devenir vertes. L'étape la plus importante est:

Télécharger et préparer les données

Elle devrait afficher un message indiquant qu'un certain nombre de détections VIIRS ont été enregistrées.

Ensuite, GitHub doit créer automatiquement un commit nommé:

Mise à jour automatique des données incendies

Après cela, contrôlez de nouveau:

https://valldrttle.github.io/tle-carte-feux/data/manifest.json

Le manifeste devra contenir une section active_fires et un champ count supérieur à zéro. La publication GitHub Pages peut prendre une ou deux minutes après le commit.

Si le workflow devient rouge, ouvrez l'étape rouge et copiez ici le message d'erreur complet, en particulier celui de Télécharger et préparer les données.

Message rouge : "1 error
update
Process completed with exit code 1." 

Le code 1 signifie ici une chose précise: la récupération NASA FIRMS a échoué et aucun ancien fichier fires.geojson valide n'était disponible. Le serveur EFFIS peut également avoir échoué, mais une panne EFFIS seule ne provoquerait pas cet arrêt si les points FIRMS avaient bien été récupérés.

Le message utile se trouve quelques lignes avant Process completed with exit code 1.
Retrouver l'erreur exacte

Dans GitHub:

    Ouvrez Actions.

    Cliquez sur l'exécution rouge de Mettre à jour la carte des feux.

    Cliquez sur le bloc update.

    Ouvrez l'étape marquée d'une croix rouge, probablement Télécharger et préparer les données.

    Descendez tout en bas.

Cherchez une ligne commençant par:

AVERTISSEMENT - NASA FIRMS:

ou:

ÉCHEC - aucune donnée FIRMS valide n'est disponible dans le dépôt.

GitHub développe normalement automatiquement les journaux de l'étape qui a échoué.
Vérification la plus probable: la clé FIRMS

Ouvrez:

Settings > Secrets and variables > Actions > Repository secrets

Vous devez voir exactement:

FIRMS_MAP_KEY

Attention:

    ce doit être un Repository secret, pas une variable;

    le nom doit être strictement FIRMS_MAP_KEY;

    la valeur doit être uniquement la clé, sans guillemets ni espace;

    GitHub ne montre jamais la valeur après l'enregistrement, seulement le nom.

Le workflow transmet ce secret au script avec:

env:
  FIRMS_MAP_KEY: ${{ secrets.FIRMS_MAP_KEY }}

NASA exige une MAP_KEY valide pour utiliser l'API Area, et la source VIIRS_NOAA20_NRT employée par le script est bien une source actuellement acceptée.
Si le secret est absent

Cliquez sur New repository secret, puis saisissez:

Name: FIRMS_MAP_KEY
Secret: votre clé NASA

Enregistrez et relancez le workflow.
Si le secret existe déjà

Recréez-le avec la clé reçue de NASA:

    Cliquez sur FIRMS_MAP_KEY.

    Cliquez sur Update secret.

    Recopiez la clé NASA sans espaces.

    Relancez le workflow.

Ne publiez pas la valeur de cette clé ici. Copiez seulement les 5 à 10 lignes du journal situées juste avant Process completed with exit code 1; elles permettront d'identifier immédiatement si la clé est absente, invalide ou si FIRMS a renvoyé une autre erreur.

Voici mon message d'erreur : 
"Run python scripts/update_data.py
  python scripts/update_data.py
  shell: /usr/bin/bash -e {0}
  env:
    pythonLocation: /opt/hostedtoolcache/Python/3.13.14/x64
    PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.13.14/x64/lib/pkgconfig
    Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.13.14/x64
    Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.13.14/x64
    Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.13.14/x64
    LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.13.14/x64/lib
    FIRMS_MAP_KEY: ***
    FORCE_BURNED: 1
  File "/home/runner/work/tle-carte-feux/tle-carte-feux/scripts/update_data.py", line 3
    OK. J'ai déjà un fond de carte paramétré comme je l'entends dans le code ci-joint. (La carte porte sur un tout autre sujet, mais j'aimerais garder cet aspect visuel.
                                                                                                                                      ^
SyntaxError: unterminated string literal (detected at line 3)
Error: Process completed with exit code 1." 

L'erreur est clairement identifiée: le fichier scripts/update_data.py ne contient pas le script Python attendu.

À la ligne 3, GitHub trouve ce texte:

OK. J'ai déjà un fond de carte paramétré...

Ce texte provient d'un ancien échange et n'est pas du code Python. La clé FIRMS est en revanche bien transmise, puisque le journal affiche:

FIRMS_MAP_KEY: ***

Remplacer le fichier incorrect

Téléchargez d'abord le script propre:

Puis, dans votre dépôt GitHub:

    Ouvrez:
    scripts > update_data.py

    Cliquez sur l'icône en forme de crayon Edit this file.

    Sélectionnez tout le contenu avec Ctrl + A ou Cmd + A.

    Supprimez-le entièrement.

    Ouvrez le fichier corrigé téléchargé avec un éditeur de texte.

    Copiez l'intégralité de son contenu.

    Collez-le dans l'éditeur GitHub.

    Cliquez sur Commit changes.

    Confirmez le commit sur la branche main.

Le début du fichier doit être exactement de cette forme:

#!/usr/bin/env python3
"""Met à jour les données statiques de la carte des feux.

- Feux actifs : NASA FIRMS, VIIRS NOAA-20 NRT, 7 jours.
- Surfaces brûlées : image WMS EFFIS MODIS + VIIRS NRT, 30 jours.

Les fichiers précédents sont conservés si une source distante échoue.
"""

Il ne doit plus contenir la phrase:

OK. J'ai déjà un fond de carte...

Relancer l'action

Après le commit:

    Ouvrez Actions.

    Sélectionnez Mettre à jour la carte des feux.

    Cliquez sur Run workflow.

    Choisissez la branche main.

    Confirmez avec Run workflow.

Cette fois, l'étape:

Télécharger et préparer les données

doit dépasser immédiatement la ligne 3 et commencer à contacter NASA FIRMS.

Après une exécution verte, vérifiez:

https://valldrttle.github.io/tle-carte-feux/data/manifest.json

Le champ last_run_at ne devra plus être null, et une section active_fires avec un nombre de détections devra apparaître.


update_data_corrige.py

#!/usr/bin/env python3
"""Met à jour les données statiques de la carte des feux.

- Feux actifs : NASA FIRMS, VIIRS NOAA-20 NRT, 7 jours.
- Surfaces brûlées : image WMS EFFIS MODIS + VIIRS NRT, 30 jours.

Les fichiers précédents sont conservés si une source distante échoue.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
FIRES_PATH = DATA_DIR / "fires.geojson"
BURNED_PATH = DATA_DIR / "burned.png"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EUROPE_BBOX = (-25.0, 27.0, 45.0, 72.0)  # ouest, sud, est, nord
FIRMS_SOURCE = "VIIRS_NOAA20_NRT"
EFFIS_LAYER = "modisviirsnrt"


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
        "User-Agent": "tle-carte-feux/1.0 (+https://github.com/valldrttle/tle-carte-feux)"
    })
    return session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1}


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
    if text.startswith("Invalid") or "MAP_KEY" in text[:250] and "," not in text[:250]:
        raise RuntimeError(f"Réponse FIRMS invalide: {text[:250]}")
    return list(csv.DictReader(io.StringIO(text)))


def update_active_fires(session: requests.Session, manifest: dict[str, Any]) -> bool:
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise RuntimeError("Le secret GitHub FIRMS_MAP_KEY n'est pas défini.")

    today = utc_now().date()
    # L'API Area limite une requête à 5 jours. Deux appels couvrent donc 7 jours.
    recent_rows = download_csv(session, firms_url(map_key, 5))
    older_start = today - timedelta(days=6)
    older_rows = download_csv(session, firms_url(map_key, 2, older_start))

    now = utc_now()
    oldest_allowed = now - timedelta(days=7, hours=3)
    seen: set[tuple[str, str, str, str]] = set()
    features: list[dict[str, Any]] = []

    for row in older_rows + recent_rows:
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
            },
        })

    # Les plus anciennes sont dessinées en premier; les plus récentes restent visibles au-dessus.
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
    }
    log(f"Feux actifs: {len(features)} détections enregistrées.")
    return True


def lon_to_mercator_x(lon: float) -> float:
    return lon * 20037508.34 / 180.0


def lat_to_mercator_y(lat: float) -> float:
    capped = max(min(lat, 85.05112878), -85.05112878)
    radians = math.radians(capped)
    return 6378137.0 * math.log(math.tan(math.pi / 4.0 + radians / 2.0))


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


def update_burned_areas(session: requests.Session, manifest: dict[str, Any]) -> bool:
    if not burned_refresh_needed(manifest):
        log("Surfaces brûlées: fichier encore récent, téléchargement ignoré.")
        return False

    now = utc_now()
    end_day = now.date()
    start_day = end_day - timedelta(days=30)
    west, south, east, north = EUROPE_BBOX
    min_x, min_y = lon_to_mercator_x(west), lat_to_mercator_y(south)
    max_x, max_y = lon_to_mercator_x(east), lat_to_mercator_y(north)

    width = 1800
    height = round(width * (max_y - min_y) / (max_x - min_x))
    height = max(1200, min(height, 2400))

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": EFFIS_LAYER,
        "STYLES": "",
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
        "SINGLETILE": "true",
        "SRS": "EPSG:3857",
        "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "TIME": f"{start_day.isoformat()}/{end_day.isoformat()}",
    }
    response = session.get(
        "https://maps.effis.emergency.copernicus.eu/gwis",
        params=params,
        timeout=(30, 300),
    )
    response.raise_for_status()
    content = response.content
    if len(content) < 1000 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        sample = content[:300].decode("utf-8", errors="replace")
        raise RuntimeError(f"EFFIS n'a pas renvoyé un PNG valide: {sample}")

    atomic_write(BURNED_PATH, content)
    manifest["burned_areas"] = {
        "source": "EFFIS / Copernicus - MODIS et VIIRS NRT",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "period_start": start_day.isoformat(),
        "period_end": end_day.isoformat(),
        "width": width,
        "height": height,
    }
    log(f"Surfaces brûlées: PNG enregistré ({len(content) / 1024:.0f} Kio).")
    return True


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = build_session()
    failures: list[str] = []
    changed = False

    try:
        changed = update_active_fires(session, manifest) or changed
    except Exception as exc:  # L'ancien fichier reste en place.
        failures.append(f"NASA FIRMS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    try:
        changed = update_burned_areas(session, manifest) or changed
    except Exception as exc:  # L'ancien fichier reste en place.
        failures.append(f"EFFIS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    manifest["last_run_at"] = utc_now().isoformat().replace("+00:00", "Z")
    manifest["last_run_errors"] = failures
    atomic_write(
        MANIFEST_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
    )

    # Le dépôt contient au départ un GeoJSON vide. Une simple existence du fichier
    # ne suffit donc pas à considérer la collecte FIRMS comme valide.
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

update_data_corrige.py

#!/usr/bin/env python3
"""Met à jour les données statiques de la carte des feux.

- Feux actifs : NASA FIRMS, VIIRS NOAA-20 NRT, 7 jours.
- Surfaces brûlées : image WMS EFFIS MODIS + VIIRS NRT, 30 jours.

Les fichiers précédents sont conservés si une source distante échoue.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
FIRES_PATH = DATA_DIR / "fires.geojson"
BURNED_PATH = DATA_DIR / "burned.png"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EUROPE_BBOX = (-25.0, 27.0, 45.0, 72.0)  # ouest, sud, est, nord
FIRMS_SOURCE = "VIIRS_NOAA20_NRT"
EFFIS_LAYER = "modisviirsnrt"


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
        "User-Agent": "tle-carte-feux/1.0 (+https://github.com/valldrttle/tle-carte-feux)"
    })
    return session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1}


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
    if text.startswith("Invalid") or "MAP_KEY" in text[:250] and "," not in text[:250]:
        raise RuntimeError(f"Réponse FIRMS invalide: {text[:250]}")
    return list(csv.DictReader(io.StringIO(text)))


def update_active_fires(session: requests.Session, manifest: dict[str, Any]) -> bool:
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise RuntimeError("Le secret GitHub FIRMS_MAP_KEY n'est pas défini.")

    today = utc_now().date()
    # L'API Area limite une requête à 5 jours. Deux appels couvrent donc 7 jours.
    recent_rows = download_csv(session, firms_url(map_key, 5))
    older_start = today - timedelta(days=6)
    older_rows = download_csv(session, firms_url(map_key, 2, older_start))

    now = utc_now()
    oldest_allowed = now - timedelta(days=7, hours=3)
    seen: set[tuple[str, str, str, str]] = set()
    features: list[dict[str, Any]] = []

    for row in older_rows + recent_rows:
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
            },
        })

    # Les plus anciennes sont dessinées en premier; les plus récentes restent visibles au-dessus.
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
    }
    log(f"Feux actifs: {len(features)} détections enregistrées.")
    return True


def lon_to_mercator_x(lon: float) -> float:
    return lon * 20037508.34 / 180.0


def lat_to_mercator_y(lat: float) -> float:
    capped = max(min(lat, 85.05112878), -85.05112878)
    radians = math.radians(capped)
    return 6378137.0 * math.log(math.tan(math.pi / 4.0 + radians / 2.0))


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


def update_burned_areas(session: requests.Session, manifest: dict[str, Any]) -> bool:
    if not burned_refresh_needed(manifest):
        log("Surfaces brûlées: fichier encore récent, téléchargement ignoré.")
        return False

    now = utc_now()
    end_day = now.date()
    start_day = end_day - timedelta(days=30)
    west, south, east, north = EUROPE_BBOX
    min_x, min_y = lon_to_mercator_x(west), lat_to_mercator_y(south)
    max_x, max_y = lon_to_mercator_x(east), lat_to_mercator_y(north)

    width = 1800
    height = round(width * (max_y - min_y) / (max_x - min_x))
    height = max(1200, min(height, 2400))

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": EFFIS_LAYER,
        "STYLES": "",
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
        "SINGLETILE": "true",
        "SRS": "EPSG:3857",
        "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "TIME": f"{start_day.isoformat()}/{end_day.isoformat()}",
    }
    response = session.get(
        "https://maps.effis.emergency.copernicus.eu/gwis",
        params=params,
        timeout=(30, 300),
    )
    response.raise_for_status()
    content = response.content
    if len(content) < 1000 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        sample = content[:300].decode("utf-8", errors="replace")
        raise RuntimeError(f"EFFIS n'a pas renvoyé un PNG valide: {sample}")

    atomic_write(BURNED_PATH, content)
    manifest["burned_areas"] = {
        "source": "EFFIS / Copernicus - MODIS et VIIRS NRT",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "period_start": start_day.isoformat(),
        "period_end": end_day.isoformat(),
        "width": width,
        "height": height,
    }
    log(f"Surfaces brûlées: PNG enregistré ({len(content) / 1024:.0f} Kio).")
    return True


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = build_session()
    failures: list[str] = []
    changed = False

    try:
        changed = update_active_fires(session, manifest) or changed
    except Exception as exc:  # L'ancien fichier reste en place.
        failures.append(f"NASA FIRMS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    try:
        changed = update_burned_areas(session, manifest) or changed
    except Exception as exc:  # L'ancien fichier reste en place.
        failures.append(f"EFFIS: {exc}")
        log(f"AVERTISSEMENT - {failures[-1]}")

    manifest["last_run_at"] = utc_now().isoformat().replace("+00:00", "Z")
    manifest["last_run_errors"] = failures
    atomic_write(
        MANIFEST_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
    )

    # Le dépôt contient au départ un GeoJSON vide. Une simple existence du fichier
    # ne suffit donc pas à considérer la collecte FIRMS comme valide.
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

