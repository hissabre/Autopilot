"""Step 1 — find active, well-reviewed businesses with no real website (Google Places API, New)."""
import json
import random
import time
from urllib.parse import urlparse

import requests

from .config import RES, Config
from .db import DB

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ",".join("places." + f for f in [
    "id", "displayName", "formattedAddress", "nationalPhoneNumber", "internationalPhoneNumber",
    "websiteUri", "rating", "userRatingCount", "businessStatus", "primaryType", "primaryTypeDisplayName",
    "regularOpeningHours", "googleMapsUri", "location", "editorialSummary", "reviews", "types",
]) + ",nextPageToken"

SOCIAL = ("facebook.com", "fb.com", "instagram.com", "linktr.ee", "tiktok.com", "wa.me", "yelp.", "business.site")
CHAIN_HINTS = ("tim hortons", "starbucks", "mcdonald", "subway", "great clips", "supercuts", "jiffy lube",
               "midas", "canadian tire", "walmart", "costco", "orange money", "total energies")


def has_real_website(uri: str | None, social_counts_as_none: bool) -> bool:
    if not uri:
        return False
    host = urlparse(uri).netloc.lower()
    if social_counts_as_none and any(s in host for s in SOCIAL):
        return False
    return True


FAKE = {
    "en": {"first": ["Maple", "Fraser", "Cedar", "Northside", "Golden", "Harbour", "Willow", "Summit", "Riverside", "Oak & Iron",
                     "Lumi", "Kingsway", "Blue Door", "Pacific", "Elm Street"],
           "kinds": [("Barber Shop", "Barber shop"), ("Bakery", "Bakery"), ("Nails & Spa", "Nail salon"),
                     ("Lawn Care", "Landscaper"), ("Auto Repair", "Auto repair shop"), ("Cleaning Co.", "Cleaning service"),
                     ("Hair Studio", "Hair salon"), ("Café", "Cafe"), ("Plumbing", "Plumber")],
           "street": ["Fraser Hwy", "200 St", "Glover Rd", "Logan Ave", "56 Ave", "88 Ave"]},
    "fr": {"first": ["Chez Awa", "Le Baobab", "Djoliba", "Étoile", "Sahel", "La Perle", "Niger", "Kanaga", "Le Palmier",
                     "Bamba", "Soleil d'Or", "Fatou", "Wassoulou"],
           "kinds": [("Coiffure", "Salon de coiffure"), ("Restaurant", "Restaurant"), ("Pâtisserie", "Pâtisserie"),
                     ("Garage", "Garage automobile"), ("Boutique", "Boutique"), ("Pressing", "Pressing"),
                     ("Maquis", "Maquis")],
           "street": ["Rue 311", "Avenue de l'Indépendance", "Boulevard du Peuple", "Rue 24", "ACI 2000", "Rue du Commerce"]},
}


def fake_places(market: dict) -> dict:
    """Test mode: invent a handful of plausible businesses so the whole pipeline can be watched safely."""
    f = FAKE.get(market["language"], FAKE["en"])
    out = []
    for _ in range(random.randint(3, 6)):
        first, (kind, typ) = random.choice(f["first"]), random.choice(f["kinds"])
        uid = f"TEST{random.getrandbits(40):x}"
        has_site = random.random() < 0.25
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] if market["language"] == "en" \
            else ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        out.append({
            "id": uid, "displayName": {"text": f"{first} {kind}"},
            "formattedAddress": f"{random.randint(100, 9999)} {random.choice(f['street'])}, {market['city']}",
            "nationalPhoneNumber": "(604) 555-0" + str(random.randint(100, 199)) if market["country"] == "CA"
            else f"{random.randint(60, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
            "websiteUri": "https://example-site.test" if has_site else None,
            "rating": round(random.uniform(3.4, 5.0), 1), "userRatingCount": random.randint(3, 320),
            "businessStatus": "OPERATIONAL", "primaryTypeDisplayName": {"text": typ},
            "regularOpeningHours": {"weekdayDescriptions": [f"{d}: 9:00 – 18:00" for d in days[:6]] + [f"{days[6]}: Closed"]},
            "googleMapsUri": f"https://maps.google.com/?q={first}+{kind}".replace(" ", "+"),
            "location": {"latitude": 49.104 + random.uniform(-.02, .02), "longitude": -122.66 + random.uniform(-.02, .02)},
            "reviews": [{"text": {"text": "Friendly, fast and great value. Highly recommend."}}],
        })
    return {"places": out}


def search(query: str, market: dict, cfg: Config, page_token=None) -> dict:
    if cfg.dry_run:
        return fake_places(market)
    body = {"textQuery": f"{query} in {market['city']}", "pageSize": 20,
            "languageCode": market["language"]}
    if page_token:
        body["pageToken"] = page_token
    r = requests.post(SEARCH_URL, json=body, timeout=30, headers={
        "X-Goog-Api-Key": Config.secret("GOOGLE_PLACES_API_KEY"),
        "X-Goog-FieldMask": FIELDS,
    })
    r.raise_for_status()
    return r.json()


def qualifies(place: dict, cfg: Config) -> bool:
    q = cfg["qualify"]
    if place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
        return False
    if has_real_website(place.get("websiteUri"), q["treat_social_as_no_website"]):
        return False
    if (place.get("rating") or 0) < q["min_rating"] or (place.get("userRatingCount") or 0) < q["min_reviews"]:
        return False
    name = place.get("displayName", {}).get("text", "").lower()
    if q.get("skip_chains") and any(c in name for c in CHAIN_HINTS):
        return False
    if not (place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")):
        return False  # no way to reach or verify them
    return True


def run(cfg: Config, db: DB, log=print) -> int:
    added = 0
    cap = cfg["limits"]["max_new_prospects_per_run"]
    for market in cfg.markets():
        queries = list(market["queries"])
        random.shuffle(queries)
        if cfg.dry_run:
            queries = queries[:2]
        for query in queries:
            token = None
            for _page in range(3):  # Places returns max 60 results per query
                data = search(query, market, cfg, token)
                for place in data.get("places", []):
                    if not qualifies(place, cfg):
                        continue
                    if cfg.dry_run and db.conn.execute("SELECT 1 FROM prospects WHERE name=?",
                                                       (place["displayName"]["text"],)).fetchone():
                        continue
                    pid = db.add_prospect({
                        "place_id": place["id"],
                        "market": market["id"],
                        "name": place["displayName"]["text"],
                        "category": place.get("primaryTypeDisplayName", {}).get("text") or query,
                        "address": place.get("formattedAddress"),
                        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
                        "rating": place.get("rating"),
                        "reviews": place.get("userRatingCount"),
                        "maps_url": place.get("googleMapsUri"),
                        "currency": market["currency"],
                        "raw": place,
                    })
                    if pid:
                        added += 1
                        db.log(pid, "found", f"{query} · {market['id']}")
                        log(f"  + {place['displayName']['text']} ({place.get('rating')}★, {place.get('userRatingCount')} reviews)")
                    if added >= cap:
                        return added
                token = data.get("nextPageToken")
                if not token or cfg.dry_run:
                    break
                time.sleep(2)
    return added
