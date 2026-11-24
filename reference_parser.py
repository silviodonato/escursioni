#!/usr/bin/env python3
"""Genera tracce/index.json con le statistiche di ogni file GPX presente in tracce/.
Uso: python3 genera_indice.py   (da eseguire nella cartella del sito o con percorso assoluto)
Solo libreria standard: funziona con il python3 di DSM."""
import os, re, json, math, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TRACCE = os.path.join(HERE, "tracce")
OUT = os.path.join(TRACCE, "index.json")

def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

def parse(path):
    with open(path, encoding="utf-8", errors="ignore") as source:
        txt = source.read()
    name = ""
    m = re.search(r"<metadata>.*?<name>([^<]*)</name>", txt, re.S) or re.search(r"<trk>.*?<name>([^<]*)</name>", txt, re.S)
    if m: name = m.group(1).strip()
    pts = []
    for m in re.finditer(r'<trkpt\s+lat="([^"]+)"\s+lon="([^"]+)"\s*/?>(.*?)(?:</trkpt>|(?=<trkpt))', txt, re.S):
        body = m.group(3)
        e = re.search(r"<ele>([^<]+)", body); t = re.search(r"<time>([^<]+)", body)
        ts = None
        if t:
            s = t.group(1).strip().replace("Z", "+00:00")
            try: ts = datetime.fromisoformat(s).timestamp()
            except ValueError: ts = None
        pts.append((float(m.group(1)), float(m.group(2)), float(e.group(1)) if e else None, ts))
    if len(pts) < 2: return None
    dist = 0.0
    for i in range(1, len(pts)): dist += hav(pts[i-1], pts[i])
    times = [p[3] for p in pts if p[3] is not None]
    dur = (times[-1] - times[0]) if len(times) >= 2 else None
    eles = [p[2] for p in pts if p[2] is not None]
    gain = loss = 0.0; emax = emin = None
    if len(eles) > 10:
        # stesso filtro "duro" della pagina: mediana + media mobile su ~2 minuti
        dt = max(1.0, (times[-1] - times[0]) / (len(times) - 1)) if len(times) >= 2 else 4.0
        w = max(3, int(round(120 / dt))) | 1; h = w // 2
        med = []
        for i in range(len(eles)):
            win = sorted(eles[max(0, i-h):i+h+1]); med.append(win[len(win)//2])
        sm = []; acc = 0.0; n = len(med)
        for i in range(n):
            a, b = max(0, i-h), min(n, i+h+1)
            sm.append(sum(med[a:b]) / (b - a))
        ref = sm[0]
        for v in sm[1:]:
            d = v - ref
            if d >= 3: gain += d; ref = v
            elif d <= -3: loss -= d; ref = v
        emax, emin = max(eles), min(eles)
    date = datetime.fromtimestamp(times[0], tz=timezone.utc).isoformat() if times else None
    return dict(name=name, date=date, km=round(dist/1000, 2), dur_s=int(dur) if dur else None,
                gain=int(round(gain)), loss=int(round(loss)), ele_max=int(round(emax)) if emax is not None else None,
                ele_min=int(round(emin)) if emin is not None else None, points=len(pts),
                start=[round(pts[0][0], 5), round(pts[0][1], 5)])

def main():
    if not os.path.isdir(TRACCE):
        print("cartella tracce/ non trovata in", HERE); sys.exit(1)
    old = {}
    if os.path.exists(OUT):
        try:
            for e in json.load(open(OUT, encoding="utf-8")): old[e["file"]] = e
        except Exception: old = {}
    out = []
    for f in sorted(os.listdir(TRACCE)):
        if not f.lower().endswith(".gpx"): continue
        p = os.path.join(TRACCE, f); mt = int(os.path.getmtime(p))
        if f in old and old[f].get("mtime") == mt:
            out.append(old[f]); continue
        try:
            st = parse(p)
        except Exception as ex:
            print("errore su", f, ex); st = None
        if not st: continue
        if not st["name"]:
            stem = re.sub(r"\.gpx$", "", f, flags=re.I)
            # un nome di file "parlante" (non un codice tipo Zepp2026...) diventa il nome dell'escursione
            if not re.match(r"^(zepp|track|activity|workout|gpx)?[\d_\-\s().]*$", stem, re.I):
                st["name"] = stem.replace("_", " ")
        st.update(file=f, mtime=mt, size=os.path.getsize(p)); out.append(st)
    out.sort(key=lambda e: e.get("date") or "", reverse=True)
    tmp = OUT + ".tmp"
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print(f"{len(out)} tracce in {OUT}")

if __name__ == "__main__":
    main()
