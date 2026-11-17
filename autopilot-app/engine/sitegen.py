"""Step 3 — write the copy with Claude, render a polished one-page site from the template."""
import hashlib
import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import RES, Config, home
from .db import DB
from .llm import LLM

SITES_DIR = home() / "out" / "sites"
env = Environment(loader=FileSystemLoader(RES / "templates"), autoescape=select_autoescape(["html"]))

THEMES = {
    "bold":    {"bg": "#111112", "surface": "#1b1b1d", "ink": "#f3efe6", "muted": "#a8a39a", "accent": "#e5b544",
                "accent_ink": "#111112", "display": "Archivo Black", "body": "Inter", "radius": "4px"},
    "warm":    {"bg": "#fbf5ec", "surface": "#ffffff", "ink": "#2a1c13", "muted": "#7b6656", "accent": "#c2562b",
                "accent_ink": "#ffffff", "display": "Fraunces", "body": "DM Sans", "radius": "18px"},
    "fresh":   {"bg": "#f3f7f4", "surface": "#ffffff", "ink": "#10261b", "muted": "#5b6f63", "accent": "#1d8a5a",
                "accent_ink": "#ffffff", "display": "Bricolage Grotesque", "body": "DM Sans", "radius": "14px"},
    "elegant": {"bg": "#faf6f3", "surface": "#ffffff", "ink": "#241a1d", "muted": "#7d6c70", "accent": "#9e5867",
                "accent_ink": "#ffffff", "display": "Cormorant Garamond", "body": "Jost", "radius": "2px"},
}
THEME_KEYWORDS = [
    ("bold", ["barber", "auto", "garage", "repair", "mechanic", "gym", "fitness", "tattoo", "tire", "body shop",
              "coiffure homme", "plumb", "electric", "construction"]),
    ("warm", ["restaurant", "bakery", "café", "cafe", "coffee", "food", "pizza", "grill", "maquis", "pâtisserie",
              "boulangerie", "catering", "deli", "butcher"]),
    ("elegant", ["salon", "nail", "spa", "beauty", "lash", "brow", "boutique", "bridal", "florist", "jewel",
                 "coiffure", "esthétique", "couture", "tailleur"]),
    ("fresh", []),  # default
]

SYSTEM = """You are a senior copywriter at a small web studio. You write warm, specific, honest copy for
one-page websites of small local businesses. Never invent awards, years, staff names, prices or reviews.
If a detail is unknown, write around it. Keep sentences short. Write in the requested language."""

PROMPT = """Write the website copy for this business, in language "{lang}".

Name: {name}
Category: {category}
City/address: {address}
Google rating: {rating} from {reviews} reviews
Known services: {services}
Known highlights: {highlights}
What customers say (Google review snippets, paraphrase themes only, never quote): {review_themes}

Return JSON:
{{
  "seo_title": "max 60 chars",
  "seo_description": "max 155 chars",
  "eyebrow": "2-4 words above the headline, e.g. 'Langley's neighbourhood barber'",
  "headline": "max 8 words, specific to them",
  "subheadline": "1 sentence",
  "cta_call": "button label to call",
  "cta_directions": "button label for directions",
  "highlights": ["3 items, max 4 words each"],
  "services_title": "...",
  "services": [{{"name": "...", "description": "max 14 words"}}],   // 4-6 items; use known services first, otherwise the obvious core services of this category
  "about_title": "...",
  "about": "2-3 sentences, no invented facts",
  "reviews_line": "short line introducing their Google rating",
  "visit_title": "...",
  "hours_title": "...",
  "contact_title": "...",
  "contact_line": "1 sentence inviting them to call or visit",
  "footer_tagline": "max 8 words"
}}"""

LABELS = {
    "en": {"demo": "Preview designed for", "by": "by", "claim": "Make it yours →", "rating": "on Google", "reviews": "reviews",
           "call": "Call", "closed": "Hours not listed — call ahead", "whatsapp": "WhatsApp"},
    "fr": {"demo": "Aperçu conçu pour", "by": "par", "claim": "L'adopter →", "rating": "sur Google", "reviews": "avis",
           "call": "Appeler", "closed": "Horaires non indiqués — appelez avant", "whatsapp": "WhatsApp"},
}


def pick_theme(category: str, name: str) -> str:
    s = f"{category} {name}".lower()
    for theme, kws in THEME_KEYWORDS:
        if any(k in s for k in kws):
            return theme
    return "fresh"


def slugify(name: str, place_id: str, prefix: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32].strip("-")
    h = hashlib.sha1(place_id.encode()).hexdigest()[:4]
    return f"{prefix}-{base}-{h}"


def initials(name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+", name) if w.lower() not in ("the", "and", "le", "la", "les", "de", "et", "&")]
    return "".join(w[0] for w in words[:2]).upper() or name[:1].upper()


def mock_copy(row, lang):
    fr = lang == "fr"
    cat = (row["category"] or "business").lower()
    city = (row["address"] or "").split(",")[-3:-2]
    city = city[0].strip() if city else ""
    return {
        "seo_title": f"{row['name']} — {row['category']}"[:60],
        "seo_description": (f"{row['name']}, {cat} à {city}." if fr else f"{row['name']} — trusted {cat} in {city}.")[:155],
        "eyebrow": (f"{row['category']} · {city}" if city else row["category"]),
        "headline": ("Le savoir-faire du quartier" if fr else "Sharp work. Friendly chairs."),
        "subheadline": ("Un service soigné, des clients fidèles." if fr else f"A {cat} your neighbours already trust — now easier to find."),
        "cta_call": "Appeler" if fr else "Call now",
        "cta_directions": "Itinéraire" if fr else "Get directions",
        "highlights": (["Clients fidèles", "Service rapide", "Prix justes"] if fr else ["Walk-ins welcome", "Local favourite", "Fair prices"]),
        "services_title": "Nos services" if fr else "What we do",
        "services": [{"name": n, "description": d} for n, d in (
            [("Coupe classique", "Précise, propre, à votre goût."), ("Barbe", "Taille et finition au rasoir."),
             ("Enfants", "Patience et douceur pour les petits."), ("Soins", "Pour repartir frais.")] if fr else
            [("Classic cut", "Clean, precise and exactly how you like it."), ("Beard trim", "Shaped and finished with a hot towel."),
             ("Kids' cuts", "Patient, quick and tear-free."), ("Fade & taper", "Smooth blends, sharp lines."),
             ("Hot towel shave", "The old-school straight-razor treat.")])],
        "about_title": "Notre maison" if fr else "About us",
        "about": (f"{row['name']} accueille ses clients avec soin." if fr else
                  f"{row['name']} has earned a loyal following one visit at a time. Come in, relax, and leave looking your best."),
        "reviews_line": "Ce que disent nos clients" if fr else "Loved by locals",
        "visit_title": "Venez nous voir" if fr else "Visit us",
        "hours_title": "Horaires" if fr else "Hours",
        "contact_title": "Contact",
        "contact_line": "Appelez-nous ou passez nous voir." if fr else "Give us a call or just drop by.",
        "footer_tagline": "Fait avec soin." if fr else "Made with care, locally.",
    }


def build_one(row, cfg: Config, llm: LLM) -> Path:
    market = cfg.market(row["market"])
    lang = market["language"]
    raw = json.loads(row["raw"] or "{}")
    facts = json.loads(row["facts"] or "{}")
    reviews = raw.get("reviews", [])[:5]
    review_themes = " | ".join((r.get("text", {}) or {}).get("text", "")[:200] for r in reviews) or "n/a"

    copy = llm.ask_json(SYSTEM, PROMPT.format(
        lang=lang, name=row["name"], category=row["category"], address=row["address"], rating=row["rating"],
        reviews=row["reviews"], services=", ".join(facts.get("services") or []) or "unknown",
        highlights=", ".join(facts.get("highlights") or []) or "unknown", review_themes=review_themes,
    ), mock=lambda: json.dumps(mock_copy(row, lang)))

    theme_name = pick_theme(row["category"] or "", row["name"])
    slug = row["site_slug"] or slugify(row["name"], row["place_id"], cfg["deploy"]["site_prefix"])
    hours = (raw.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    loc = raw.get("location") or {}
    phone = row["phone"] or ""
    tel = re.sub(r"[^\d+]", "", phone)
    social = facts.get("social") or {}
    whatsapp = social.get("whatsapp") or (tel if market["country"] in ("ML", "CI", "SN", "BF") else None)

    html = env.get_template("site/index.html").render(
        c=copy, t=THEMES[theme_name], theme=theme_name, lang=lang, L=LABELS.get(lang, LABELS["en"]),
        name=row["name"], initials=initials(row["name"]), category=row["category"], address=row["address"],
        phone=phone, tel=tel, whatsapp=re.sub(r"[^\d]", "", whatsapp or "") or None,
        rating=row["rating"], reviews=row["reviews"], maps_url=row["maps_url"], hours=hours,
        lat=loc.get("latitude"), lng=loc.get("longitude"), social=social,
        brand=cfg["brand"], claim_mailto=f"mailto:{cfg['brand']['reply_to']}?subject=" + (
            "Je veux ce site" if lang == "fr" else "I want this website") + f" — {row['name']}",
    )
    out = SITES_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")  # demos stay out of search until claimed
    return out


def run(cfg: Config, db: DB, llm: LLM, log=print) -> int:
    n = 0
    for row in db.by_status("enriched", limit=cfg["limits"]["max_sites_per_run"]):
        try:
            out = build_one(row, cfg, llm)
        except Exception as e:  # noqa: BLE001
            db.log(row["id"], "build_error", str(e))
            log(f"  ! {row['name']}: build failed ({e})")
            continue
        db.update(row["id"], status="site_built", site_slug=out.name)
        db.log(row["id"], "site_built", out.name)
        log(f"  ✓ built {out.name}")
        n += 1
    return n
