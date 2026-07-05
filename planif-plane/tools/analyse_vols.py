#!/usr/bin/env python3
"""Extraction de finesse / polaire depuis un backup SoarX (.paraflightlog).

Méthode (cf. docs/derive-polaire-depuis-tracklogs.md) :
1. Par vol : lissage altitude, vitesses sol, cap, Vz.
2. Vent estimé par fit de cercle GPS : |Vg - W|² = Va² linéarisé,
   par fenêtres glissantes si la diversité de caps suffit, sinon sur tout le vol.
3. Vols "corde" (Bandit 16 Xav) : seul l'après-largage est exploité
   (largage = dernier passage au voisinage de l'altitude max, suivi d'une descente).
4. Segments de plané : cap ~constant, Vz < 0 stable, ≥ 12 s, ≥ 6 m perdus.
5. Par segment : Va = |Vg_moy - W|, f = Va / |Vz|.
6. Agrégat par voile : médiane (finesse de planif), p85 (proche best glide),
   vitesse air des meilleurs segments.

Usage : python3 analyse_vols.py <dossier_backup> [--json sortie.json] [--details]
"""
import json, csv, os, sys, math
from collections import defaultdict

D2R = math.pi/180

# ---------- utilitaires ----------
def median(v):
    s = sorted(v); n = len(s)
    return s[n//2] if n % 2 else 0.5*(s[n//2-1]+s[n//2])

def percentile(v, p):
    s = sorted(v)
    if not s: return float('nan')
    k = (len(s)-1)*p/100
    i = int(k)
    return s[i] + (s[min(i+1, len(s)-1)]-s[i])*(k-i)

def median_filter(v, w=5):
    h = w//2
    return [median(v[max(0,i-h):i+h+1]) for i in range(len(v))]

def solve3(A, b):
    """résout le système 3x3 des équations normales (moindres carrés)."""
    M = [[0.0]*3 for _ in range(3)]; r = [0.0]*3
    for row, y in zip(A, b):
        for i in range(3):
            r[i] += row[i]*y
            for j in range(3):
                M[i][j] += row[i]*row[j]
    # élimination de Gauss avec pivot
    for c in range(3):
        p = max(range(c,3), key=lambda k: abs(M[k][c]))
        if abs(M[p][c]) < 1e-9: return None
        M[c], M[p] = M[p], M[c]; r[c], r[p] = r[p], r[c]
        for k in range(c+1,3):
            f = M[k][c]/M[c][c]
            for j in range(c,3): M[k][j] -= f*M[c][j]
            r[k] -= f*r[c]
    x = [0.0]*3
    for c in (2,1,0):
        x[c] = (r[c] - sum(M[c][j]*x[j] for j in range(c+1,3)))/M[c][c]
    return x

def fit_wind(samples, min_n=25, min_bins=6, max_rms=2.8):
    """fit (Wx,Wy,Va) sur [(vx,vy)] : vx²+vy² = 2Wx·vx + 2Wy·vy + c.
    Renvoie (Wx,Wy,Va,rms) ou None si dégénéré / diversité de caps insuffisante."""
    if len(samples) < min_n: return None
    bins = set()
    for vx, vy in samples:
        bins.add(int(((math.atan2(vx, vy)/D2R) % 360)//30))
    if len(bins) < min_bins: return None
    A = [(vx, vy, 1.0) for vx, vy in samples]
    b = [vx*vx+vy*vy for vx, vy in samples]
    s = solve3(A, b)
    if not s: return None
    Wx, Wy, c = s[0]/2, s[1]/2, s[2]
    va2 = c + Wx*Wx + Wy*Wy
    if va2 <= 1: return None
    Va = math.sqrt(va2)
    res = [math.hypot(vx-Wx, vy-Wy) - Va for vx, vy in samples]
    rms = math.sqrt(sum(x*x for x in res)/len(res))
    if rms > max_rms: return None       # fit trop incohérent (vent instable)
    W = math.hypot(Wx, Wy)
    if W > 20 or Va > 24: return None   # aberrant
    return (Wx, Wy, Va, rms)

# ---------- analyse d'un vol ----------
def analyse_flight(pts, is_rope, borrow=None):
    """renvoie (segments, meta). segment = dict(t, dur, va, vz, f, W, gs).
    borrow = [(t,Wx,Wy)] : vents d'autres vols proches, utilisés en dernier recours."""
    pts = sorted(pts, key=lambda p: p['timestamp'])
    # dédoublonnage temporel
    clean = []
    for p in pts:
        if clean and p['timestamp'] - clean[-1]['timestamp'] < 0.5: continue
        clean.append(p)
    pts = clean
    if len(pts) < 30: return [], {'reject': 'trop court'}

    t   = [p['timestamp'] for p in pts]
    lat = [p['latitude'] for p in pts]
    lon = [p['longitude'] for p in pts]
    alt = median_filter([p['altitude'] for p in pts], 5)

    lat0, lon0 = lat[0], lon[0]
    E = [(lo-lon0)*111320*math.cos(lat0*D2R) for lo in lon]
    N = [(la-lat0)*111320 for la in lat]

    n = len(pts)
    vx = [0.0]*n; vy = [0.0]*n; vz = [0.0]*n; spd = [0.0]*n
    for i in range(1, n):
        dt = t[i]-t[i-1]
        if dt <= 0 or dt > 15: continue
        vx[i] = (E[i]-E[i-1])/dt
        vy[i] = (N[i]-N[i-1])/dt
        vz[i] = (alt[i]-alt[i-1])/dt
        spd[i] = math.hypot(vx[i], vy[i])
    vz = median_filter(vz, 5)

    i0 = 0
    i1 = n
    meta = {}
    if is_rope:
        # sessions corde : cycles montée treuillée / descente accroché, répétés.
        # Seule la DESCENTE FINALE (après le dernier sommet > 55 % du max) est libre.
        amax = max(alt)
        if amax < 25: return [], {'reject': 'pas de montée (kiting pur)'}
        thresh = max(30, 0.55*amax)
        last_hi = max(i for i, a in enumerate(alt) if a >= thresh)
        lo = max(0, last_hi-20)
        rel = max(range(lo, last_hi+1), key=lambda i: alt[i])
        i0 = min(rel+2, n-1)             # saute l'abattée du largage
        # fin = retour au sol (alt basse et immobile)
        i1 = n
        for i in range(i0+5, n):
            if alt[i] < 6 and spd[i] < 1.2:
                i1 = i+2; break
        if i1 - i0 < 10: return [], {'reject': 'trop peu de données après largage'}
        meta['release_alt'] = round(alt[rel], 1)
        meta['free_dur'] = round(t[min(i1, n-1)-1]-t[rel], 0)

    # vent : fenêtres glissantes sur la partie exploitée (vol libre pour la corde)
    fly = [i for i in range(max(i0,1), i1) if spd[i] > 1.5]
    # vol libre court (corde) : critères assouplis, les manœuvres fournissent les caps
    kw = dict(min_n=12, min_bins=4, max_rms=3.5) if is_rope else {}
    winds = []   # (t_centre, Wx, Wy)
    WIN, STEP = (40, 15) if is_rope else (90, 30)
    for s in range(0, max(1, len(fly)-WIN//2), STEP):
        idx = fly[s:s+WIN]
        if len(idx) < 12: continue
        w = fit_wind([(vx[i], vy[i]) for i in idx], **kw)
        if w: winds.append(((t[idx[0]]+t[idx[-1]])/2, w[0], w[1]))
    wglob = fit_wind([(vx[i], vy[i]) for i in fly], **kw)
    if wglob: meta['wind_global'] = (round(math.hypot(wglob[0], wglob[1]),1),
                                     round(wglob[2],1), round(wglob[3],1))  # (W, Va, rms)
    if not winds and not wglob and not borrow:
        return [], {'reject': 'vent non estimable (caps trop peu variés)', **meta}
    if not winds and not wglob: meta['wind_borrowed'] = True

    def wind_at(tt):
        if winds:
            best = min(winds, key=lambda w: abs(w[0]-tt))
            if abs(best[0]-tt) < 600: return best[1], best[2]
        if wglob: return wglob[0], wglob[1]
        if borrow:
            best = min(borrow, key=lambda w: abs(w[0]-tt))
            if abs(best[0]-tt) < 5400: return best[1], best[2]   # ≤ 90 min d'écart
        return None

    # segments de plané : droit, descendant, stable
    # (corde : vol libre court → micro-segments admis, le bruit GPS se moyenne
    #  dans l'estimateur poolé Σdist/Σalt)
    max_rate = 12.0 if is_rope else 8.0
    min_dur, min_dh = (6, 4) if is_rope else (9, 5)
    segs = []
    i = max(i0, 1)
    while i < i1-1:
        j = i
        while j+1 < i1:
            dt = t[j+1]-t[j]
            if dt <= 0 or dt > 8: break
            if spd[j+1] < 1.5: break
            dh = (math.atan2(vx[j+1], vy[j+1]) - math.atan2(vx[j], vy[j]))/D2R
            dh = (dh+180) % 360 - 180
            if abs(dh) > max_rate*dt: break          # vire trop
            if not (-3.0 < vz[j+1] < -0.05): break   # hors domaine de plané
            j += 1
        dur = t[j]-t[i]
        if dur >= min_dur and (alt[i]-alt[j]) >= min_dh:
            w = wind_at((t[i]+t[j])/2)
            if w:
                mvx = (E[j]-E[i])/dur; mvy = (N[j]-N[i])/dur
                vax, vay = mvx-w[0], mvy-w[1]
                va = math.hypot(vax, vay)
                mvz = (alt[j]-alt[i])/dur
                if 3.5 < va < 22 and -3.0 < mvz < -0.15:
                    f = va/(-mvz)
                    if 1 < f < 16:
                        segs.append({'t': t[i], 'dur': dur, 'va': va, 'vz': -mvz,
                                     'f': f, 'W': math.hypot(w[0], w[1]),
                                     'gs': math.hypot(mvx, mvy), 'dh': alt[i]-alt[j]})
        i = j+1 if j > i else i+1
    meta['n_seg'] = len(segs)
    meta['_winds'] = winds if winds else ([(t[0], wglob[0], wglob[1])] if wglob else [])
    return segs, meta

# ---------- main ----------
def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    out_json = None
    details = '--details' in sys.argv
    if '--json' in sys.argv: out_json = sys.argv[sys.argv.index('--json')+1]

    wings = {}
    with open(os.path.join(root, 'wings.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            wings[r['ID']] = (r['Nom'], r['Taille'])

    flights = []
    with open(os.path.join(root, 'flights.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            flights.append(r)

    # passe 1 : analyse + collecte des vents estimés
    per_wing = defaultdict(list)
    logs = []
    all_winds = []
    retry = []
    for r in flights:
        p = os.path.join(root, 'gps', r['ID']+'.json')
        if not os.path.exists(p): continue
        pts = json.load(open(p))
        if len(pts) < 50: continue
        wname, wsize = wings.get(r['Voile ID'], (r['Voile Nom'], '?'))
        is_rope = 'Xav' in wname            # vols corde = Bandit 16 Xav
        segs, meta = analyse_flight(pts, is_rope)
        all_winds.extend(meta.pop('_winds', []))
        key = f'{wname} {wsize}'
        if meta.get('reject', '').startswith('vent'):
            retry.append((r, pts, is_rope, key))
        per_wing[key].extend(segs)
        logs.append((key, r['Date début'], r['Spot'], len(pts), meta))
    # passe 2 : vols sans vent → vent emprunté à un vol proche dans le temps
    for r, pts, is_rope, key in retry:
        segs, meta = analyse_flight(pts, is_rope, borrow=all_winds)
        meta.pop('_winds', None)
        if segs:
            per_wing[key].extend(segs)
            logs.append((key, r['Date début']+' (vent emprunté)', r['Spot'], len(pts), meta))

    if details:
        for k, d, spot, np_, meta in sorted(logs):
            print(f'{k:26s} {d} {spot[:18]:18s} {np_:5d} pts  {meta}')
        print()

    result = {}
    print(f'{"Voile":26s} {"segs":>4s} {"f pool":>6s} {"f méd":>6s} {"f p80":>6s} '
          f'{"Va méd":>7s} {"Va p80f":>8s} {"Δh tot":>7s} {"vent méd":>8s}')
    for k in sorted(per_wing, key=lambda k: -len(per_wing[k])):
        segs = per_wing[k]
        if len(segs) < 3:
            print(f'{k:26s} {len(segs):4d}   (trop peu de segments)')
            continue
        fs = [s['f'] for s in segs]
        # estimateur le plus robuste au bruit GPS : distances/altitudes cumulées
        f_pool = sum(s['va']*s['dur'] for s in segs)/sum(s['dh'] for s in segs)
        f_med, f_p80 = median(fs), percentile(fs, 80)
        top = sorted(segs, key=lambda s: -s['f'])[:max(3, len(segs)//4)]
        va_best = median([s['va'] for s in top])*3.6
        va_med = median([s['va'] for s in segs])*3.6
        dh_tot = sum(s['dh'] for s in segs)
        w_med = median([s['W'] for s in segs])/0.514444
        print(f'{k:26s} {len(segs):4d} {f_pool:6.1f} {f_med:6.1f} {f_p80:6.1f} '
              f'{va_med:7.1f} {va_best:8.1f} {dh_tot:7.0f} {w_med:8.1f}')
        result[k] = {'n_segments': len(segs), 'f_pooled': round(f_pool,2),
                     'f_median': round(f_med,2), 'f_p80': round(f_p80,2),
                     'va_median_kmh': round(va_med,1), 'va_bestf_kmh': round(va_best,1),
                     'alt_perdue_totale_m': round(dh_tot),
                     'wind_median_kt': round(w_med,1),
                     'source': 'measured-gps', 'note': 'Vz GPS (pas de baro) ; '
                     'segments en soaring possiblement influencés par l ascendance'}
    # export CSV des segments pour inspection
    seg_csv = os.path.join(os.path.dirname(out_json) if out_json else '.', 'segments.csv')
    with open(seg_csv, 'w', newline='') as f:
        wcsv = csv.writer(f)
        wcsv.writerow(['voile','dur_s','va_ms','vz_ms','finesse','gs_ms','dh_m','vent_ms'])
        for k, segs in per_wing.items():
            for s in segs:
                wcsv.writerow([k, round(s['dur'],1), round(s['va'],2), round(s['vz'],2),
                               round(s['f'],2), round(s['gs'],2), round(s['dh'],1), round(s['W'],2)])
    print(f'→ segments : {seg_csv}')
    if out_json:
        json.dump(result, open(out_json, 'w'), indent=2, ensure_ascii=False)
        print(f'\n→ {out_json}')

if __name__ == '__main__':
    main()
