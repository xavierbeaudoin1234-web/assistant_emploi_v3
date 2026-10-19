import os, json, re, hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
import feedparser

OUT = "jobs.json"
FEEDS = [x.strip() for x in os.environ.get("JOB_ALERT_FEEDS", "").splitlines() if x.strip()]

CATEGORY_KEYWORDS = {
    "Entrepôt": ["entrepôt", "warehouse", "inventaire", "réception", "expédition", "manutention", "commis d'entrepôt", "préparateur de commandes", "stock"],
    "Commerce et vente": ["vente", "vendeur", "conseiller", "commis de plancher", "commerce", "magasin", "retail", "sales", "cellulaire"],
    "Informatique et électronique": ["informatique", "technicien", "support technique", "électronique", "ordinateur", "technologie", "téléphone", "zebra"],
    "Service à la clientèle": ["service à la clientèle", "clientèle", "customer service", "accueil", "centre d'appel", "conseiller service", "réceptionniste"],
}
LOCATION_TERMS = ["drummondville", "saint-nicéphore", "saint-nicephore", "wickham", "saint-cyrille", "saint-germain-de-grantham", "saint-majorique", "saint-joachim-de-courval", "saint-bonaventure", "saint-lucien"]
SALARY_RE = re.compile(r"(?:\$\s?)(\d{2}(?:[.,]\d{1,2})?)\s*(?:/\s?h|par heure|de l'heure|l'heure)?|(?:\b)(\d{2}(?:[.,]\d{1,2})?)\s*\$\s*(?:/\s?h|par heure|de l'heure|l'heure)", re.I)

def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()

def classify(text):
    t = text.lower()
    best, count = "Service à la clientèle", 0
    for cat, words in CATEGORY_KEYWORDS.items():
        n = sum(1 for w in words if w in t)
        if n > count:
            best, count = cat, n
    return best

def parse_salary(text):
    for m in SALARY_RE.finditer(text or ""):
        raw = next((g for g in m.groups() if g), None)
        if raw:
            try:
                n = float(raw.replace(",", "."))
                if 10 <= n <= 100:
                    return n
            except ValueError:
                pass
    return None

items, seen = [], set()
for feed_url in FEEDS:
    parsed = feedparser.parse(feed_url)
    for entry in parsed.entries:
        title = clean_html(getattr(entry, "title", "Offre d'emploi"))
        link = getattr(entry, "link", "")
        summary = clean_html(getattr(entry, "summary", ""))
        blob = (title + " " + summary).lower()
        if not link or urlparse(link).scheme not in ("http", "https"):
            continue
        if not any(loc in blob for loc in LOCATION_TERMS):
            continue
        cat = classify(blob)
        if not any(word in blob for word in sum(CATEGORY_KEYWORDS.values(), [])):
            continue
        key = link.split("?")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        company = "À vérifier dans l'annonce"
        domain = urlparse(link).netloc.replace("www.", "")
        source = "Google Alerts"
        if "indeed." in domain:
            source = "Indeed (via alerte de recherche)"
        elif "jobillico.com" in domain:
            source = "Jobillico (via alerte de recherche)"
        salary = parse_salary(blob)
        items.append({
            "id": "feed-" + h,
            "title": title[:180],
            "company": company,
            "category": cat,
            "salary": salary,
            "km": None,
            "url": link,
            "source": source,
            "description": summary[:1200],
            "status": "review",
            "created": datetime.now(timezone.utc).isoformat(),
            "feedItem": True,
            "salaryNeedsVerification": salary is None or salary < 18,
            "distanceNeedsVerification": True
        })

# Newest first; cap the dashboard feed to a manageable size.
items = items[:250]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "source": "Google Alerts RSS", "jobs": items}, f, ensure_ascii=False, indent=2)
print(f"Écrit {len(items)} offre(s) candidates dans {OUT}")
