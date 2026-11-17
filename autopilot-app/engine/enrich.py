"""Step 2 — find a PUBLICLY PUBLISHED contact email + facts for the site (Claude with web search).

Compliance: CASL's "conspicuous publication" exemption only covers an address the business itself
published, with no "no unsolicited messages" notice, and an offer relevant to the business.
We store the source URL as evidence and skip anything that doesn't meet that bar.
"""
import re

from .config import Config
from .db import DB
from .llm import LLM

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
BAD_EMAIL = ("noreply", "no-reply", "example.", "sentry", "wix", "godaddy", "@yelp", "@google")

SYSTEM = """You research small local businesses for a web studio.
Find the business's OWN publicly published contact email (on its Facebook/Instagram page, Google listing,
a directory listing it controls, or local chamber listing). Never guess or construct an address.
Also gather short, factual details useful for a one-page website. Do not invent anything."""

PROMPT = """Business: {name}
Category: {category}
Address: {address}
Phone: {phone}
Google rating: {rating} ({reviews} reviews)

Search the web for this exact business (match name + address/phone). Return JSON:
{{
  "email": "address or null",
  "email_source_url": "URL of the page where the business itself published the email, or null",
  "source_is_business_controlled": true/false,
  "no_solicitation_notice": true/false,   // the page says it does not want unsolicited messages
  "owner_first_name": "only if clearly stated, else null",
  "services": ["up to 6 real services/products they offer"],
  "highlights": ["up to 3 factual selling points, e.g. 'Family-run since 2009', 'Walk-ins welcome'"],
  "social": {{"facebook": null, "instagram": null, "whatsapp": null}},
  "languages_spoken": [],
  "confidence": 0.0-1.0                   // that this is the same business
}}"""


def mock_enrich(row):
    slug = re.sub(r"[^a-z0-9]+", "", row["name"].lower())[:16]
    import random
    return {
        "email": f"{slug}@demo-mail.test" if random.random() > 0.2 else None,
        "email_source_url": "https://www.facebook.com/example",
        "source_is_business_controlled": True,
        "no_solicitation_notice": False,
        "owner_first_name": None,
        "services": [],
        "highlights": [],
        "social": {},
        "confidence": 0.9,
    }


def valid_email(e: str | None) -> bool:
    return bool(e) and bool(EMAIL_RE.match(e)) and not any(b in e.lower() for b in BAD_EMAIL)


def run(cfg: Config, db: DB, llm: LLM, log=print, limit=None) -> int:
    rows = db.by_status("found", limit=limit or cfg["limits"]["max_sites_per_run"])
    ok = 0
    for row in rows:
        try:
            info = llm.ask_json(SYSTEM, PROMPT.format(**dict(row)), web_search=True,
                                mock=lambda: __import__("json").dumps(mock_enrich(row)))
        except Exception as e:  # noqa: BLE001
            db.log(row["id"], "enrich_error", str(e))
            log(f"  ! {row['name']}: enrich failed ({e})")
            continue

        email = (info.get("email") or "").strip()
        reasons = []
        if not valid_email(email):
            reasons.append("no valid published email")
        if not info.get("email_source_url") or not info.get("source_is_business_controlled"):
            reasons.append("email not published by the business itself")
        if info.get("no_solicitation_notice"):
            reasons.append("page says no unsolicited messages")
        if (info.get("confidence") or 0) < 0.7:
            reasons.append("low match confidence")
        if email and db.is_suppressed(email):
            reasons.append("suppressed")

        facts = {k: info.get(k) for k in ("services", "highlights", "social", "languages_spoken")}
        if reasons:
            db.update(row["id"], status="no_email", facts=facts)
            db.log(row["id"], "skipped", "; ".join(reasons))
            log(f"  - {row['name']}: skipped ({'; '.join(reasons)})")
            continue

        db.update(row["id"], status="enriched", email=email, email_source=info["email_source_url"],
                  owner_name=info.get("owner_first_name"), facts=facts)
        db.log(row["id"], "enriched", f"{email} via {info['email_source_url']}")
        log(f"  ✓ {row['name']}: {email}")
        ok += 1
    return ok
