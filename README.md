# TLE - Carte des feux en Europe

Carte MapLibre destinée à être hébergée sur GitHub Pages puis intégrée dans WordPress par une iframe.

## Données

- **Feux actifs** : NASA FIRMS, VIIRS NOAA-20 NRT, sept derniers jours.
- **Surfaces brûlées** : EFFIS / Copernicus, MODIS et VIIRS NRT, trente derniers jours.
- **Fond de carte** : OpenFreeMap / OpenStreetMap.

Les données sont préparées par GitHub Actions. Les lecteurs ne contactent donc ni FIRMS ni EFFIS lorsqu'ils déplacent la carte.

## Installation

### 1. Copier les fichiers

Copier tout le contenu de cette archive à la racine du dépôt `valldrttle/tle-carte-feux`.

### 2. Ajouter la clé NASA FIRMS

Dans GitHub :

`Settings > Secrets and variables > Actions > New repository secret`

- Nom : `FIRMS_MAP_KEY`
- Valeur : la clé gratuite reçue de NASA FIRMS.

La clé se demande sur la page officielle NASA FIRMS consacrée aux MAP_KEY.

### 3. Autoriser l'écriture du workflow

Dans :

`Settings > Actions > General > Workflow permissions`

sélectionner **Read and write permissions**, puis enregistrer.

### 4. Activer GitHub Pages

Dans :

`Settings > Pages`

- Source : **Deploy from a branch**
- Branch : `main`
- Dossier : `/docs`

Enregistrer.

### 5. Lancer la première mise à jour

Dans l'onglet **Actions** :

1. ouvrir `Mettre à jour la carte des feux` ;
2. cliquer sur `Run workflow` ;
3. choisir la branche `main` ;
4. lancer le workflow.

Le déclenchement manuel force aussi le renouvellement de l'image EFFIS.

### 6. Ouvrir la carte

Adresse attendue :

`https://valldrttle.github.io/tle-carte-feux/`

### 7. Intégrer dans WordPress

Copier le contenu de `wordpress-embed.html` dans un bloc **HTML personnalisé**.

## Planification

Le workflow s'exécute toutes les trois heures :

- FIRMS est actualisé à chaque exécution ;
- EFFIS est actualisé lorsque son image a plus de vingt heures ;
- si une source échoue, son dernier fichier valide est conservé.

## Structure

- `docs/` : site publié par GitHub Pages ;
- `docs/data/` : fichiers générés ;
- `scripts/update_data.py` : récupération et préparation ;
- `.github/workflows/update-data.yml` : automatisation.

## Remarque sur les surfaces brûlées

La première version utilise une image EFFIS précalculée en EPSG:3857, chargée une seule fois. Le rendu reste fluide car le navigateur n'interroge pas le WMS. Une version ultérieure pourra convertir les périmètres en tuiles vectorielles si un niveau de détail supérieur est nécessaire.
