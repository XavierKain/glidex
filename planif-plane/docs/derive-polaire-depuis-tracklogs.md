# Dériver ta finesse / polaire depuis tes anciens vols (tracklogs)

Réponse à : « j'ai tous mes anciens vols dans mon app (SoarX). On peut s'en servir pour calibrer ? »

**Oui.** Un tracklog (série temporelle position + altitude) contient tout ce qu'il faut pour extraire empiriquement ta finesse et ta vitesse au best glide — c'est la méthode standard pour construire une polaire à partir de vols réels. Ça remplace avantageusement un vol de calibrage dédié : la donnée existe déjà.

---

## Entrée nécessaire

- Échantillons `{ t, lat, lon, alt }`, idéalement ≥ 1 Hz.
- Formats supportés à prévoir : **GPX**, **IGC** (format vol libre, contient l'altitude baro + GPS), ou **CSV** `t,lat,lon,alt`.
- Comme SoarX est ton app, le prérequis n°0 est un **export** dans un de ces formats. Si le stockage est propriétaire, ajouter un exporteur GPX/IGC est la première tâche.
- Bonus si déjà présents : vitesse sol, cap, altitude baro (préférable au GPS).

---

## Le piège central : finesse SOL ≠ finesse AIR

Le GPS mesure ta trajectoire par rapport au **sol** → tu obtiens la **finesse sol**, polluée par le vent. Le modèle de l'outil a besoin de la **finesse air**. Il faut donc estimer le vent et le retirer.

---

## Algorithme (module `polar-from-track`)

### 1. Parsing + nettoyage
- Lire le tracklog → tableau de samples.
- Lisser l'altitude (filtre médian court puis passe-bas) : le baro/GPS est bruité.
- Dériver par pas : vitesse sol vectorielle `Vg`, taux vertical `Vz = dAlt/dt`, cap.

### 2. Segmentation — isoler les planés stabilisés
Garder uniquement les segments exploitables :
- **Rejeter** : virages (variation de cap importante), montées (`Vz > 0` : thermique / dynamique de pente), phases sol / décollage / atterrissage, à-coups de frein.
- **Garder** : cap ~constant, `Vz` stable et négatif (chute régulière), durée ≥ ~10–15 s.

### 3. Estimation du vent
- **Méthode « cercle GPS »** (la plus fiable) : sur un 360 — ou en agrégeant des segments droits volés dans des directions variées — la vitesse sol tracée en fonction du cap décrit un **cercle décentré**. Le décalage du centre = **vecteur vent** ; le rayon = **vitesse air**. Fit moindres carrés.
- Sans 360 : résoudre conjointement (vent + vitesse air) sur plusieurs segments droits de caps différents, sous l'hypothèse d'une vitesse air ~constante au best glide.
- Repli : utiliser les segments où le vent météo est connu et faible.

### 4. Passage sol → air
Pour chaque sample de plané : `Va = Vg − W` (soustraction vectorielle).
Point de polaire = `( |Va_horizontal| , Vz )`.

### 5. Extraction des paramètres
- Nuage (vitesse air, taux de chute) → **enveloppe supérieure**.
- **Finesse best glide** `f_best = max( Va_h / |Vz| )` ; **vitesse best glide** = la `Va_h` correspondante.
- **Min-sink** = point de `|Vz|` minimal.
- Pour un **parakite** (finesse pilotée à la main via le FLARE System), la polaire est un **nuage large** : prendre l'enveloppe comme `f_best`, et un percentile plus bas (ex. médiane des planés) comme `f_plan` conservatrice. → alimente directement la **fourchette** de l'outil (finesse best vs planif).

### 6. Sortie
Par voile : `{ f_best, f_plan, v_best, min_sink, n_segments, confidence, source: "measured" }`.
Injecter dans `wings.ts` / la persistance, en écrasant les estimations.

---

## Version pragmatique (quick win)

Sans reconstruire toute la polaire : repérer dans un vol **un long plané droit par vent faible connu**, prendre la distance sol parcourue et la hauteur perdue, corriger du vent :
```
distance_air ≈ distance_sol − W · t · cos(angle_entre_cap_et_vent)
f_air ≈ distance_air / Δh
```
Un seul bon segment par voile donne déjà un `f_best` crédible pour démarrer.

---

## Limites / honnêteté

- **Qualité capteur** : l'altitude GPS est bruitée — privilégier le baro (IGC). Incertitude de ±0,5 à 1 point de finesse est normale.
- **Vent non uniforme** : l'estimation vaut pour la tranche d'altitude et l'instant du segment ; il varie dans le temps et avec l'altitude.
- **Parakite** : tu mesures ce que **toi** tu fais de la voile, pas une constante intrinsèque. C'est exactement ce qu'on veut pour la planif de trajectoire.
- **Export** : tout dépend de la capacité de SoarX à sortir les données. Format propriétaire → écrire un exporteur d'abord.

---

## Ce dont Claude Code a besoin de toi

1. **Un fichier d'exemple** exporté d'un vrai vol (GPX / IGC / CSV) → pour caler le parseur sur le format réel.
2. Idéalement **2–3 vols par voile**, avec des caps variés (indispensable pour une bonne estimation du vent).

Avec ça, l'extraction de polaire remplace les finesses estimées par tes vraies valeurs, par voile et par taille.
