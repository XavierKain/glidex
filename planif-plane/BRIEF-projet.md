# Brief projet — Planificateur de plané parapente/parakite

Document de passation pour Claude Code. Objectif : transformer les prototypes HTML existants en un vrai projet maintenable (TypeScript, testé, déployable, offline terrain).

---

## 1. Vision

Un outil de **planification de trajectoire de plané** sur carte, pour parapente et parakite (Flare Moustache / Bandit notamment). L'utilisateur pose un point de départ et un point d'arrivée sur une carte, renseigne le vent et sa voile, et l'outil calcule s'il atteint la cible, avec quelle hauteur au sol, en combien de temps, et affiche l'**empreinte atteignable** (zone où il peut se poser) en tenant compte de la dérive du vent.

Usage réel : sécu de trajectoire à Tarifa (soaring de dune, aller-retour dune ↔ eau, franchissement d'obstacles).

---

## 2. Modèle physique (cœur du projet — à isoler dans un module pur et testé)

### 2.1 Hypothèses
- Vol à **vitesse air constante = vitesse au best glide** `Vx` (m/s). L'angle de plané étant faible, on assimile la vitesse horizontale à `Vx`.
- Taux de chute `Vz = Vx / f` où `f` = finesse air.
- Vent **uniforme et constant** pendant tout le vol.
- Sol supposé **plat à l'altitude d'arrivée** (le relief intermédiaire n'est pas modélisé — voir roadmap).

### 2.2 Modèle « cercle décalé » (offset glide circle)
- En air calme, l'ensemble des points atteignables pour une perte d'altitude `Δh` est un **cercle de rayon `R0 = f·Δh`** centré sur le départ (`R0` = distance parcourue dans l'air).
- Pendant la durée de vol `t = Δh / Vz = R0 / Vx`, le vent translate tout le cercle sous le vent de `d = W·t = R0·(W/Vx) = R0·k`, avec **`k = W/Vx`** (W = force du vent en m/s).
- **Empreinte atteignable** = cercle de rayon `R0` centré au point décalé `C = R0·k·û`, où `û` est le vecteur unitaire **vers lequel souffle le vent**.

### 2.3 Conventions
- Vent saisi en **provenance** (° vrai). Direction vers laquelle il pousse : `toward = (provenance + 180) mod 360`.
- Repère local (Est, Nord) en mètres. `û = (sin(toward), cos(toward))`.
- Cap = bearing (départ → arrivée).
- Borne : `k` plafonné à `0.985`. Si `W ≥ Vx`, pénétration face au vent impossible, le modèle n'est plus borné → à signaler à l'utilisateur.

### 2.4 Résolution « point cible → altitude »
Point cible = vecteur sol `P = (dE, dN)` (mètres Est/Nord depuis le départ). On cherche `R0` tel que `P` soit sur la frontière de l'empreinte :

```
|P - R0·k·û|² = R0²
⇔ R0²(k²-1) - 2·R0·k·(P·û) + |P|² = 0
```

Racine physique (positive) :

```
pu = P·û = dE·ûE + dN·ûN      // projection sur l'axe du vent (+ = sous le vent)
D  = |P|                       // distance sol
R0 = ( √(k²·pu² + (1-k²)·D²) - k·pu ) / (1 - k²)
```

Grandeurs dérivées (indépendantes les unes des autres) :

```
Δh (perte d'altitude) = R0 / f
temps de vol t        = R0 / Vx           // NB : indépendant de f
vitesse sol moyenne   = D / t
finesse sol du leg    = D / Δh
compo. vent sur leg   = (pu / D) · W       // m/s, + = vent arrière
hauteur au sol arrivée = (alt_départ - sol_arrivée) - Δh
```

**Point clé pour la fourchette de finesse** : `R0` ne dépend **que** de la géométrie et de `k`, **pas de `f`**. Donc pour deux finesses `f_best` et `f_plan`, on calcule `R0` une seule fois puis `Δh_i = R0 / f_i`. La borne conservatrice `f_plan` sert au verdict de sécurité.

### 2.5 Empreinte à afficher (hauteur exploitable fixée)
Avec `Δh_dispo = alt_départ - sol_arrivée` :
```
R0_best = f_best · Δh_dispo     // contour = max théorique au best glide
R0_plan = f_plan · Δh_dispo     // surface pleine = atteignable même hors best glide
C_i     = R0_i · k · û          // centre décalé sous le vent
```
Extents utiles : max sous le vent `= R0·(1+k)`, max contre le vent `= R0·(1-k)`, travers `= R0·√(1-k²)`.

### 2.6 Cas de validation (à mettre en test unitaire)
Bandit 16 estimée `f = 8`, `Vx = 44 km/h = 12.22 m/s`, altitude 700 m sol, vent **10 kt = 5.14 m/s** de cul plein axe, cible **500 m** plein sous le vent :

```
k   = 5.14 / 12.22            ≈ 0.4207
pu  = D = 500 (plein downwind)
R0  = D / (1 + k) = 500/1.4207 ≈ 352 m
Δh  = 352 / 8                  ≈ 44 m   → arrivée ≈ 656 m sol
t   = 352 / 12.22             ≈ 28.8 s
Vsol= 500 / 28.8              ≈ 17.4 m/s ≈ 62.5 km/h
```
(Rappel : avec une finesse générique `f=9`, la même cible donnait ≈ 663 m — sert de 2ᵉ cas de test.)

### 2.7 Géodésie (implémentation actuelle, à conserver ou améliorer)
Projection ENU locale plate autour du départ (OK à l'échelle km) :
```
dE = (lon_to - lon_from) · 111320 · cos(lat_from)
dN = (lat_to - lat_from) · 111320
offset(from, dE, dN) → [lat + dN/111320, lon + dE/(111320·cos(lat))]
```
Pour la distance affichée : haversine (via `map.distance` de Leaflet). Bearing : formule standard.

---

## 3. Données voiles

### 3.1 Structure
```js
WINGS = {
  flare_bandit:     { name, note, sizes: { taille: { f, v } } },
  flare_moustache2: { ... },
  flare_moustache:  { ... },
  paraglider_b:     { ... },   // ordre de grandeur
  custom:           { ... }    // valeurs libres
}
// f = finesse air best glide ; v = vitesse best glide (km/h)
```

### 3.2 Tailles officielles (vérifiées sur go-flare.com)
- **Flare Bandit** : 10 / 13 / 16 / 19 / 22. Allongements publiés : 10→6.5, 13→6.8, 16→7, 19→7, 22→7.1.
- **Flare Moustache 2** : 13 / 15 / 18 / 22 / 26.
- **Flare Moustache 1** : tailles **à confirmer** (18 certaine).

### 3.3 ⚠️ Intégrité des données — À LIRE
- Les valeurs `f` et `v` actuelles sont des **ESTIMATIONS**, pas des données constructeur.
- **Flare ne publie aucune polaire chiffrée** : le concept FLARE System permet d'ajuster la finesse à la main (angle d'attaque), donc pas de valeur unique. Les pages produit ont une section « Technical Data » et « Performance Data » **mais uniquement en images** (non extractibles automatiquement).
- Estimations dérivées des allongements publiés + retours pilotes qualitatifs (ex. « Moustache 15 plane comme un parapente de 18/19 », « Bandit : net avantage de glisse sur M2 »).
- **Reco projet** : ajouter à chaque valeur un champ `source` / `confidence` (`estimate` | `measured` | `manufacturer`). Prévoir un flux d'import des vrais chiffres (saisie manuelle depuis les « Performance Data », ou idéalement une **polaire complète** vitesse/taux-de-chute par cran de frein).

### 3.4 Calibration (source de vérité recommandée)
Vol par vent quasi nul : `f_mesurée = distance_parcourue / hauteur_perdue`. Vitesse GPS best glide optionnelle. C'est la donnée la plus fiable pour une voile à finesse pilotable → à mettre en avant dans l'UX et à persister par voile.

---

## 4. Fonctionnalités déjà prototypées (3 fichiers HTML de référence)

1. **`planif-plane.html`** — v1 : calculateur + empreinte schématique (canvas, vue du dessus), rose des vents, anneaux iso-altitude, export KML. Pas de carte.
2. **`planif-plane-carte.html`** — v2 : carte Leaflet (fonds OSM / Esri satellite / OpenTopoMap), clic départ/arrivée, distance & cap auto, marqueurs déplaçables, rose de vent draggable, **altitude sol auto** via open-meteo, base voiles + calibration, export KML.
3. **`planif-plane-pro.html`** — v3 (référence principale) : tailles corrigées, **temps de vol**, **vitesse sol moyenne**, **fourchette de finesse** (best vs planif) avec double empreinte (surface pleine = sûr, contour = max), **marge de sécurité configurable** + verdict ✓/⚠/✕.

Toutes les versions : vanilla HTML/CSS/JS, **aucune clé API**, thème sombre « instrument de vol » (accent ambre `#f2a23d`, vent cyan `#43ccd6`).

---

## 5. Stack technique

### 5.1 Actuelle
- HTML/CSS/JS vanilla + **Leaflet 1.9.4** (CDN).
- Tuiles : OSM, Esri World Imagery (satellite), OpenTopoMap — toutes **sans clé**.
- Élévation : **open-meteo elevation API** (gratuit, CORS, sans clé).
- Export : KML (Blob download), importable dans Google My Maps / Google Earth.

### 5.2 Recommandée pour le vrai projet
- **Vite + TypeScript**. React optionnel (l'UI actuelle tient très bien en vanilla/Web Components).
- Carte : **MapLibre GL** conseillé si on veut du relief 3D (terrain RGB) et du vectoriel ; sinon rester sur Leaflet (plus simple).
- Architecture modulaire :
  - `src/model/glide.ts` — fonctions pures (§2), zéro dépendance UI.
  - `src/data/wings.ts` — données voiles + types (`source`/`confidence`).
  - `src/services/elevation.ts` — abstraction API élévation (open-meteo / open-topo-data, avec cache).
  - `src/ui/` — carte, panneau, rose des vents, export.
- **Tests : Vitest** sur `glide.ts` (reprendre les cas §2.6).
- Persistance : IndexedDB (spots, réglages voiles calibrés).
- **PWA offline** : cache des tuiles et de l'élévation pour usage terrain sans réseau (Tarifa, dune…).
- Déploiement : statique (Vercel / Netlify / GitHub Pages).

---

## 6. Roadmap (priorisée)

1. **Profil de relief sous la trajectoire** ⭐ (sécu clé) — échantillonner N points d'élévation le long du leg, tracer le terrain vs la pente de plané, détecter tout franchissement d'obstacle/crête. Alerte si la trajectoire coupe le relief.
2. **Vraies polaires** — remplacer les estimations ; import des « Performance Data » Flare ; idéalement polaire complète (vitesse ↔ taux de chute) par cran de frein.
3. **Speed-to-fly optimal** (MacCready simplifié) — le modèle actuel suppose une vitesse best glide constante. Optimum réel : accélérer face au vent, ralentir vent de dos. À activer une fois la polaire complète disponible.
4. **Multi-legs / routes** — enchaîner plusieurs branches, cumuler perte d'altitude et temps.
5. **Gradient de vent** — vent différent par tranche d'altitude (souvent plus fort en haut) → dérive plus juste.
6. **Sauvegarde de spots** + réglages voiles calibrés.
7. **Import/export GPX** en plus du KML.
8. **PWA offline** terrain.

---

## 7. Limitations connues (à documenter dans le README)

- Sol plat supposé à l'arrivée ; relief intermédiaire non modélisé (→ roadmap #1).
- Vent uniforme/constant : pas de gradient, pas de thermique ni de dynamique de pente.
- Vol à vitesse best glide constante : pas d'optimisation speed-to-fly (→ roadmap #3).
- Finesses = estimations tant que non calibrées (→ §3.3).
- Projection ENU locale plate : précise à l'échelle km, à revoir pour de très longues distances.
- Modèle non borné si `W ≥ Vx` (vent ≥ vitesse air) : afficher un avertissement.
- Fonctionnalité « altitude sol auto » et tuiles carte nécessitent le réseau (prévoir fallback offline).

---

## 8. Contexte utilisateur

- Pilote basé à Tarifa (Espagne). Voiles : Flare Moustache 18 et Flare Bandit 16 (à calibrer en priorité).
- Spot par défaut du proto : Tarifa `36.0143, -5.6044`.
- Langue : **français**.
- Préférence : outils autonomes, sans clé API, utilisables sur le terrain.
