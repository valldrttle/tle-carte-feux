Texte collé(89).txt
Document
OK. J'ai déjà un fond de carte paramétré comme je l'entends dans le code ci-joint. (La carte porte sur un tout autre sujet, mais j'aimerais garder cet aspect visuel.
Concrètement, si je veux visualiser les terres brûlées sur la saison des feux sur cette carte. Comment puis-je procéder ? 

aujourd’hui 11:08
Texte collé(92).txt
Document
Voici ci-joint ma version actuelle de la carte. Le problème est que pour cette carte, le temps de chargement est beaucoup trop long. Et parfois la requête WMS EFFIS échoue. Quelles solutions me proposes-tu ?

Parfait. J'ai préparé le dépôt complet, prêt à être ajouté à GitHub:

Cette première version utilise:

    NASA FIRMS, VIIRS NOAA-20 NRT, pour les feux actifs des sept derniers jours;

    une couleur par ancienneté: moins de 24 heures, 1 à 3 jours, 3 à 5 jours et 5 à 7 jours;

    une carte de densité à l'échelle européenne, remplacée progressivement par des points au zoom rapproché;

    une image EFFIS des surfaces brûlées des trente derniers jours, préparée une fois par jour;

    MapLibre et un fond vectoriel OpenFreeMap;

    GitHub Actions pour actualiser les données toutes les trois heures;

    GitHub Pages pour héberger la carte;

    une iframe légère pour WordPress.

FIRMS limite actuellement l'API Area à cinq jours par requête. Le script effectue donc deux appels puis les fusionne pour couvrir sept jours.
1. Décompresser l'archive

Décompressez tle-carte-feux-depot.zip.

Vous obtiendrez notamment:

.github/workflows/update-data.yml
docs/index.html
docs/data/
scripts/update_data.py
requirements.txt
wordpress-embed.html
README.md

2. Copier les fichiers dans GitHub

Dans votre dépôt:

https://github.com/valldrttle/tle-carte-feux

cliquez sur:

Add file > Upload files

Glissez le contenu intérieur du dossier tle-carte-feux-depot, et non le dossier parent lui-même.

À la racine du dépôt, vous devez donc voir directement:

.github
docs
scripts
README.md
requirements.txt
wordpress-embed.html

Validez avec Commit changes.
3. Ajouter la clé NASA FIRMS

La clé FIRMS doit rester secrète. NASA fournit gratuitement une MAP_KEY destinée à ses API et services cartographiques.

Dans le dépôt GitHub:

Settings
> Secrets and variables
> Actions
> New repository secret

Renseignez:

Name: FIRMS_MAP_KEY
Secret: votre clé NASA FIRMS

Ne placez jamais cette clé dans un fichier public du dépôt.
4. Autoriser GitHub Actions à écrire

Ouvrez:

Settings
> Actions
> General
> Workflow permissions

Sélectionnez:

Read and write permissions

puis enregistrez.

Cette autorisation permet au robot GitHub Actions d'enregistrer les nouveaux fichiers fires.geojson, burned.png et manifest.json.
5. Activer GitHub Pages

Ouvrez:

Settings
> Pages

Choisissez:

Source: Deploy from a branch
Branch: main
Folder: /docs

puis cliquez sur Save.

GitHub Pages permet précisément de publier un site depuis un dossier d'une branche, notamment le dossier /docs.
6. Lancer la première mise à jour

Ouvrez l'onglet:

Actions

Sélectionnez:

Mettre à jour la carte des feux

Puis:

Run workflow
> Branch: main
> Run workflow

Ce premier lancement:

    télécharge les détections VIIRS NOAA-20;

    les convertit en GeoJSON allégé;

    calcule leur ancienneté;

    télécharge l'image EFFIS des trente derniers jours;

    enregistre les données dans docs/data;

    crée automatiquement un commit.

Les workflows planifiés GitHub utilisent une expression cron. Celui du dépôt est programmé toutes les trois heures, à la minute 17.
7. Vérifier la carte

L'adresse attendue est:

https://valldrttle.github.io/tle-carte-feux/

La carte peut également être ouverte depuis le lien indiqué dans Settings > Pages.

Le moteur utilise un fond OpenFreeMap compatible MapLibre, sans clé de fond de carte.
8. Intégrer la carte dans WordPress

Le fichier:

wordpress-embed.html

contient le bloc suivant:

<div style="max-width:1040px;margin:20px auto;">
  <iframe
    src="https://valldrttle.github.io/tle-carte-feux/"
    title="Carte des feux actifs et des surfaces brûlées en Europe"
    loading="lazy"
    style="display:block;width:100%;height:780px;border:0;overflow:hidden;"
    referrerpolicy="strict-origin-when-cross-origin"
  ></iframe>
</div>

Copiez-le dans un bloc HTML personnalisé WordPress.
Comportement prévu

Les lecteurs de votre site ne contacteront plus directement NASA ou EFFIS. Ils chargeront seulement deux fichiers statiques depuis GitHub Pages:

docs/data/fires.geojson
docs/data/burned.png

Les déplacements et les zooms seront donc calculés localement par MapLibre. Les couches GeoJSON peuvent être rendues sous forme de carte de chaleur ou de points sans nouvelle requête aux fournisseurs.

En cas d'échec temporaire d'EFFIS ou de FIRMS, le script conserve le dernier fichier valide. Le pied de la carte signale simplement que la mise à jour distante a été retardée.

Je suis perdu à l'étape 4. Je ne trouve pas quelle action je dois faire

L'étape 4 correspond à un réglage situé assez bas dans la page GitHub.

Dans votre dépôt tle-carte-feux:

    Cliquez sur Settings.

    Dans la colonne de gauche, ouvrez Actions.

    Cliquez sur General.

    Faites défiler la page presque tout en bas jusqu'à la section Workflow permissions.

    Sélectionnez Read and write permissions.

    Cliquez sur Save. GitHub place bien ce réglage dans Settings > Actions > General.

Ne cochez pas nécessairement Allow GitHub Actions to create and approve pull requests: notre automatisation n'en a pas besoin.
Si vous ne voyez pas «Workflow permissions»

Vous pouvez passer à l'étape suivante pour le moment. Le fichier que je vous ai fourni contient déjà cette instruction:

permissions:
  contents: write

Elle demande explicitement au robot GitHub l'autorisation de modifier les fichiers du dépôt. GitHub permet de définir ces droits directement dans le fichier du workflow avec la clé permissions.

Lancez donc la première mise à jour dans:

Actions > Mettre à jour la carte des feux > Run workflow

Si l'exécution échoue sur l'étape git push avec un message du type Permission denied, 403 ou Write access not granted, nous reviendrons alors précisément sur ce réglage.

Ma carte reste vierge, alors que j'ai respecté toutes les étapes : "https://valldrttle.github.io/tle-carte-feux/" 
Et je n'ai pas de message d'erreur

J'ai identifié un défaut dans la version que je vous ai fournie.

Le dépôt initial contient volontairement des fichiers d'attente:

    fires.geojson: vide, avec zéro détection;

    burned.png: image transparente de 2 × 2 pixels;

    manifest.json: sans information active_fires.

Le script devait les remplacer lors du premier lancement. Mais il contenait une erreur logique: si FIRMS échouait, le workflow pouvait malgré tout apparaître comme réussi, car il vérifiait seulement que fires.geojson existait, sans vérifier qu'il contenait réellement des données.

Par ailleurs, les erreurs du fond cartographique étaient seulement écrites dans la console. Cela explique la carte vierge sans message visible.
Correctif préparé

Vous pouvez télécharger l'ensemble corrigé:

Ou remplacer uniquement les deux fichiers concernés:

La nouvelle page utilise toujours MapLibre 5.24.0, mais avec un fond raster CARTO défini directement dans le code. Elle ne dépend donc plus du chargement d'un style OpenFreeMap distant. MapLibre 5.24.0 est bien une version publiée et les fonds OpenFreeMap sont normalement compatibles; la modification vise surtout à réduire les dépendances et à rendre les erreurs visibles.
1. Remplacer docs/index.html

Dans votre dépôt GitHub:

    Ouvrez le dossier docs.

    Ouvrez index.html.

    Cliquez sur l'icône crayon Edit this file.

    Supprimez tout le contenu.

    Ouvrez le fichier corrigé téléchargé:

    Copiez tout son contenu dans GitHub.

    Cliquez sur Commit changes.

Le fichier doit toujours s'appeler exactement:

docs/index.html

2. Remplacer scripts/update_data.py

Dans GitHub:

    Ouvrez le dossier scripts.

    Ouvrez update_data.py.

    Cliquez sur le crayon.

    Remplacez son contenu par celui de:

    Validez avec Commit changes.

La version corrigée fait désormais échouer clairement GitHub Actions lorsque FIRMS ne répond pas et qu'aucune donnée valide n'est disponible.
3. Relancer l'automatisation

Ouvrez:

Actions
> Mettre à jour la carte des feux
> Run workflow
> Run workflow

Lorsque l'exécution est terminée, ouvrez-la et vérifiez l'étape:

Télécharger et préparer les données

Vous devez voir une ligne similaire à:

Feux actifs: 1234 détections enregistrées.

Le nombre exact sera différent.

Si cette étape est rouge, le message sera désormais explicite, par exemple:

Le secret GitHub FIRMS_MAP_KEY n'est pas défini.

ou:

Réponse FIRMS invalide

4. Vérifier directement les données

Ouvrez ces deux adresses dans votre navigateur:

https://valldrttle.github.io/tle-carte-feux/data/manifest.json

https://valldrttle.github.io/tle-carte-feux/data/fires.geojson

Le manifeste doit contenir

"active_fires": {
  "source": "NASA FIRMS - VIIRS NOAA-20 NRT",
  "generated_at": "...",
  "period_start": "...",
  "period_end": "...",
  "count": 1234
}

Le champ count doit être supérieur à zéro.
Le GeoJSON doit contenir

{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [...]
      }
    }
  ]
}

Si vous voyez:

{"type":"FeatureCollection","features":[]}

la collecte FIRMS n'a pas fonctionné.
5. Recharger la carte

Rechargez ensuite:

https://valldrttle.github.io/tle-carte-feux/

Utilisez un rechargement forcé:

    Windows: Ctrl + F5;

    macOS: Cmd + Shift + R.

La nouvelle version ne doit plus rester silencieusement vierge. Elle affichera l'un de ces diagnostics:

    Le fond fonctionne, mais aucune détection VIIRS n'a été chargée;

    Le fond de carte n'a pas pu être chargé;

    Une couche n'a pas pu être ajoutée;

    MapLibre n'a pas pu être téléchargé.

GitHub Pages publie les fichiers du dossier /docs lorsque cette source a été sélectionnée dans les paramètres du dépôt.

Le point le plus important est maintenant de vérifier le contenu de manifest.json: il permettra de savoir immédiatement si le problème vient encore de la collecte FIRMS ou uniquement de l'affichage.


Bibliothèque
/update_data_corrige.py

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

Bibliothèque
/update_data_corrige.py

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

