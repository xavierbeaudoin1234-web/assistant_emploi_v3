#!/usr/bin/env python3
# Improved update_jobs.py
# Reads RSS feeds from JOB_ALERT_FEEDS (one URL per line), normalizes entries,
# checks links server-side, attempts geocoding to compute distance to Drummondville,
# and writes jobs.json only when changed.

import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    import feedparser
    import requests
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
except Exception as e:
    raise SystemExit("Missing dependency: {}. Please install requirements.txt".format(e))

OUT = "jobs.json"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "geocode_cache.json")
FEEDS = [x.strip() for x in os.environ.get("JOB_ALERT_FEEDS", "").splitlines() if x.strip()]
USER_AGENT = os.environ.get("GEOCODER_USER_AGENT") or "assistant-emploi-v3 (https://github.com/xavierbeaudoin1234-web)"

# Drummondville approx center (lat, lon)
DRUMMONDVILLE_COORD = (45.8889, -72.4889)
MAX_DISTANCE_KM = 20

# Keywords for categories and location hints
CATEGORY_KEYWORDS = {
    "Entrepôt": ["entrepôt", "warehouse", "inventaire", "réception", "expédition", "manutention", "commis d'entrepôt", "préparateur de commandes", "stock"],
    "Commerce et vente": ["vente", "vendeur", "conseiller", "commis de plancher", "commerce", "magasin", "retail", "sales", "cellulaire"],
    "Informatique et électronique": ["informatique", "technicien", "support technique", "électronique", "ordinateur", "technologie", "téléphone", "zebra"],
    "Service à la clientèle": ["service à la clientèle", "clientèle", "customer service", "accueil", "centre d'appel", "conseiller service", "réceptionniste"],
    "Administratif": ["administratif", "saisie", "bureautique", "secrétaire", "administration", "assistant administratif"]
}

LOCATION_TERMS = [
    "drummondville", "saint-nicéphore", "wickham", "saint-cyrille", "saint-germain-de-grantham",
    "saint-majorique", "saint-joachim-de-courval", "saint-bonaventure", "victoriaville", "rocheston"
]

SALARY_RE = re.compile(r"(?:\$\s?)(\d{1,3}(?:[.,]\d{1,2})?)|(?:(\d{1,3}(?:[.,]\d{1,2})?)\s?\$)", re.I)

REQUESTS_TIMEOUT = 10.0


def save_json_if_changed(path, data):
    new = json.dumps(data, ensure_ascii=False, indent=2)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        if old.strip() == new.strip():
            print("No changes to {}".format(path))
            return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Wrote {len(data.get('jobs', []))} job(s) to {path}")
    return True


def clean_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (s or "")).strip())


def classify(text):
    t = (text or "").lower()
    best, count = "Service à la clientèle", 0
    for cat, words in CATEGORY_KEYWORDS.items():
        n = sum(1 for w in words if w in t)
        if n > count:
            best, count = cat, n
    return best


def parse_salary(text):
    if not text:
        return None
    for m in SALARY_RE.finditer(text):
        raw = next((g for g in m.groups() if g), None)
        if raw:
            try:
                n = float(raw.replace(",", "."))
                if 8 <= n <= 200:
                    return n
            except Exception:
                pass
    return None


def normalize_url(u):
    if not u:
        return ''
    try:
        p = urlparse(u)
        scheme = p.scheme or 'http'
        netloc = p.netloc.lower()
        path = p.path.rstrip('/')
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return u


def load_cache(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('Unable to write cache:', e)


def geocode_location(geolocator, cache, place):
    key = place.strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]
    try:
        time.sleep(1.0)  # be polite with Nominatim
        loc = geolocator.geocode(key, addressdetails=False, exactly_one=True, timeout=10)
        if loc:
            val = (loc.latitude, loc.longitude)
            cache[key] = val
            return val
    except Exception as e:
        print('Geocode error for', key, e)
    cache[key] = None
    return None


def check_url(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=REQUESTS_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.status_code >= 400:
            # try GET as fallback
            r = requests.get(url, allow_redirects=True, timeout=REQUESTS_TIMEOUT, headers={"User-Agent": USER_AGENT}, stream=True)
        return r.status_code, None
    except requests.RequestException as e:
        return None, str(e)


def main():
    if not FEEDS:
        print('No feeds provided in JOB_ALERT_FEEDS. Exiting.')
        return

    geolocator = Nominatim(user_agent=USER_AGENT)
    cache = load_cache(CACHE_FILE)

    items = []
    seen = set()

    for feed_url in FEEDS:
        print('Parsing feed', feed_url)
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print('Failed to parse feed', feed_url, e)
            continue
        for entry in parsed.entries:
            title = clean_html(getattr(entry, 'title', '') or '')
            link = getattr(entry, 'link', '') or ''
            summary = clean_html(getattr(entry, 'summary', '') or '')
            published = getattr(entry, 'published', '') or ''
            blob = (title + ' ' + summary).lower()

            # basic link / scheme check
            if not link or urlparse(link).scheme not in ('http', 'https'):
                continue

            # location filter (approx) — check if any location term appears in text
            if not any(loc in blob for loc in LOCATION_TERMS):
                # try to use entry.location or tags
                loc_field = getattr(entry, 'location', '') or ''
                if not loc_field and hasattr(entry, 'tags'):
                    loc_field = ' '.join([t.get('term','') for t in entry.tags or []])
                if not any(loc in (loc_field or '').lower() for loc in LOCATION_TERMS):
                    # skip if location doesn't mention Drummondville area
                    continue

            norm = normalize_url(link)
            key = norm or (title + '|' + (getattr(entry, 'author', '') or ''))
            if key in seen:
                continue
            seen.add(key)

            # classify
            cat = classify(blob)
            # salary parsing
            salary = parse_salary(title + ' ' + summary)

            # attempt geocode from entry location or detect place token in text
            place_guess = ''
            if hasattr(entry, 'location') and entry.location:
                place_guess = entry.location
            else:
                # try to find a city mention substring: first matching location term in blob
                for lt in LOCATION_TERMS:
                    if lt in blob:
                        place_guess = lt
                        break
            coord = None
            distance_km = None
            distanceNeedsVerification = True
            if place_guess:
                coord = geocode_location(geolocator, cache, place_guess + ', QC, Canada')
                if coord:
                    try:
                        distance_km = round(geodesic(DRUMMONDVILLE_COORD, coord).kilometers, 1)
                        distanceNeedsVerification = False
                    except Exception:
                        distance_km = None

            # check url server-side
            status_code, err = check_url(link)
            link_ok = (status_code is not None and status_code < 400)

            # build id
            h = hashlib.sha1((norm or (title + link)).encode('utf-8')).hexdigest()[:12]
            company = getattr(entry, 'author', '') or getattr(entry, 'source', '') or 'À vérifier dans l\'annonce'
            source = 'RSS'
            domain = urlparse(link).netloc.replace('www.', '')
            if 'indeed.' in domain:
                source = 'Indeed (via alert)'
            elif 'jobillico' in domain:
                source = 'Jobillico (via alert)'
            elif 'guichetemplois' in domain or 'guichetemplois.gc.ca' in domain:
                source = 'Guichet-Emplois'

            item = {
                'id': 'feed-' + h,
                'title': title[:200],
                'company': company,
                'category': cat,
                'salary': salary,
                'km': distance_km,
                'url': link,
                'source': source,
                'description': summary[:2000],
                'status': 'review',
                'created': datetime.now(timezone.utc).isoformat(),
                'feedItem': True,
                'salaryNeedsVerification': salary is None or (isinstance(salary, (int,float)) and salary < 18),
                'distanceNeedsVerification': distanceNeedsVerification,
                'linkStatusCode': status_code,
                'linkError': err
            }

            # if distance calculated and > MAX_DISTANCE_KM, skip
            if distance_km is not None and distance_km > MAX_DISTANCE_KM:
                print(f"Skipping {title} — distance {distance_km} km > {MAX_DISTANCE_KM}")
                continue

            items.append(item)

    # limit size
    items = sorted(items, key=lambda x: x.get('created', ''), reverse=True)[:500]

    out = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'Aggregated RSS',
        'jobs': items
    }

    # save cache
    save_cache(CACHE_FILE, cache)

    # write jobs.json only if changed
    save_json_if_changed(OUT, out)


if __name__ == '__main__':
    main()
