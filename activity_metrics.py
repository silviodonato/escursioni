"""GPS estimates on continuous timestamped segments, using only the standard library."""
import math
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

VERSION = 1
DISTANCES = (1000, 5000, 10000)
MAX_GAP = 120
MAX_SPEED = 55.6  # 200 km/h: reject clear GPS jumps, without assuming a sport.


def hav(a, b):
    p, q = math.radians(a[0]), math.radians(b[0])
    h = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(b[1]-a[1])/2)**2
    return 12742000 * math.asin(math.sqrt(min(1, max(0, h))))


def stamp(value):
    try:
        result = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        if result.tzinfo is None:
            return None  # Never infer the server's timezone for a device clock.
        return result.timestamp()
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None


def iso(value):
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def best_effort(points, distance):
    """Exact minimum on piecewise-linear distance/time, anchored at either endpoint."""
    if len(points) < 2:
        return None
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1]+hav(a, b))
    if lengths[-1] < distance:
        return None
    best = None

    def offer(start, end):
        nonlocal best
        seconds = end-start
        if seconds > 0 and (best is None or seconds < best[0]):
            best = (seconds, start, end)

    # End at a recorded point; choose the latest start when stationary.
    left = 0
    for right in range(1, len(points)):
        target = lengths[right]-distance
        if target < 0:
            continue
        while left+1 < right and lengths[left+1] <= target:
            left += 1
        span = lengths[left+1]-lengths[left]
        if span > 0:
            start = points[left][2]+(points[left+1][2]-points[left][2])*(target-lengths[left])/span
            offer(start, points[right][2])
    # Start at a recorded point; choose the earliest end when stationary.
    right = 1
    for left in range(len(points)-1):
        target = lengths[left]+distance
        if target > lengths[-1]:
            break
        right = max(right, left+1)
        while right < len(points)-1 and lengths[right] < target:
            right += 1
        span = lengths[right]-lengths[right-1]
        if span > 0:
            end = points[right-1][2]+(points[right][2]-points[right-1][2])*(target-lengths[right-1])/span
            offer(points[left][2], end)
    return dict(seconds=round(best[0], 3), start=iso(best[1]), end=iso(best[2])) if best else None


def analyze(text, format):
    quality = dict(invalid_gps=0, missing_time=0, clock_errors=0, gaps=0, gps_jumps=0)
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD non consentito')
    root = ET.fromstring(text.lstrip('\ufeff \r\n\t'))
    for element in root.iter():
        element.tag = element.tag.rsplit('}', 1)[-1]
    tcx = format.upper() == 'TCX'
    tracks = list(root.iter('Track' if tcx else 'trkseg'))
    segments = []
    total = timed = 0
    for track in tracks:
        segment = []
        for point in track.findall('Trackpoint' if tcx else 'trkpt'):
            total += 1
            try:
                lat = float(point.findtext('Position/LatitudeDegrees') if tcx else point.get('lat'))
                lon = float(point.findtext('Position/LongitudeDegrees') if tcx else point.get('lon'))
                if not (math.isfinite(lat) and math.isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180):
                    raise ValueError()
            except (TypeError, ValueError):
                quality['invalid_gps'] += 1
                if segment: segments.append(segment)
                segment = []
                continue
            time = stamp(point.findtext('Time' if tcx else 'time'))
            if time is None:
                quality['missing_time'] += 1
                if segment: segments.append(segment)
                segment = []
                continue
            timed += 1
            current = (lat, lon, time)
            if segment:
                dt = time-segment[-1][2]
                flag = 'clock_errors' if dt <= 0 else 'gaps' if dt > MAX_GAP else 'gps_jumps' if hav(segment[-1], current)/dt > MAX_SPEED else None
                if flag:
                    quality[flag] += 1
                    segments.append(segment)
                    segment = []
            segment.append(current)
        if segment: segments.append(segment)
    efforts = {}
    for distance in DISTANCES:
        candidates = [best_effort(segment, distance) for segment in segments]
        candidates = [candidate for candidate in candidates if candidate]
        if candidates: efforts[str(distance)] = min(candidates, key=lambda e: e['seconds'])
    return dict(_insights_version=VERSION, efforts=efforts, quality=quality,
                timed_points=timed, inspected_points=total)
