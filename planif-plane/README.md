# Planif Plané — dossier projet

Planificateur de trajectoire de plané (parapente / parakite) sur carte, avec dérive du vent, fourchette de finesse et marge de sécurité. Ce dossier contient tout pour démarrer un vrai projet avec Claude Code.

## Contenu

```
planif-plane/
├── README.md                             ← tu es ici
├── BRIEF-projet.md                       ← spec complète : modèle physique, données, stack, roadmap, limites
├── prototypes/
│   ├── planif-plane.html                 v1 — calculateur + empreinte (canvas), export KML
│   ├── planif-plane-carte.html           v2 — carte Leaflet, clic départ/arrivée, altitude sol auto
│   └── planif-plane-pro.html             v3 — RÉFÉRENCE : temps de vol, fourchette de finesse, marge sécu
├── docs/
│   └── derive-polaire-depuis-tracklogs.md  ← comment tirer la finesse réelle de tes anciens vols
└── data/
    └── wings.json                        base voiles (tailles officielles + finesses ESTIMÉES à remplacer)
```

## Ordre de lecture pour Claude Code

1. `BRIEF-projet.md` — le modèle physique (§2) est le cœur, avec des cas de validation chiffrés à transformer en tests.
2. `prototypes/planif-plane-pro.html` — implémentation de référence du modèle et de l'UI.
3. `docs/derive-polaire-depuis-tracklogs.md` — pour remplacer les finesses estimées par des vraies, extraites des tracklogs.
4. `data/wings.json` — données prêtes à importer (toutes marquées `source: "estimate"`).

## Prompt de démarrage suggéré

> Lis `BRIEF-projet.md`. Initialise un projet **Vite + TypeScript**. Extrais le modèle de plané dans `src/model/glide.ts` (fonctions pures) et écris les tests **Vitest** à partir des cas de validation §2.6. Charge `data/wings.json` dans `src/data/wings.ts` avec des types incluant `source`/`confidence`. Puis recâble la carte de `prototypes/planif-plane-pro.html` sur ce modèle (Leaflet, fonds sans clé). Ensuite, implémente l'import de tracklogs et l'extraction de polaire décrits dans `docs/derive-polaire-depuis-tracklogs.md`.

## ⚠️ Deux points d'intégrité

- **Les finesses sont des estimations** (Flare ne publie pas de polaire chiffrée). Priorité n°1 : les remplacer via les tracklogs (voir `docs/`) ou les « Performance Data » constructeur.
- **Le relief intermédiaire n'est pas modélisé** — première vraie feature sécu de la roadmap.

## Stack & contraintes

Aucune clé API requise. Tuiles OSM / Esri / OpenTopoMap et élévation open-meteo sont gratuites et sans clé. Cible : utilisable **hors-ligne sur le terrain** (PWA + cache tuiles) à terme. Langue : français.
