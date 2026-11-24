#!/usr/bin/env python3
"""Genera tracce/index.json con le statistiche di ogni file GPX presente in tracce/.
Uso: python3 genera_indice.py   (da eseguire nella cartella del sito o con percorso assoluto)
Solo libreria standard: funziona con il python3 di DSM."""
import os, re, json, math, sys, hashlib, argparse, stat, subprocess, time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from activity_store import decorate
import activity_metrics

from activity_config import SITE
HERE = str(SITE)
TRACCE = os.path.join(HERE, "tracce")
OUT = os.path.join(TRACCE, "index.json")

def simplify_route(coordinates, tolerance=20.0):
    if len(coordinates) <= 2:
        return [[round(a,5),round(b,5)] for a,b in coordinates]
    scale=math.cos(math.radians(sum(a for a,b in coordinates)/len(coordinates)))
    origin=coordinates[0]
    xy=[((b-origin[1])*111195*scale,(a-origin[0])*111195) for a,b in coordinates]
    keep={0,len(xy)-1};pending=[(0,len(xy)-1)];limit=tolerance*tolerance
    while pending:
        first,last=pending.pop();ax,ay=xy[first];bx,by=xy[last];dx,dy=bx-ax,by-ay
        norm=dx*dx+dy*dy;furthest=limit;chosen=None
        for i in range(first+1,last):
            x,y=xy[i];fraction=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/norm)) if norm else 0
            distance=(x-ax-fraction*dx)**2+(y-ay-fraction*dy)**2
            if distance>furthest:furthest=distance;chosen=i
        if chosen is not None:
            keep.add(chosen);pending.extend(((first,chosen),(chosen,last)))
    return [[round(coordinates[i][0],5),round(coordinates[i][1],5)] for i in sorted(keep)]

def route_metadata(segments):
    points=[p for segment in segments for p in segment]
    return dict(routes=[simplify_route(s) for s in segments if s],
                bounds=[min(p[0] for p in points),min(p[1] for p in points),
                        max(p[0] for p in points),max(p[1] for p in points)] if points else None,
                has_gps=len(points)>=2,route_tolerance_m=21)

def tcx_data(text):
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD non consentito nei file TCX')
    root=ET.fromstring(text.lstrip('\ufeff \r\n\t'))
    # Normalize names once, then use ElementTree's direct child lookups.
    for element in root.iter():
        element.tag=element.tag.rsplit('}',1)[-1]
    def child(element,tag):
        return element.findtext(tag)
    def number(value):
        try:
            value=float(value)
            return value if math.isfinite(value) else None
        except (TypeError,ValueError):return None
    def stamp(value):
        try:return datetime.fromisoformat(value.strip().replace('Z','+00:00')).timestamp()
        except (ValueError,AttributeError):return None
    activities=list(root.iter('Activity')) or list(root.iter('Course'))
    activity=activities[0] if activities else root
    sport=activity.get('Sport','Other')
    label={'hike':'Escursione','running':'Corsa','biking':'Ciclismo','swimming':'Nuoto','walking':'Camminata'}.get(sport.lower(),'Attività')
    name=(child(activity,'Name') or child(activity,'Notes') or label).strip()[:200]
    start=stamp(child(activity,'Id'));segments=[];points=[]
    for track in root.iter('Track'):
        segment=[]
        for point in track.findall('Trackpoint'):
            position=point.find('Position')
            if position is None:continue
            latitude=number(child(position,'LatitudeDegrees'));longitude=number(child(position,'LongitudeDegrees'))
            if latitude is None or longitude is None or not (-90<=latitude<=90 and -180<=longitude<=180):continue
            points.append((latitude,longitude,number(child(point,'AltitudeMeters')),stamp(child(point,'Time'))))
            segment.append((latitude,longitude))
        if segment:segments.append(segment)
    laps=list(root.iter('Lap'))
    distance=sum(number(child(e,'DistanceMeters')) or 0 for e in laps)
    duration=sum(number(child(e,'TotalTimeSeconds')) or 0 for e in laps)
    return name,points,segments,dict(sport=sport,date=datetime.fromtimestamp(start,tz=timezone.utc).isoformat() if start is not None else None,
                                  km=round(distance/1000,2),dur_s=int(duration) if duration else None)

def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

def parse(path, txt=None):
    if txt is None:
        with open(path, encoding="utf-8", errors="ignore") as source:
            txt = source.read()
    is_tcx=path.lower().endswith('.tcx');extra={}
    if is_tcx:
        name,pts,segments,extra=tcx_data(txt)
    else:
        name,pts,segments=gpx_data(txt)
    geometry=route_metadata(segments)
    if len(pts)<2:
        if not is_tcx:return None
        return dict(name=name,date=extra['date'],km=extra['km'],dur_s=extra['dur_s'],gain=0,loss=0,
                    ele_max=None,ele_min=None,points=len(pts),start=list(pts[0][:2]) if pts else None,
                    sport=extra['sport'],format='TCX',**geometry)
    dist = 0.0
    for i in range(1, len(pts)): dist += hav(pts[i-1], pts[i])
    times = [p[3] for p in pts if p[3] is not None]
    dur = (times[-1] - times[0]) if len(times) >= 2 else None
    eles = [p[2] for p in pts if p[2] is not None]
    gain = loss = 0.0; emax = emin = None
    if len(eles) > 10:
        dt = max(1.0, (times[-1] - times[0]) / (len(times) - 1)) if len(times) >= 2 else 4.0
        w = max(3, int(round(120 / dt))) | 1; h = w // 2
        med = []
        for i in range(len(eles)):
            win = sorted(eles[max(0, i-h):i+h+1]); med.append(win[len(win)//2])
        sm = []; n = len(med)
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
    return dict(name=name, date=extra.get('date') or date, km=round(dist/1000, 2), dur_s=int(dur) if dur else extra.get('dur_s'),
                gain=int(round(gain)), loss=int(round(loss)), ele_max=int(round(emax)) if emax is not None else None,
                ele_min=int(round(emin)) if emin is not None else None, points=len(pts),
                start=[round(pts[0][0], 5), round(pts[0][1], 5)],format='TCX' if is_tcx else 'GPX',
                sport=extra.get('sport'),**geometry)

def gpx_data(txt):
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
    segments=[]
    for section in re.split(r'</trkseg\s*>',txt,flags=re.I):
        coords=[(float(a),float(b)) for a,b in re.findall(r'<trkpt\s+lat="([^"]+)"\s+lon="([^"]+)"',section)]
        if coords:segments.append(coords)
    return name,pts,segments

# Increase this when changing the track-statistics algorithm.
CACHE_VERSION = 2


def metadata(info):
    return dict(mtime=int(info.st_mtime), mtime_ns=info.st_mtime_ns,
                ctime_ns=info.st_ctime_ns, size=info.st_size)


def read_snapshot(path):
    """Read a stable snapshot; do not cache a GPX while it is being uploaded."""
    for attempt in range(2):
        with open(path, 'rb') as source:
            before = os.fstat(source.fileno())
            raw = source.read()
            after = os.fstat(source.fileno())
        current = os.stat(path)
        if (metadata(before) == metadata(after) == metadata(current)
                and (after.st_dev, after.st_ino) == (current.st_dev, current.st_ino)
                and len(raw) == after.st_size):
            return raw, after
    raise OSError('file ancora in modifica; riprova al prossimo aggiornamento')


def prepare_web_temporary(path):
    # Only the fixed temporary index gets a writable ACL on Synology.
    fd = os.open(path, os.O_CREAT | os.O_RDONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r') as handle:
        info = os.fstat(handle.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PermissionError('Unsafe temporary index file')
    subprocess.run(['/usr/syno/bin/synoacltool', '-add', path,
                    'user:http:allow:rw--d--------:----'],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=5, check=True)


def write_index(entries, web_acl=False):
    temporary = OUT + '.tmp'
    if web_acl:
        prepare_web_temporary(temporary)
    with open(temporary, 'w', encoding='utf-8') as output:
        json.dump(entries, output, ensure_ascii=False, separators=(',', ':'))
    os.replace(temporary, OUT)


def main(web_acl=False, max_files=None, max_seconds=None):
    if not os.path.isdir(TRACCE):
        raise FileNotFoundError('cartella tracce/ non trovata in ' + HERE)
    previous = None
    try:
        with open(OUT, encoding='utf-8') as source:
            previous = json.load(source)
        if not isinstance(previous, list) or not all(
                isinstance(entry, dict) and isinstance(entry.get('file'), str)
                for entry in previous):
            previous = None
    except (OSError, ValueError):
        pass
    old = {entry['file']: entry for entry in (previous or [])}
    names=os.listdir(TRACCE)
    gpx_stems={os.path.splitext(n)[0].casefold() for n in names if n.lower().endswith('.gpx')}
    files=sorted(n for n in names if n.lower().endswith('.gpx') or
                 (n.lower().endswith('.tcx') and os.path.splitext(n)[0].casefold() not in gpx_stems))
    out = []
    processed = reused = errors = pending = examined = 0
    started = time.monotonic()
    for name in files:
        path = os.path.join(TRACCE, name)
        cached = old.get(name)
        valid_cache = cached is not None and cached.get('_cache_version') == CACHE_VERSION
        try:
            current = os.stat(path)
            if (valid_cache and cached.get('_insights_version') == activity_metrics.VERSION
                    and all(cached.get(key) == value for key, value in metadata(current).items())):
                out.append(cached)
                reused += 1
                continue
            if ((max_files is not None and examined >= max_files)
                    or (max_seconds is not None and time.monotonic()-started >= max_seconds)):
                pending += 1
                if cached:
                    out.append(cached)
                continue
            examined += 1
            raw, current = read_snapshot(path)
            digest = hashlib.sha256(raw).hexdigest()
            if valid_cache and cached.get('sha256') == digest:
                entry = dict(cached)
                reused += 1
            elif (cached and cached.get('_cache_version') == 1
                  and name.lower().endswith('.gpx') and cached.get('sha256') == digest):
                # Version 2 adds route geometry; the version 1 GPX statistics are unchanged.
                _, _, segments = gpx_data(raw.decode('utf-8', errors='ignore'))
                entry = dict(cached)
                entry.update(route_metadata(segments))
                entry.update(format='GPX', sport=None)
                reused += 1
            else:
                entry = parse(path, raw.decode('utf-8', errors='ignore'))
                if not entry:
                    raise ValueError('GPX senza almeno due punti validi')
                processed += 1
                if not entry['name']:
                    stem = re.sub(r'\.(gpx|tcx)$', '', name, flags=re.I)
                    if not re.match(r'^(zepp|track|activity|workout|gpx)?[\d_\-\s().]*$', stem, re.I):
                        entry['name'] = stem.replace('_', ' ')
            if entry.get('_insights_version') != activity_metrics.VERSION:
                try:
                    entry.update(activity_metrics.analyze(raw.decode('utf-8', errors='ignore'), entry.get('format', 'GPX')))
                except (ET.ParseError, ValueError, OverflowError) as error:
                    # Cache the failed inspection too; retry only if the source or algorithm changes.
                    entry.update(_insights_version=activity_metrics.VERSION, efforts={},
                                 quality={'xml_error': 1}, timed_points=0, inspected_points=0)
                    errors += 1
                    print('approfondimenti non disponibili per {}: {}'.format(name,error),file=sys.stderr)
            entry.update(metadata(current))
            entry.update(file=name, sha256=digest, _cache_version=CACHE_VERSION)
            out.append(entry)
        except (OSError, ValueError, OverflowError, ET.ParseError) as error:
            errors += 1
            print('errore su {}: {}'.format(name, error), file=sys.stderr)
            # Preserve an existing valid result during a failed/incomplete upload.
            if cached:
                out.append(cached)
    out = [dict(entry) for entry in out]
    decorate(out)
    out.sort(key=lambda entry: entry.get('date') or '', reverse=True)
    written = previous != out
    if written:
        write_index(out, web_acl=web_acl)
    return dict(count=len(out), processed=processed, reused=reused,
                removed=len(set(old) - set(files)), errors=errors, written=written,
                pending=pending)


if __name__ == '__main__':
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('--json', action='store_true', help='riepilogo per il pulsante web')
    arguments.add_argument('--web-acl', action='store_true', help='permessi del file temporaneo su DSM')
    arguments.add_argument('--max-files', type=int, help='massimo di file nuovi/modificati per lotto')
    arguments.add_argument('--max-seconds', type=float, help='tempo di lavoro prima di salvare un lotto')
    args = arguments.parse_args()
    if ((args.max_files is not None and args.max_files < 1)
            or (args.max_seconds is not None and args.max_seconds <= 0)):
        arguments.error('i limiti devono essere positivi')
    result = main(web_acl=args.web_acl, max_files=args.max_files, max_seconds=args.max_seconds)
    if args.json:
        print(json.dumps(result, separators=(',', ':')))
    else:
        state = 'indice aggiornato' if result['written'] else 'nessuna modifica'
        print('{} tracce in {} — {} elaborate, {} riutilizzate, {} rimosse; {}'.format(
            result['count'], OUT, result['processed'], result['reused'], result['removed'], state))
        if result['pending']:
            print('{} file ancora da elaborare; il prossimo lotto riparte dalla cache.'.format(result['pending']))

