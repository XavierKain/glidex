# Backlog GlideX

Idées identifiées mais non implémentées, à reprendre plus tard.

---

## 1. Empreinte inondée sur le relief, décalée par le vent (« hikeandfly + vent »)

**Priorité :** à décider — c'est le seul vrai manque de GlideX face à hikeandfly.org.
**Statut :** backlog (2026-07-13).

### Le manque
Aujourd'hui, l'empreinte atteignable de GlideX est un **cercle décalé « sol plat »**, et le
relief n'est vérifié **que sous la route tracée** (profil de terrain + alerte de collision).

hikeandfly.org, lui, **peint toute la zone réellement atteignable** en croisant le cône de
plané avec le modèle numérique de terrain (grille ~200 m, rayon ~20 km, couverture mondiale).
Mais hikeandfly assume explicitement l'**air statique** — pas de vent.

### L'idée
Reproduire le flood-fill sur relief de hikeandfly, **mais en gardant l'avantage unique de
GlideX** : un **cône de plané décalé par la dérive du vent**, croisé avec le DEM (open-meteo).

Résultat = littéralement **« hikeandfly + vent »**, que ni hikeandfly ni le Party Till Impact
Line Planner ne proposent.

### Pistes techniques
- Réutiliser le modèle de dérive de vent et la composante de vent par leg déjà en place.
- Croiser le cône de plané (best finesse / finesse planif) avec le DEM open-meteo par échantillonnage
  sur une grille (viser ~200 m comme hikeandfly, rayon ~20 km).
- Rendu : peindre la zone atteignable sur la carte Leaflet (fond Esri déjà utilisé).
- Conserver le verdict de marge de sécurité et la fourchette de finesse dans l'affichage.

---

## 2. Reco de voile inversée et enrichie par les polaires mesurées

**Priorité :** secondaire.
**Statut :** backlog (2026-07-13).

### L'idée
Le Party Till Impact Line Planner fait « voici la **voile** pour cette **ligne** » (calé sur les
voiles Flare). Inverser la question et l'enrichir avec les données propres de GlideX :

> **« Avec ma Bandit 16, quelles lignes / cibles passent ? »**

La base de voiles et les **finesses mesurées sur les vrais vols GPS (tracklogs SoarX)** existent
déjà pour alimenter ça — c'est l'atout que ni hikeandfly ni le Line Planner n'ont.

---

## Contexte / positionnement (rappel)

Les trois outils ne se marchent pas dessus :
- **hikeandfly.org** = rayon d'action global **sans vent**.
- **Party Till Impact Line Planner** = feasibility de lignes speedfly + reco voile **Flare**.
- **GlideX** = planif de trajectoire fine **avec vent** + marge de sécurité chiffrée + **polaires
  réelles** (tracklogs). C'est le créneau occupé seul par GlideX.
